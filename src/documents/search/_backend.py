from __future__ import annotations

import logging
import re
import threading
from datetime import UTC
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import Self
from typing import TypedDict
from typing import TypeVar
from typing import cast

import filelock
import regex
import tantivy
from django.conf import settings
from django.utils.timezone import get_current_timezone
from guardian.shortcuts import get_users_with_perms

from documents.search._normalize import ascii_fold
from documents.search._query import build_permission_filter
from documents.search._query import parse_simple_text_highlight_query
from documents.search._query import parse_simple_text_query
from documents.search._query import parse_simple_title_query
from documents.search._query import parse_user_query
from documents.search._schema import _write_sentinels
from documents.search._schema import build_schema
from documents.search._schema import open_or_rebuild_index
from documents.search._schema import wipe_index
from documents.search._tokenizer import register_tokenizers
from documents.utils import IterWrapper
from documents.utils import identity

if TYPE_CHECKING:
    from pathlib import Path

    from django.contrib.auth.models import AbstractUser
    from django.db.models import QuerySet

    from documents.models import Document

logger = logging.getLogger("paperless.search")

_WORD_RE = regex.compile(r"\w+")
_AUTOCOMPLETE_REGEX_TIMEOUT = 1.0  # seconds; guards against ReDoS on untrusted content

T = TypeVar("T")


class SearchMode(StrEnum):
    QUERY = "query"
    TEXT = "text"
    TITLE = "title"


def _extract_autocomplete_words(text_sources: list[str]) -> set[str]:
    """Extract and normalize words for autocomplete.

    Splits on non-word characters (matching Tantivy's simple tokenizer), lowercases,
    and ascii-folds each token. Uses the regex library with a timeout to guard against
    ReDoS on untrusted document content.
    """
    words = set()
    for text in text_sources:
        if not text:
            continue
        try:
            tokens = _WORD_RE.findall(text, timeout=_AUTOCOMPLETE_REGEX_TIMEOUT)
        except TimeoutError:  # pragma: no cover
            logger.warning(
                "Autocomplete word extraction timed out for a text source; skipping.",
            )
            continue
        for token in tokens:
            normalized = ascii_fold(token.lower())
            if normalized:
                words.add(normalized)
    return words


class SearchHit(TypedDict):
    """Type definition for search result hits."""

    id: int
    score: float
    rank: int
    highlights: dict[str, str]


class TantivyRelevanceList:
    """
    DRF-compatible list wrapper for Tantivy search results.

    Holds a lightweight ordered list of IDs (for pagination count and
    ``selection_data``) together with a small page of rich ``SearchHit``
    dicts (for serialization).  DRF's ``PageNumberPagination`` calls
    ``__len__`` to compute the total page count and ``__getitem__`` to
    slice the displayed page.

    Args:
        ordered_ids: All matching document IDs in display order.
        page_hits: Rich SearchHit dicts for the requested DRF page only.
        page_offset: Index into *ordered_ids* where *page_hits* starts.
    """

    def __init__(
        self,
        ordered_ids: list[int],
        page_hits: list[SearchHit],
        page_offset: int = 0,
    ) -> None:
        self._ordered_ids = ordered_ids
        self._page_hits = page_hits
        self._page_offset = page_offset

    def __len__(self) -> int:
        return len(self._ordered_ids)

    def __getitem__(self, key: int | slice) -> SearchHit | list[SearchHit]:
        if isinstance(key, int):
            idx = key if key >= 0 else len(self._ordered_ids) + key
            if self._page_offset <= idx < self._page_offset + len(self._page_hits):
                return self._page_hits[idx - self._page_offset]
            return SearchHit(
                id=self._ordered_ids[key],
                score=0.0,
                rank=idx + 1,
                highlights={},
            )
        start = key.start or 0
        stop = key.stop or len(self._ordered_ids)
        # DRF slices to extract the current page.  If the slice aligns
        # with our pre-fetched page_hits, return them directly.
        # We only check start — DRF always slices with stop=start+page_size,
        # which exceeds page_hits length on the last page.
        if start == self._page_offset:
            return self._page_hits[: stop - start]
        # Fallback: return stub dicts (no highlights).
        return [
            SearchHit(id=doc_id, score=0.0, rank=start + i + 1, highlights={})
            for i, doc_id in enumerate(self._ordered_ids[key])
        ]

    def get_all_ids(self) -> list[int]:
        """Return all matching document IDs in display order."""
        return self._ordered_ids


class SearchIndexLockError(Exception):
    """Raised when the search index file lock cannot be acquired within the timeout."""


class WriteBatch:
    """
    Context manager for bulk index operations with file locking.

    Provides transactional batch updates to the search index with proper
    concurrency control via file locking. All operations within the batch
    are committed atomically or rolled back on exception.

    Usage:
        with backend.batch_update() as batch:
            batch.add_or_update(document)
            batch.remove(doc_id)
    """

    def __init__(self, backend: TantivyBackend, lock_timeout: float):
        self._backend = backend
        self._lock_timeout = lock_timeout
        self._raw_writer: tantivy.IndexWriter | None = None
        self._lock = None

    @property
    def _writer(self) -> tantivy.IndexWriter:
        assert self._raw_writer is not None, (
            "WriteBatch not entered; use as context manager"
        )
        return self._raw_writer

    def __enter__(self) -> Self:
        if self._backend._path is not None:
            lock_path = self._backend._path / ".tantivy.lock"
            self._lock = filelock.FileLock(str(lock_path))
            try:
                self._lock.acquire(timeout=self._lock_timeout)
            except filelock.Timeout as e:  # pragma: no cover
                raise SearchIndexLockError(
                    f"Could not acquire index lock within {self._lock_timeout}s",
                ) from e

        self._raw_writer = self._backend._index.writer()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._writer.commit()
                self._backend._index.reload()
            # Explicitly delete writer to release tantivy's internal lock.
            # On exception the uncommitted writer is simply discarded.
            if self._raw_writer is not None:
                del self._raw_writer
                self._raw_writer = None
        finally:
            if self._lock is not None:
                self._lock.release()

    def add_or_update(
        self,
        document: Document,
        effective_content: str | None = None,
    ) -> None:
        """
        Add or update a document in the batch.

        Implements upsert behavior by deleting any existing document with the same ID
        and adding the new version. This ensures stale document data (e.g., after
        permission changes) doesn't persist in the index.

        Args:
            document: Django Document instance to index
            effective_content: Override document.content for indexing (used when
                re-indexing with newer OCR text from document versions)
        """
        self.remove(document.pk)
        doc = self._backend._build_tantivy_doc(document, effective_content)
        self._writer.add_document(doc)

    def remove(self, doc_id: int) -> None:
        """Remove a document from the batch by its primary key."""
        self._writer.delete_documents_by_query(
            tantivy.Query.term_query(self._backend._schema, "id", doc_id),
        )


class TantivyBackend:
    """
    Tantivy search backend with explicit lifecycle management.

    Provides full-text search capabilities using the Tantivy search engine.
    Supports in-memory indexes (for testing) and persistent on-disk indexes
    (for production use). Handles document indexing, search queries, autocompletion,
    and "more like this" functionality.

    The backend manages its own connection lifecycle and can be reset when
    the underlying index directory changes (e.g., during test isolation).
    """

    # Maps DRF ordering field names to Tantivy index field names.
    SORT_FIELD_MAP: dict[str, str] = {
        "title": "title_sort",
        "correspondent__name": "correspondent_sort",
        "document_type__name": "type_sort",
        "created": "created",
        "added": "added",
        "modified": "modified",
        "archive_serial_number": "asn",
        "page_count": "page_count",
        "num_notes": "num_notes",
    }

    # Fields where Tantivy's sort order matches the ORM's sort order.
    # Text-based fields (title, correspondent__name, document_type__name)
    # are excluded because Tantivy's tokenized fast fields produce different
    # ordering than the ORM's collation-based ordering.
    SORTABLE_FIELDS: frozenset[str] = frozenset(
        {
            "created",
            "added",
            "modified",
            "archive_serial_number",
            "page_count",
            "num_notes",
        },
    )

    def __init__(self, path: Path | None = None):
        # path=None → in-memory index (for tests)
        # path=some_dir → on-disk index (for production)
        self._path = path
        self._raw_index: tantivy.Index | None = None
        self._raw_schema: tantivy.Schema | None = None

    @property
    def _index(self) -> tantivy.Index:
        assert self._raw_index is not None, "Index not open; call open() first"
        return self._raw_index

    @property
    def _schema(self) -> tantivy.Schema:
        assert self._raw_schema is not None, "Schema not open; call open() first"
        return self._raw_schema

    def open(self) -> None:
        """
        Open or rebuild the index as needed.

        For disk-based indexes, checks if rebuilding is needed due to schema
        version or language changes. Registers custom tokenizers after opening.
        Safe to call multiple times - subsequent calls are no-ops.
        """
        if self._raw_index is not None:
            return  # pragma: no cover
        if self._path is not None:
            self._raw_index = open_or_rebuild_index(self._path)
        else:
            self._raw_index = tantivy.Index(build_schema())
        register_tokenizers(self._raw_index, settings.SEARCH_LANGUAGE)
        self._raw_schema = self._raw_index.schema

    def close(self) -> None:
        """
        Close the index and release resources.

        Safe to call multiple times - subsequent calls are no-ops.
        """
        self._raw_index = None
        self._raw_schema = None

    def _ensure_open(self) -> None:
        """Ensure the index is open before operations."""
        if self._raw_index is None:
            self.open()  # pragma: no cover

    def _parse_query(
        self,
        query: str,
        search_mode: SearchMode,
    ) -> tantivy.Query:
        """Parse a user query string into a Tantivy Query object."""
        tz = get_current_timezone()
        if search_mode is SearchMode.TEXT:
            return parse_simple_text_query(self._index, query)
        elif search_mode is SearchMode.TITLE:
            return parse_simple_title_query(self._index, query)
        else:
            return parse_user_query(self._index, query, tz)

    def _apply_permission_filter(
        self,
        query: tantivy.Query,
        user: AbstractUser | None,
    ) -> tantivy.Query:
        """Wrap a query with a permission filter if the user is not a superuser."""
        if user is not None:
            permission_filter = build_permission_filter(self._schema, user)
            return tantivy.Query.boolean_query(
                [
                    (tantivy.Occur.Must, query),
                    (tantivy.Occur.Must, permission_filter),
                ],
            )
        return query

    def _build_tantivy_doc(
        self,
        document: Document,
        effective_content: str | None = None,
    ) -> tantivy.Document:
        """Build a tantivy Document from a Django Document instance.

        ``effective_content`` overrides ``document.content`` for indexing —
        used when re-indexing a root document with a newer version's OCR text.
        """
        content = (
            effective_content if effective_content is not None else document.content
        )

        doc = tantivy.Document()

        # Basic fields
        doc.add_unsigned("id", document.pk)
        doc.add_text("checksum", document.checksum)
        doc.add_text("title", document.title)
        doc.add_text("title_sort", document.title)
        doc.add_text("simple_title", document.title)
        doc.add_text("content", content)
        doc.add_text("bigram_content", content)
        doc.add_text("simple_content", content)

        # Original filename - only add if not None/empty
        if document.original_filename:
            doc.add_text("original_filename", document.original_filename)

        # Correspondent
        if document.correspondent:
            doc.add_text("correspondent", document.correspondent.name)
            doc.add_text("correspondent_sort", document.correspondent.name)
            doc.add_unsigned("correspondent_id", document.correspondent_id)

        # Document type
        if document.document_type:
            doc.add_text("document_type", document.document_type.name)
            doc.add_text("type_sort", document.document_type.name)
            doc.add_unsigned("document_type_id", document.document_type_id)

        # Storage path
        if document.storage_path:
            doc.add_text("storage_path", document.storage_path.name)
            doc.add_unsigned("storage_path_id", document.storage_path_id)

        # Tags — collect names for autocomplete in the same pass
        tag_names: list[str] = []
        for tag in document.tags.all():
            doc.add_text("tag", tag.name)
            doc.add_unsigned("tag_id", tag.pk)
            tag_names.append(tag.name)

        # Notes — JSON for structured queries (notes.user:alice, notes.note:text).
        # notes_text is a plain-text companion for snippet/highlight generation;
        # tantivy's SnippetGenerator does not support JSON fields.
        num_notes = 0
        note_texts: list[str] = []
        for note in document.notes.all():
            num_notes += 1
            doc.add_json("notes", {"note": note.note, "user": note.user.username})
            note_texts.append(note.note)
        if note_texts:
            doc.add_text("notes_text", " ".join(note_texts))

        # Custom fields — JSON for structured queries (custom_fields.name:x, custom_fields.value:y),
        # companion text field for default full-text search.
        for cfi in document.custom_fields.all():
            search_value = cfi.value_for_search
            # Skip fields where there is no value yet
            if search_value is None:
                continue
            doc.add_json(
                "custom_fields",
                {
                    "name": cfi.field.name,
                    "value": search_value,
                },
            )

        # Dates
        created_date = datetime(
            document.created.year,
            document.created.month,
            document.created.day,
            tzinfo=UTC,
        )
        doc.add_date("created", created_date)
        doc.add_date("modified", document.modified)
        doc.add_date("added", document.added)

        if document.archive_serial_number is not None:
            doc.add_unsigned("asn", document.archive_serial_number)

        if document.page_count is not None:
            doc.add_unsigned("page_count", document.page_count)

        doc.add_unsigned("num_notes", num_notes)

        # Owner
        if document.owner_id:
            doc.add_unsigned("owner_id", document.owner_id)

        # Viewers with permission
        users_with_perms = get_users_with_perms(
            document,
            only_with_perms_in=["view_document"],
        )
        for user in users_with_perms:
            doc.add_unsigned("viewer_id", user.pk)

        # Autocomplete words
        text_sources = [document.title, content]
        if document.correspondent:
            text_sources.append(document.correspondent.name)
        if document.document_type:
            text_sources.append(document.document_type.name)
        text_sources.extend(tag_names)

        for word in sorted(_extract_autocomplete_words(text_sources)):
            doc.add_text("autocomplete_word", word)

        return doc

    def add_or_update(
        self,
        document: Document,
        effective_content: str | None = None,
    ) -> None:
        """
        Add or update a single document with file locking.

        Convenience method for single-document updates. For bulk operations,
        use batch_update() context manager for better performance.

        Args:
            document: Django Document instance to index
            effective_content: Override document.content for indexing
        """
        self._ensure_open()
        with self.batch_update(lock_timeout=5.0) as batch:
            batch.add_or_update(document, effective_content)

    def remove(self, doc_id: int) -> None:
        """
        Remove a single document from the index with file locking.

        Convenience method for single-document removal. For bulk operations,
        use batch_update() context manager for better performance.

        Args:
            doc_id: Primary key of the document to remove
        """
        self._ensure_open()
        with self.batch_update(lock_timeout=5.0) as batch:
            batch.remove(doc_id)

    def highlight_hits(
        self,
        query: str,
        doc_ids: list[int],
        *,
        search_mode: SearchMode = SearchMode.QUERY,
        rank_start: int = 1,
    ) -> list[SearchHit]:
        """
        Generate SearchHit dicts with highlights for specific document IDs.

        Unlike search(), this does not execute a ranked query — it looks up
        each document by ID and generates snippets against the provided query.
        Use this when you already know which documents to display (from
        search_ids + ORM filtering) and just need highlight data.

        Args:
            query: The search query (used for snippet generation)
            doc_ids: Ordered list of document IDs to generate hits for
            search_mode: Query parsing mode (for building the snippet query)
            rank_start: Starting rank value (1-based absolute position in the
                full result set; pass ``page_offset + 1`` for paginated calls)

        Returns:
            List of SearchHit dicts in the same order as doc_ids
        """
        if not doc_ids:
            return []

        self._ensure_open()
        user_query = self._parse_query(query, search_mode)
        highlight_query = user_query
        if search_mode is SearchMode.TEXT:
            highlight_query = parse_simple_text_highlight_query(self._index, query)

        # For notes_text snippet generation, we need a query that targets the
        # notes_text field directly. user_query may contain JSON-field terms
        # (e.g. notes.note:urgent) that the SnippetGenerator cannot resolve
        # against a text field. Strip field:value prefixes so bare terms like
        # "urgent" are re-parsed against notes_text, producing highlights even
        # when the original query used structured syntax.
        bare_query = re.sub(r"\w[\w.]*:", "", query).strip()
        try:
            notes_text_query = (
                self._index.parse_query(bare_query, ["notes_text"])
                if bare_query
                else user_query
            )
        except Exception:
            notes_text_query = user_query

        searcher = self._index.searcher()

        # Fetch all requested docs in a single search: user_query MUST match
        # and exactly the requested IDs MUST match (OR of term_queries).
        id_filter = tantivy.Query.boolean_query(
            [
                (
                    tantivy.Occur.Should,
                    tantivy.Query.term_query(self._schema, "id", did),
                )
                for did in doc_ids
            ],
        )
        batch_query = tantivy.Query.boolean_query(
            [
                (tantivy.Occur.Must, user_query),
                (tantivy.Occur.Must, id_filter),
            ],
        )
        batch_results = searcher.search(batch_query, limit=len(doc_ids))

        result_addrs = [addr for _score, addr in batch_results.hits]
        result_ids = cast("list[int]", searcher.fast_field_values("id", result_addrs))
        addr_by_id: dict[int, tuple[float, tantivy.DocAddress]] = {
            doc_id: (score, addr)
            for (score, addr), doc_id in zip(batch_results.hits, result_ids)
        }

        snippet_generator = None
        notes_snippet_generator = None
        hits: list[SearchHit] = []

        for rank, doc_id in enumerate(doc_ids, start=rank_start):
            if doc_id not in addr_by_id:
                continue

            score, doc_address = addr_by_id[doc_id]
            actual_doc = searcher.doc(doc_address)
            doc_dict = actual_doc.to_dict()

            highlights: dict[str, str] = {}
            try:
                if snippet_generator is None:
                    snippet_generator = tantivy.SnippetGenerator.create(
                        searcher,
                        highlight_query,
                        self._schema,
                        "content",
                    )

                content_html = snippet_generator.snippet_from_doc(actual_doc).to_html()
                if content_html:
                    highlights["content"] = content_html

                if search_mode is SearchMode.QUERY and "notes_text" in doc_dict:
                    # Use notes_text (plain text) for snippet generation — tantivy's
                    # SnippetGenerator does not support JSON fields.
                    if notes_snippet_generator is None:
                        notes_snippet_generator = tantivy.SnippetGenerator.create(
                            searcher,
                            notes_text_query,
                            self._schema,
                            "notes_text",
                        )
                    notes_html = notes_snippet_generator.snippet_from_doc(
                        actual_doc,
                    ).to_html()
                    if notes_html:
                        highlights["notes"] = notes_html

            except Exception:  # pragma: no cover
                logger.debug("Failed to generate highlights for doc %s", doc_id)

            hits.append(
                SearchHit(
                    id=doc_id,
                    score=score,
                    rank=rank,
                    highlights=highlights,
                ),
            )

        return hits

    def search_ids(
        self,
        query: str,
        user: AbstractUser | None,
        *,
        sort_field: str | None = None,
        sort_reverse: bool = False,
        search_mode: SearchMode = SearchMode.QUERY,
        limit: int | None = None,
    ) -> list[int]:
        """
        Return document IDs matching a query — no highlights or scores.

        This is the lightweight companion to search(). Use it when you need the
        full set of matching IDs (e.g. for ``selection_data``) but don't need
        scores, ranks, or highlights.

        Args:
            query: User's search query
            user: User for permission filtering (None for superuser/no filtering)
            sort_field: Field to sort by (None for relevance ranking)
            sort_reverse: Whether to reverse the sort order
            search_mode: Query parsing mode (QUERY, TEXT, or TITLE)
            limit: Maximum number of IDs to return (None = all matching docs)

        Returns:
            List of document IDs in the requested order
        """
        self._ensure_open()
        user_query = self._parse_query(query, search_mode)
        final_query = self._apply_permission_filter(user_query, user)

        searcher = self._index.searcher()
        effective_limit = limit if limit is not None else searcher.num_docs
        if effective_limit <= 0:
            return []

        if sort_field and sort_field in self.SORT_FIELD_MAP:
            mapped_field = self.SORT_FIELD_MAP[sort_field]
            results = searcher.search(
                final_query,
                limit=effective_limit,
                order_by_field=mapped_field,
                order=tantivy.Order.Desc if sort_reverse else tantivy.Order.Asc,
            )
            all_hits = [(hit[1],) for hit in results.hits]
        else:
            results = searcher.search(final_query, limit=effective_limit)
            all_hits = [(hit[1], hit[0]) for hit in results.hits]

            # Normalize scores and apply threshold (relevance search only)
            if all_hits:
                max_score = max(hit[1] for hit in all_hits) or 1.0
                all_hits = [(hit[0], hit[1] / max_score) for hit in all_hits]

            threshold = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD
            if threshold is not None:
                all_hits = [hit for hit in all_hits if hit[1] >= threshold]

        return cast(
            "list[int]",
            searcher.fast_field_values("id", [doc_addr for doc_addr, *_ in all_hits]),
        )

    def autocomplete(
        self,
        term: str,
        limit: int,
        user: AbstractUser | None = None,
    ) -> list[str]:
        """
        Get autocomplete suggestions for search queries.

        Returns words that start with the given term prefix, ranked by document
        frequency (how many documents contain each word). Optionally filters
        results to only words from documents visible to the specified user.

        NOTE: This is the hottest search path (called per keystroke).
        A future improvement would be to cache results in Redis, keyed by
        (prefix, user_id), and invalidate on index writes.

        Args:
            term: Prefix to match against autocomplete words
            limit: Maximum number of suggestions to return
            user: User for permission filtering (None for no filtering)

        Returns:
            List of word suggestions ordered by frequency, then alphabetically
        """
        self._ensure_open()
        normalized_term = ascii_fold(term.lower())
        if not normalized_term:
            return []

        searcher = self._index.searcher()

        permission_query = None
        # Intersect with permission filter so autocomplete words from
        # invisible documents don't leak to other users.
        if user is not None and not user.is_superuser:
            permission_query = build_permission_filter(self._schema, user)

        matches = searcher.terms_with_prefix(
            "autocomplete_word",
            normalized_term,
            permission_query,
            limit,
        )

        return [x[0] for x in matches]

    def more_like_this_ids(
        self,
        doc_id: int,
        user: AbstractUser | None,
        *,
        limit: int | None = None,
    ) -> list[int]:
        """
        Return IDs of documents similar to the given document — no highlights.

        Lightweight companion to more_like_this(). The original document is
        excluded from results.

        Args:
            doc_id: Primary key of the reference document
            user: User for permission filtering (None for no filtering)
            limit: Maximum number of IDs to return (None = all matching docs)

        Returns:
            List of similar document IDs (excluding the original)
        """
        self._ensure_open()
        searcher = self._index.searcher()

        id_query = tantivy.Query.term_query(self._schema, "id", doc_id)
        results = searcher.search(id_query, limit=1)

        if not results.hits:
            return []

        doc_address = results.hits[0][1]
        mlt_query = tantivy.Query.more_like_this_query(
            doc_address,
            min_doc_frequency=1,
            max_doc_frequency=None,
            min_term_frequency=1,
            max_query_terms=12,
            min_word_length=None,
            max_word_length=None,
            boost_factor=None,
        )

        final_query = self._apply_permission_filter(mlt_query, user)

        effective_limit = limit if limit is not None else searcher.num_docs
        # Fetch one extra to account for excluding the original document
        results = searcher.search(final_query, limit=effective_limit + 1)

        addrs = [addr for _score, addr in results.hits]
        all_ids = cast("list[int]", searcher.fast_field_values("id", addrs))
        ids = [rid for rid in all_ids if rid != doc_id]
        return ids[:limit] if limit is not None else ids

    def batch_update(self, lock_timeout: float = 30.0) -> WriteBatch:
        """
        Get a batch context manager for bulk index operations.

        Use this for efficient bulk document updates/deletions. All operations
        within the batch are committed atomically at the end of the context.

        Args:
            lock_timeout: Seconds to wait for file lock acquisition

        Returns:
            WriteBatch context manager

        Raises:
            SearchIndexLockError: If lock cannot be acquired within timeout
        """
        self._ensure_open()
        return WriteBatch(self, lock_timeout)

    def rebuild(
        self,
        documents: QuerySet[Document],
        iter_wrapper: IterWrapper[Document] = identity,
    ) -> None:
        """
        Rebuild the entire search index from scratch.

        Wipes the existing index and re-indexes all provided documents.
        On failure, restores the previous index state to keep the backend usable.

        Args:
            documents: QuerySet of Document instances to index
            iter_wrapper: Optional wrapper function for progress tracking
                (e.g., progress bar). Should yield each document unchanged.
        """
        # Create new index (on-disk or in-memory)
        if self._path is not None:
            wipe_index(self._path)
            new_index = tantivy.Index(build_schema(), path=str(self._path))
            _write_sentinels(self._path)
        else:
            new_index = tantivy.Index(build_schema())
        register_tokenizers(new_index, settings.SEARCH_LANGUAGE)

        # Point instance at the new index so _build_tantivy_doc uses it
        old_index, old_schema = self._raw_index, self._raw_schema
        self._raw_index = new_index
        self._raw_schema = new_index.schema

        try:
            writer = new_index.writer()
            for document in iter_wrapper(documents):
                doc = self._build_tantivy_doc(
                    document,
                    document.get_effective_content(),
                )
                writer.add_document(doc)
            writer.commit()
            new_index.reload()
        except BaseException:  # pragma: no cover
            # Restore old index on failure so the backend remains usable
            self._raw_index = old_index
            self._raw_schema = old_schema
            raise


# Module-level singleton with proper thread safety
_backend: TantivyBackend | None = None
_backend_path: Path | None = None  # tracks which INDEX_DIR the singleton uses
_backend_lock = threading.RLock()


def get_backend() -> TantivyBackend:
    """
    Get the global backend instance with thread safety.

    Returns a singleton TantivyBackend instance, automatically reinitializing
    when settings.INDEX_DIR changes. This ensures proper test isolation when
    using pytest-xdist or @override_settings that change the index directory.

    Returns:
        Thread-safe singleton TantivyBackend instance
    """
    global _backend, _backend_path

    current_path: Path = settings.INDEX_DIR

    # Fast path: backend is initialized and path hasn't changed (no lock needed)
    if _backend is not None and _backend_path == current_path:
        return _backend

    # Slow path: first call, or INDEX_DIR changed between calls
    with _backend_lock:
        # Double-check after acquiring lock — another thread may have beaten us
        if _backend is not None and _backend_path == current_path:
            return _backend  # pragma: no cover

        if _backend is not None:
            _backend.close()

        _backend = TantivyBackend(path=current_path)
        _backend.open()
        _backend_path = current_path

        return _backend


def reset_backend() -> None:
    """
    Reset the global backend instance with thread safety.

    Forces creation of a new backend instance on the next get_backend() call.
    Used for test isolation and when switching between different index directories.
    """
    global _backend, _backend_path

    with _backend_lock:
        if _backend is not None:
            _backend.close()
        _backend = None
        _backend_path = None
