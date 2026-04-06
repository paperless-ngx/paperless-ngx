from __future__ import annotations

import logging
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import Self
from typing import TypedDict
from typing import TypeVar

import filelock
import regex
import tantivy
from django.conf import settings
from django.utils.timezone import get_current_timezone
from guardian.shortcuts import get_users_with_perms

from documents.caching import bump_search_cache_generation
from documents.caching import get_search_results_cache
from documents.caching import set_search_results_cache
from documents.search._normalize import ascii_fold
from documents.search._query import build_permission_filter
from documents.search._query import normalize_query
from documents.search._query import parse_simple_text_query
from documents.search._query import parse_simple_title_query
from documents.search._query import parse_user_query
from documents.search._query import rewrite_natural_date_keywords
from documents.search._schema import _write_sentinels
from documents.search._schema import build_schema
from documents.search._schema import open_or_rebuild_index
from documents.search._schema import wipe_index
from documents.search._tokenizer import register_tokenizers
from documents.utils import IterWrapper
from documents.utils import identity

if TYPE_CHECKING:
    from pathlib import Path

    from django.contrib.auth.base_user import AbstractBaseUser
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


@dataclass(frozen=True, slots=True)
class SearchResults:
    """
    Container for search results with pagination metadata.

    Attributes:
        hits: List of search results with scores and highlights
        total: Total matching documents across all pages (for pagination)
        query: Raw query string as entered by the user
    """

    hits: list[SearchHit]
    total: int  # total matching documents (for pagination)
    query: str  # raw query string as entered by the user


class TantivyRelevanceList:
    """
    DRF-compatible list wrapper for Tantivy search hits.

    Provides paginated access to search results while storing all hits in memory
    for efficient ID retrieval. Used by Django REST framework for pagination.

    Methods:
        __len__: Returns total hit count for pagination calculations
        __getitem__: Slices the hit list for page-specific results

    Note: Stores ALL post-filter hits so get_all_result_ids() can return
    every matching document ID without requiring a second search query.
    """

    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits

    def __len__(self) -> int:
        return len(self._hits)

    def __getitem__(self, key: slice) -> list[SearchHit]:
        return self._hits[key]


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
        self._writer = None
        self._lock = None

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

        self._writer = self._backend._index.writer()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._writer.commit()
                self._backend._index.reload()
                bump_search_cache_generation()
            # Explicitly delete writer to release tantivy's internal lock.
            # On exception the uncommitted writer is simply discarded.
            if self._writer is not None:
                del self._writer
                self._writer = None
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
        """
        Remove a document from the batch by its primary key.

        Uses range query instead of term query to work around unsigned integer
        type detection bug in tantivy-py 0.25.
        """
        # Use range query to work around u64 deletion bug
        self._writer.delete_documents_by_query(
            tantivy.Query.range_query(
                self._backend._schema,
                "id",
                tantivy.FieldType.Unsigned,
                doc_id,
                doc_id,
            ),
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

    def __init__(self, path: Path | None = None):
        # path=None → in-memory index (for tests)
        # path=some_dir → on-disk index (for production)
        self._path = path
        self._index = None
        self._schema = None

    def open(self) -> None:
        """
        Open or rebuild the index as needed.

        For disk-based indexes, checks if rebuilding is needed due to schema
        version or language changes. Registers custom tokenizers after opening.
        Safe to call multiple times - subsequent calls are no-ops.
        """
        if self._index is not None:
            return  # pragma: no cover
        if self._path is not None:
            self._index = open_or_rebuild_index(self._path)
        else:
            self._index = tantivy.Index(build_schema())
        register_tokenizers(self._index, settings.SEARCH_LANGUAGE)
        self._schema = self._index.schema

    def close(self) -> None:
        """
        Close the index and release resources.

        Safe to call multiple times - subsequent calls are no-ops.
        """
        self._index = None
        self._schema = None

    def _ensure_open(self) -> None:
        """Ensure the index is open before operations."""
        if self._index is None:
            self.open()  # pragma: no cover

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

        # Notes — JSON for structured queries (notes.user:alice, notes.note:text),
        # companion text field for default full-text search.
        num_notes = 0
        for note in document.notes.all():
            num_notes += 1
            doc.add_json("notes", {"note": note.note, "user": note.user.username})

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

    def search(
        self,
        query: str,
        user: AbstractBaseUser | None,
        page: int,
        page_size: int,
        sort_field: str | None,
        *,
        sort_reverse: bool,
        search_mode: SearchMode = SearchMode.QUERY,
    ) -> SearchResults:
        """
        Execute a search query against the document index.

        Processes the user query through date rewriting, normalization, and
        permission filtering before executing against Tantivy. Supports both
        relevance-based and field-based sorting.

        QUERY search mode supports natural date keywords, field filters, etc.
        TITLE search mode treats the query as plain text to search for in title only
        TEXT search mode treats the query as plain text to search for in title and content

        Args:
            query: User's search query
            user: User for permission filtering (None for superuser/no filtering)
            page: Page number (1-indexed) for pagination
            page_size: Number of results per page
            sort_field: Field to sort by (None for relevance ranking)
            sort_reverse: Whether to reverse the sort order
            search_mode: "query" for advanced Tantivy syntax, "text" for
                plain-text search over title and content only, "title" for
                plain-text search over title only

        Returns:
            SearchResults with hits, total count, and the raw query string
        """
        self._ensure_open()

        user_id = user.pk if user is not None else None
        tz = get_current_timezone()

        if search_mode is SearchMode.TEXT:
            user_query = parse_simple_text_query(self._index, query)
            # TEXT/TITLE are plain-text searches — tantivy lowercases tokens, so
            # "Rechnung" and "rechnung" return identical results.  Lowercase the
            # key so both map to the same cache entry.
            effective_query_key = query.lower()
        elif search_mode is SearchMode.TITLE:
            user_query = parse_simple_title_query(self._index, query)
            effective_query_key = query.lower()
        else:
            user_query = parse_user_query(self._index, query, tz)
            # QUERY mode rewrites relative date keywords (e.g. "today", "[-7 days to now]")
            # to absolute ISO 8601 ranges at parse time.  Cache by the rewritten string so
            # that "created:today" tomorrow does not return yesterday's cached results.
            # We do not lowercase here because boolean operators (AND, OR, NOT) are
            # case-sensitive in tantivy's query parser.
            effective_query_key = normalize_query(
                rewrite_natural_date_keywords(query, tz),
            )

        # Apply permission filter if user is not None (not superuser)
        if user is not None:
            permission_filter = build_permission_filter(self._schema, user)
            final_query = tantivy.Query.boolean_query(
                [
                    (tantivy.Occur.Must, user_query),
                    (tantivy.Occur.Must, permission_filter),
                ],
            )
        else:
            final_query = user_query

        full_results = self._fetch_all_hits(
            query,
            effective_query_key,
            search_mode,
            user_id,
            final_query,
            sort_field,
            sort_reverse=sort_reverse,
        )

        # Cache hit path: slice only — zero tantivy calls.
        offset = (page - 1) * page_size
        return SearchResults(
            hits=full_results.hits[offset : offset + page_size],
            total=full_results.total,
            query=full_results.query,
        )

    def _fetch_all_hits(
        self,
        query: str,
        effective_query_key: str,
        search_mode: str,
        user_id: int | None,
        final_query: tantivy.Query,
        sort_field: str | None,
        *,
        sort_reverse: bool,
    ) -> SearchResults:
        """Fetch, score, and build all matching hits for a query.

        Results are cached keyed by (effective_query_key, search_mode, user_id,
        sort_field, sort_reverse) with no pagination parameters — the full hit
        list including precomputed highlights is stored once and sliced per page
        by the caller.

        Highlights are generated here, not in ``search()``, because
        ``SnippetGenerator.create()`` is the expensive step — it loads posting
        lists for all query terms across every segment regardless of how many
        docs you ultimately call ``snippet_from_doc()`` on.  Paying that cost
        once on cache miss and storing the result strings means cache hits are a
        free list slice with zero tantivy work.

        All stored field types are plain Python (int, float, str, dict) — safely
        picklable by Redis or any other Django cache backend.

        ``effective_query_key`` ensures QUERY mode date expressions like
        "created:today" resolve to an absolute ISO range and never return stale
        results across day boundaries.

        ``total`` is clamped to ``len(all_hits)`` after filtering so pagination
        stays consistent with the hard ``_MAX_HITS`` cap.
        """
        cached: SearchResults | None = get_search_results_cache(
            effective_query_key,
            search_mode,
            user_id,
            sort_field,
            sort_reverse=sort_reverse,
        )
        if cached is not None:
            return cached

        searcher = self._index.searcher()

        _MAX_HITS = 10_000
        sort_field_map = {
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

        if sort_field and sort_field in sort_field_map:
            mapped_field = sort_field_map[sort_field]
            results = searcher.search(
                final_query,
                limit=_MAX_HITS,
                order_by_field=mapped_field,
                order=tantivy.Order.Desc if sort_reverse else tantivy.Order.Asc,
            )
            # Field sorting: hits are (score, DocAddress) tuples; score unused
            all_hits = [(hit[1], 0.0) for hit in results.hits]
        else:
            # Score-based search: hits are (score, DocAddress) tuples
            results = searcher.search(final_query, limit=_MAX_HITS)
            all_hits = [(hit[1], hit[0]) for hit in results.hits]

        # Normalize scores for score-based searches
        if not sort_field and all_hits:
            max_score = max(hit[1] for hit in all_hits) or 1.0
            all_hits = [(hit[0], hit[1] / max_score) for hit in all_hits]

        # Apply threshold filter if configured (score-based search only)
        threshold = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD
        if threshold is not None and not sort_field:
            all_hits = [hit for hit in all_hits if hit[1] >= threshold]

        # total is clamped to the number of hits we can actually serve.
        # results.count may exceed _MAX_HITS; reporting it would produce empty
        # pages beyond the cap while the UI shows a misleadingly large total.
        total = len(all_hits)

        hits: list[SearchHit] = []
        snippet_generator = None
        notes_snippet_generator = None

        for rank, (doc_address, score) in enumerate(all_hits, start=1):
            actual_doc = searcher.doc(doc_address)
            doc_dict = actual_doc.to_dict()
            doc_id = doc_dict["id"][0]

            highlights: dict[str, str] = {}

            if score > 0:
                try:
                    if snippet_generator is None:
                        snippet_generator = tantivy.SnippetGenerator.create(
                            searcher,
                            final_query,
                            self._schema,
                            "content",
                        )

                    content_snippet = snippet_generator.snippet_from_doc(actual_doc)
                    if content_snippet:
                        highlights["content"] = str(content_snippet)

                    if "notes" in doc_dict:
                        if notes_snippet_generator is None:
                            notes_snippet_generator = tantivy.SnippetGenerator.create(
                                searcher,
                                final_query,
                                self._schema,
                                "notes",
                            )
                        notes_snippet = notes_snippet_generator.snippet_from_doc(
                            actual_doc,
                        )
                        if notes_snippet:
                            highlights["notes"] = str(notes_snippet)

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

        full_results = SearchResults(hits=hits, total=total, query=query)
        set_search_results_cache(
            effective_query_key,
            search_mode,
            user_id,
            sort_field,
            sort_reverse=sort_reverse,
            results=full_results,
        )
        return full_results

    def autocomplete(
        self,
        term: str,
        limit: int,
        user: AbstractBaseUser | None = None,
    ) -> list[str]:
        """
        Get autocomplete suggestions for search queries.

        Returns words that start with the given term prefix, ranked by document
        frequency (how many documents contain each word). Optionally filters
        results to only words from documents visible to the specified user.

        Args:
            term: Prefix to match against autocomplete words
            limit: Maximum number of suggestions to return
            user: User for permission filtering (None for no filtering)

        Returns:
            List of word suggestions ordered by frequency, then alphabetically
        """
        self._ensure_open()
        normalized_term = ascii_fold(term.lower())

        searcher = self._index.searcher()

        # Apply permission filter for non-superusers so autocomplete words
        # from invisible documents don't leak to other users.
        if user is not None and not user.is_superuser:
            base_query = build_permission_filter(self._schema, user)
        else:
            base_query = tantivy.Query.all_query()

        results = searcher.search(base_query, limit=10000)

        # Count how many visible documents each word appears in.
        # Using Counter (not set) preserves per-word document frequency so
        # we can rank suggestions by how commonly they occur — the same
        # signal Whoosh used for Tf/Idf-based autocomplete ordering.
        word_counts: Counter[str] = Counter()
        for _score, doc_address in results.hits:
            stored_doc = searcher.doc(doc_address)
            doc_dict = stored_doc.to_dict()
            if "autocomplete_word" in doc_dict:
                word_counts.update(doc_dict["autocomplete_word"])

        # Filter to prefix matches, sort by document frequency descending;
        # break ties alphabetically for stable, deterministic output.
        matches = sorted(
            (w for w in word_counts if w.startswith(normalized_term)),
            key=lambda w: (-word_counts[w], w),
        )

        return matches[:limit]

    def more_like_this(
        self,
        doc_id: int,
        user: AbstractBaseUser | None,
        page: int,
        page_size: int,
    ) -> SearchResults:
        """
        Find documents similar to the given document using content analysis.

        Uses Tantivy's "more like this" query to find documents with similar
        content patterns. The original document is excluded from results.

        Args:
            doc_id: Primary key of the reference document
            user: User for permission filtering (None for no filtering)
            page: Page number (1-indexed) for pagination
            page_size: Number of results per page

        Returns:
            SearchResults with similar documents (excluding the original)
        """
        self._ensure_open()
        searcher = self._index.searcher()

        # First find the document address
        id_query = tantivy.Query.range_query(
            self._schema,
            "id",
            tantivy.FieldType.Unsigned,
            doc_id,
            doc_id,
        )
        results = searcher.search(id_query, limit=1)

        if not results.hits:
            # Document not found
            return SearchResults(hits=[], total=0, query=f"more_like:{doc_id}")

        # Extract doc_address from (score, doc_address) tuple
        doc_address = results.hits[0][1]

        # Build more like this query
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

        # Apply permission filter
        if user is not None:
            permission_filter = build_permission_filter(self._schema, user)
            final_query = tantivy.Query.boolean_query(
                [
                    (tantivy.Occur.Must, mlt_query),
                    (tantivy.Occur.Must, permission_filter),
                ],
            )
        else:
            final_query = mlt_query

        # Search
        offset = (page - 1) * page_size
        results = searcher.search(final_query, limit=offset + page_size)

        total = results.count
        # Convert from (score, doc_address) to (doc_address, score)
        all_hits = [(hit[1], hit[0]) for hit in results.hits]

        # Normalize scores
        if all_hits:
            max_score = max(hit[1] for hit in all_hits) or 1.0
            all_hits = [(hit[0], hit[1] / max_score) for hit in all_hits]

        # Get page hits
        page_hits = all_hits[offset : offset + page_size]

        # Build results
        hits: list[SearchHit] = []
        for rank, (doc_address, score) in enumerate(page_hits, start=offset + 1):
            actual_doc = searcher.doc(doc_address)
            doc_dict = actual_doc.to_dict()
            result_doc_id = doc_dict["id"][0]

            # Skip the original document
            if result_doc_id == doc_id:
                continue

            hits.append(
                SearchHit(
                    id=result_doc_id,
                    score=score,
                    rank=rank,
                    highlights={},  # MLT doesn't generate highlights
                ),
            )

        return SearchResults(
            hits=hits,
            total=max(0, total - 1),  # Subtract 1 for the original document
            query=f"more_like:{doc_id}",
        )

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
        old_index, old_schema = self._index, self._schema
        self._index = new_index
        self._schema = new_index.schema

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
            bump_search_cache_generation()
        except BaseException:  # pragma: no cover
            # Restore old index on failure so the backend remains usable
            self._index = old_index
            self._schema = old_schema
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
