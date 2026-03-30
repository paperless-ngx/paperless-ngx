from __future__ import annotations

import bisect
import logging
import threading
import unicodedata
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Self
from typing import TypedDict
from typing import TypeVar

import filelock
import tantivy
from django.conf import settings
from django.utils.timezone import get_current_timezone
from guardian.shortcuts import get_users_with_perms

from documents.search._query import build_permission_filter
from documents.search._query import parse_user_query
from documents.search._schema import _wipe_index
from documents.search._schema import _write_sentinels
from documents.search._schema import build_schema
from documents.search._schema import open_or_rebuild_index
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable

    from django.contrib.auth.base_user import AbstractBaseUser
    from django.db.models import QuerySet

    from documents.models import Document

logger = logging.getLogger("paperless.search")

T = TypeVar("T")


def _identity(iterable: Iterable[T]) -> Iterable[T]:
    """Default iter_wrapper that passes through unchanged."""
    return iterable


def _ascii_fold(s: str) -> str:
    """Normalize unicode to ASCII equivalent characters."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def _extract_autocomplete_words(text_sources: list[str]) -> set[str]:
    """Extract and normalize words for autocomplete, filtering stopwords."""
    words = set()

    # Use NLTK if enabled
    if settings.NLTK_ENABLED and settings.NLTK_LANGUAGE:
        try:
            import nltk
            from nltk.corpus import stopwords
            from nltk.tokenize import word_tokenize

            # Set NLTK data path
            nltk.data.path = [settings.NLTK_DIR]

            # Get stopwords for the configured language
            try:
                stopwords.ensure_loaded()
                stop_words = frozenset(stopwords.words(settings.NLTK_LANGUAGE))
            except (AttributeError, OSError) as e:
                logger.debug(f"Could not load NLTK stopwords: {e}")
                stop_words = frozenset()

            for text in text_sources:
                if text:
                    try:
                        tokens = word_tokenize(
                            text.lower(),
                            language=settings.NLTK_LANGUAGE,
                        )
                        for token in tokens:
                            if (
                                token.isalpha()
                                and len(token) > 2
                                and token not in stop_words
                            ):
                                normalized = _ascii_fold(token)
                                if normalized:
                                    words.add(normalized)
                    except Exception as e:
                        logger.debug(f"NLTK tokenization failed: {e}")
                        # Fallback to regex
                        import re

                        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text)
                        for token in tokens:
                            normalized = _ascii_fold(token.lower())
                            if normalized and normalized not in stop_words:
                                words.add(normalized)

        except ImportError:
            logger.debug("NLTK not available, using fallback tokenization")
            # Fall through to basic tokenization
        except Exception as e:
            logger.debug(f"NLTK initialization failed: {e}")
            # Fall through to basic tokenization

    # Fallback tokenization when NLTK is disabled or unavailable
    if not words:  # Only use fallback if NLTK didn't produce results
        import re

        basic_stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        for text in text_sources:
            if text:
                tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text)
                for token in tokens:
                    normalized = _ascii_fold(token.lower())
                    if normalized and normalized not in basic_stopwords:
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
    hits: list[SearchHit]
    total: int  # total matching documents (for pagination)
    query: str  # preprocessed query string


class SearchIndexLockError(Exception):
    pass


class WriteBatch:
    """Context manager for bulk index operations with file locking."""

    def __init__(self, backend: TantivyBackend, lock_timeout: float):
        self._backend = backend
        self._lock_timeout = lock_timeout
        self._writer = None

    def __enter__(self) -> Self:
        lock_path = settings.INDEX_DIR / ".tantivy.lock"
        self._lock = filelock.FileLock(str(lock_path))

        try:
            self._lock.acquire(timeout=self._lock_timeout)
        except filelock.Timeout as e:
            raise SearchIndexLockError(
                f"Could not acquire index lock within {self._lock_timeout}s",
            ) from e

        self._writer = self._backend._index.writer()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                # Success case - commit changes
                self._writer.commit()
                self._backend._index.reload()
            else:
                # Exception occurred - discard changes
                # Writer is automatically discarded when it goes out of scope
                pass
            # Explicitly delete writer to release tantivy's internal lock
            if self._writer is not None:
                del self._writer
                self._writer = None
        finally:
            if hasattr(self, "_lock") and self._lock:
                self._lock.release()

    def add_or_update(self, document: Document) -> None:
        """Add or update a document in the batch."""
        doc = self._backend._build_tantivy_doc(document)
        self._writer.add_document(doc)

    def remove(self, doc_id: int) -> None:
        """Remove a document from the batch."""
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
    """Tantivy search backend with context manager interface."""

    def __init__(self):
        self._index = None
        self._schema = None

    def __enter__(self) -> Self:
        self._index = open_or_rebuild_index()
        register_tokenizers(self._index, settings.SEARCH_LANGUAGE)
        self._schema = self._index.schema
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Index doesn't need explicit close
        pass

    def _build_tantivy_doc(self, document: Document) -> tantivy.Document:
        """Build a tantivy Document from a Django Document instance."""
        doc = tantivy.Document()

        # Basic fields
        doc.add_unsigned("id", document.pk)
        doc.add_text("checksum", document.checksum)
        doc.add_text("title", document.title)
        doc.add_text("title_sort", document.title)
        doc.add_text("content", document.content)
        doc.add_text("bigram_content", document.content)

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

        # Tags
        for tag in document.tags.all():
            doc.add_text("tag", tag.name)
            doc.add_unsigned("tag_id", tag.pk)

        # Notes — JSON for structured queries (notes.user:alice, notes.note:text),
        # companion text field for default full-text search.
        for note in document.notes.all():
            note_data: dict[str, str] = {"note": note.note}
            if note.user:
                note_data["user"] = note.user.username
            doc.add_json("notes", note_data)
            doc.add_text("note", note.note)

        # Custom fields — JSON for structured queries (custom_fields.name:x, custom_fields.value:y),
        # companion text field for default full-text search.
        for cfi in document.custom_fields.all():
            doc.add_json(
                "custom_fields",
                {
                    "name": cfi.field.name,
                    "value": str(cfi.value),
                },
            )
            doc.add_text("custom_field", str(cfi.value))

        # Dates - created is date-only, others are full datetime
        created_date = datetime(
            document.created.year,
            document.created.month,
            document.created.day,
            tzinfo=UTC,
        )
        doc.add_date("created", created_date)
        doc.add_date("modified", document.modified)
        doc.add_date("added", document.added)

        # ASN - skip entirely when None (0 is valid)
        if document.archive_serial_number is not None:
            doc.add_unsigned("asn", document.archive_serial_number)

        # Page count - only add if not None
        if document.page_count is not None:
            doc.add_unsigned("page_count", document.page_count)

        # Number of notes
        doc.add_unsigned("num_notes", document.notes.count())

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

        # Autocomplete words with NLTK stopword filtering
        text_sources = [document.title, document.content]
        if document.correspondent:
            text_sources.append(document.correspondent.name)
        if document.document_type:
            text_sources.append(document.document_type.name)
        for tag in document.tags.all():
            text_sources.append(tag.name)

        autocomplete_words = _extract_autocomplete_words(text_sources)

        # Add sorted deduplicated words
        for word in sorted(autocomplete_words):
            doc.add_text("autocomplete_word", word)

        return doc

    def add_or_update(self, document: Document) -> None:
        """Add or update a single document with file locking."""
        with self.batch_update(lock_timeout=5.0) as batch:
            batch.add_or_update(document)

    def remove(self, doc_id: int) -> None:
        """Remove a single document with file locking."""
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
    ) -> SearchResults:
        """Search the index."""
        tz = get_current_timezone()
        user_query = parse_user_query(self._index, query, tz)

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

        searcher = self._index.searcher()
        offset = (page - 1) * page_size

        # Map sort fields
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

        # Perform search
        if sort_field and sort_field in sort_field_map:
            mapped_field = sort_field_map[sort_field]
            if sort_reverse:
                # For reverse sort, we need to use a different approach
                # tantivy doesn't directly support reverse field sorting in the Python API
                # We'll search for more results and sort in Python
                results = searcher.search(final_query, limit=offset + page_size * 10)
                # For field sorting: just DocAddress (no score)
                all_hits = [
                    (hit, 0.0) for hit in results.hits
                ]  # score is 0 for field sorts
            else:
                results = searcher.search(
                    final_query,
                    limit=offset + page_size,
                    order_by_field=mapped_field,
                )
                # For field sorting: just DocAddress (no score)
                all_hits = [
                    (hit, 0.0) for hit in results.hits
                ]  # score is 0 for field sorts
        else:
            # Score-based search returns: (score, doc_address) tuple
            results = searcher.search(final_query, limit=offset + page_size)
            # Convert to (doc_address, score) for consistency
            all_hits = [(hit[1], hit[0]) for hit in results.hits]

        total = results.count

        # Normalize scores for score-based searches
        if not sort_field and all_hits:
            scores = [hit[1] for hit in all_hits]
            max_score = max(scores) if scores else 1.0
            all_hits = [(hit[0], hit[1] / max_score) for hit in all_hits]

        # Apply threshold filter if configured
        threshold = getattr(settings, "ADVANCED_FUZZY_SEARCH_THRESHOLD", None)
        if (
            threshold is not None and not sort_field
        ):  # Only apply threshold to score-based search
            all_hits = [hit for hit in all_hits if hit[1] >= threshold]

        # Get the page's hits
        page_hits = all_hits[offset : offset + page_size]

        # Build result hits with highlights
        hits: list[SearchHit] = []
        snippet_generator = None

        for rank, (doc_address, score) in enumerate(page_hits, start=offset + 1):
            # Get the actual document from the searcher using the doc address
            actual_doc = searcher.doc(doc_address)
            doc_dict = actual_doc.to_dict()
            doc_id = doc_dict["id"][0]

            highlights: dict[str, str] = {}

            # Generate highlights if score > 0
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

                    # Try notes highlights
                    if "notes" in doc_dict:
                        notes_generator = tantivy.SnippetGenerator.create(
                            searcher,
                            final_query,
                            self._schema,
                            "notes",
                        )
                        notes_snippet = notes_generator.snippet_from_doc(actual_doc)
                        if notes_snippet:
                            highlights["notes"] = str(notes_snippet)

                except Exception as e:
                    logger.debug(f"Failed to generate highlights for doc {doc_id}: {e}")

            hits.append(
                SearchHit(
                    id=doc_id,
                    score=score,
                    rank=rank,
                    highlights=highlights,
                ),
            )

        return SearchResults(
            hits=hits,
            total=total,
            query=query,
        )

    def autocomplete(self, term: str, limit: int) -> list[str]:
        """Get autocomplete suggestions."""
        normalized_term = _ascii_fold(term.lower())

        searcher = self._index.searcher()
        # Search all documents to collect autocomplete words
        all_query = tantivy.Query.all_query()
        results = searcher.search(all_query, limit=10000)  # High limit to get all docs

        # Collect all autocomplete words
        words = set()
        for hit in results.hits:
            # For all_query, hit is (score, doc_address)
            doc_address = hit[1] if len(hit) == 2 else hit[0]

            stored_doc = searcher.doc(doc_address)
            doc_dict = stored_doc.to_dict()
            if "autocomplete_word" in doc_dict:
                for word in doc_dict["autocomplete_word"]:
                    words.add(word)

        # Sort and find matches
        sorted_words = sorted(words)

        # Use binary search to find starting position
        start_idx = bisect.bisect_left(sorted_words, normalized_term)

        # Collect matching words
        matches = []
        for i in range(start_idx, len(sorted_words)):
            word = sorted_words[i]
            if word.startswith(normalized_term):
                matches.append(word)
                if len(matches) >= limit:
                    break
            else:
                break

        return matches

    def more_like_this(
        self,
        doc_id: int,
        user: AbstractBaseUser | None,
        page: int,
        page_size: int,
    ) -> SearchResults:
        """Find documents similar to the given document."""
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
        """Get a batch context manager for bulk operations."""
        return WriteBatch(self, lock_timeout)

    def rebuild(self, documents: QuerySet, iter_wrapper: Callable = _identity) -> None:
        """Rebuild the entire search index."""
        from documents.search._tokenizer import register_tokenizers

        index_dir = settings.INDEX_DIR

        # Create new index
        _wipe_index(index_dir)
        new_index = tantivy.Index(build_schema(), path=str(index_dir))
        _write_sentinels(index_dir)
        register_tokenizers(new_index, settings.SEARCH_LANGUAGE)

        # Index all documents using the new index
        writer = new_index.writer()

        for document in iter_wrapper(documents):
            # Temporarily use new index for document building
            old_index = self._index
            old_schema = self._schema
            self._index = new_index
            self._schema = new_index.schema

            try:
                doc = self._build_tantivy_doc(document)
                writer.add_document(doc)
            finally:
                # Restore old index
                self._index = old_index
                self._schema = old_schema

        writer.commit()

        # Swap to new index
        self._index = new_index
        self._schema = new_index.schema
        self._index.reload()


# Module-level singleton with proper thread safety
_backend: TantivyBackend | None = None
_backend_lock = threading.RLock()


def get_backend() -> TantivyBackend:
    """Get the global backend instance with thread safety."""
    global _backend

    # Fast path for already initialized backend
    if _backend is not None:
        return _backend

    # Slow path with locking
    with _backend_lock:
        if _backend is None:
            _backend = TantivyBackend()
            _backend.__enter__()
        return _backend


def reset_backend() -> None:
    """Reset the global backend instance with thread safety."""
    global _backend

    with _backend_lock:
        if _backend is not None:
            _backend.__exit__(None, None, None)
        _backend = None
