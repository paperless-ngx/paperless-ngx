from __future__ import annotations

import logging
import pickle
from binascii import hexlify
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import Final

from django.conf import settings
from django.core.cache import cache
from django.core.cache import caches

from documents.models import Document

if TYPE_CHECKING:
    from django.core.cache.backends.base import BaseCache

    from documents.classifier import DocumentClassifier

logger = logging.getLogger("paperless.caching")


@dataclass(frozen=True)
class MetadataCacheData:
    original_checksum: str
    original_metadata: list
    archive_checksum: str | None
    archive_metadata: list | None


@dataclass(frozen=True)
class SuggestionCacheData:
    classifier_version: int
    classifier_hash: str
    suggestions: dict


CLASSIFIER_VERSION_KEY: Final[str] = "classifier_version"
CLASSIFIER_HASH_KEY: Final[str] = "classifier_hash"
CLASSIFIER_MODIFIED_KEY: Final[str] = "classifier_modified"
LLM_CACHE_CLASSIFIER_VERSION: Final[int] = 1000  # Marker distinguishing LLM suggestions

CACHE_1_MINUTE: Final[int] = 60
CACHE_5_MINUTES: Final[int] = 5 * CACHE_1_MINUTE
CACHE_50_MINUTES: Final[int] = 50 * CACHE_1_MINUTE

read_cache = caches["read-cache"]


class LRUCache:
    def __init__(self, capacity: int = 128):
        self._data = OrderedDict()
        self.capacity = capacity

    def get(self, key, default=None) -> Any | None:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return default

    def set(self, key, value) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)


class StoredLRUCache(LRUCache):
    """
    LRU cache that can persist its entire contents as a single entry in a backend cache.

    Useful for sharing a cache across multiple workers or processes.

    Workflow:
        1. Load the cache state from the backend using `load()`.
        2. Use `get()` and `set()` locally as usual.
        3. Persist changes back to the backend using `save()`.
    """

    def __init__(
        self,
        backend_key: str,
        capacity: int = 128,
        backend: BaseCache = read_cache,
        backend_ttl=settings.CACHALOT_TIMEOUT,
    ):
        if backend_key is None:
            raise ValueError("backend_key is mandatory")
        super().__init__(capacity)
        self._backend_key = backend_key
        self._backend = backend
        self.backend_ttl = backend_ttl

    def load(self) -> None:
        """
        Load the whole cache content from backend storage.

        If no valid cached data exists in the backend, the local cache is cleared.
        """
        serialized_data = self._backend.get(self._backend_key)
        try:
            self._data = (
                pickle.loads(serialized_data) if serialized_data else OrderedDict()
            )
        except pickle.PickleError:
            logger.warning(
                "Cache exists in backend but could not be read (possibly invalid format)",
            )

    def save(self) -> None:
        """Save the entire local cache to the backend as a serialized object.

        The backend entry will expire after the configured TTL.
        """
        self._backend.set(
            self._backend_key,
            pickle.dumps(self._data),
            self.backend_ttl,
        )


def get_suggestion_cache_key(document_id: int) -> str:
    """
    Returns the basic key for a document's suggestions
    """
    return f"doc_{document_id}_suggest"


def get_suggestion_cache(document_id: int) -> SuggestionCacheData | None:
    """
    If possible, return the cached suggestions for the given document ID.
    The classifier needs to be matching in format and hash and the suggestions need to
    have been cached once.
    """
    from documents.classifier import DocumentClassifier

    doc_key = get_suggestion_cache_key(document_id)
    cache_hits = cache.get_many([CLASSIFIER_VERSION_KEY, CLASSIFIER_HASH_KEY, doc_key])
    # The document suggestions are in the cache
    if doc_key in cache_hits:
        doc_suggestions: SuggestionCacheData = cache_hits[doc_key]
        # The classifier format is the same
        # The classifier hash is the same
        # Then the suggestions can be used
        if (
            CLASSIFIER_VERSION_KEY in cache_hits
            and cache_hits[CLASSIFIER_VERSION_KEY] == DocumentClassifier.FORMAT_VERSION
            and cache_hits[CLASSIFIER_VERSION_KEY] == doc_suggestions.classifier_version
        ) and (
            CLASSIFIER_HASH_KEY in cache_hits
            and cache_hits[CLASSIFIER_HASH_KEY] == doc_suggestions.classifier_hash
        ):
            return doc_suggestions
        else:  # pragma: no cover
            # Remove the key because something didn't match
            cache.delete(doc_key)
    return None


def set_suggestions_cache(
    document_id: int,
    suggestions: dict,
    classifier: DocumentClassifier | None,
    *,
    timeout=CACHE_50_MINUTES,
) -> None:
    """
    Caches the given suggestions, which were generated by the given classifier.  If there is no classifier,
    this function is a no-op (there won't be suggestions then anyway)
    """
    if classifier is not None:
        doc_key = get_suggestion_cache_key(document_id)
        cache.set(
            doc_key,
            SuggestionCacheData(
                classifier.FORMAT_VERSION,
                hexlify(classifier.last_auto_type_hash).decode(),
                suggestions,
            ),
            timeout,
        )


def refresh_suggestions_cache(
    document_id: int,
    *,
    timeout: int = CACHE_50_MINUTES,
) -> None:
    """
    Refreshes the expiration of the suggestions for the given document ID
    to the given timeout
    """
    doc_key = get_suggestion_cache_key(document_id)
    cache.touch(doc_key, timeout)


def get_llm_suggestion_cache(
    document_id: int,
    backend: str,
) -> SuggestionCacheData | None:
    doc_key = get_suggestion_cache_key(document_id)
    data: SuggestionCacheData = cache.get(doc_key)

    if data and data.classifier_hash == backend:
        return data

    return None


def set_llm_suggestions_cache(
    document_id: int,
    suggestions: dict,
    *,
    backend: str,
    timeout: int = CACHE_50_MINUTES,
) -> None:
    """
    Cache LLM-generated suggestions using a backend-specific identifier (e.g. 'openai:gpt-4').
    """
    doc_key = get_suggestion_cache_key(document_id)
    cache.set(
        doc_key,
        SuggestionCacheData(
            classifier_version=LLM_CACHE_CLASSIFIER_VERSION,
            classifier_hash=backend,
            suggestions=suggestions,
        ),
        timeout,
    )


def invalidate_llm_suggestions_cache(
    document_id: int,
) -> None:
    """
    Invalidate the LLM suggestions cache for a specific document and backend.
    """
    doc_key = get_suggestion_cache_key(document_id)
    data: SuggestionCacheData = cache.get(doc_key)

    if data:
        cache.delete(doc_key)


def get_metadata_cache_key(document_id: int) -> str:
    """
    Returns the basic key for a document's metadata
    """
    return f"doc_{document_id}_metadata"


def get_metadata_cache(document_id: int) -> MetadataCacheData | None:
    """
    Returns the cached document metadata for the given document ID, as long as the metadata
    was cached once and the checksums have not changed
    """
    doc_key = get_metadata_cache_key(document_id)
    doc_metadata: MetadataCacheData | None = cache.get(doc_key)
    # The metadata exists in the cache
    if doc_metadata is not None:
        try:
            doc = Document.objects.only(
                "pk",
                "checksum",
                "archive_checksum",
                "archive_filename",
            ).get(pk=document_id)
            # The original checksums match
            # If it has one, the archive checksums match
            # Then, we can use the metadata
            if (
                doc_metadata.original_checksum == doc.checksum
                and doc.has_archive_version
                and doc_metadata.archive_checksum is not None
                and doc_metadata.archive_checksum == doc.archive_checksum
            ):
                # Refresh cache
                cache.touch(doc_key, CACHE_50_MINUTES)
                return doc_metadata
            else:  # pragma: no cover
                # Something didn't match, delete the key
                cache.delete(doc_key)
        except Document.DoesNotExist:  # pragma: no cover
            # Basically impossible, but the key existed, but the Document didn't
            cache.delete(doc_key)
    return None


def set_metadata_cache(
    document: Document,
    original_metadata: list,
    archive_metadata: list | None,
    *,
    timeout=CACHE_50_MINUTES,
) -> None:
    """
    Sets the metadata into cache for the given Document
    """
    doc_key = get_metadata_cache_key(document.pk)
    cache.set(
        doc_key,
        MetadataCacheData(
            document.checksum,
            original_metadata,
            document.archive_checksum,
            archive_metadata,
        ),
        timeout,
    )


def refresh_metadata_cache(
    document_id: int,
    *,
    timeout: int = CACHE_50_MINUTES,
) -> None:
    """
    Refreshes the expiration of the metadata for the given document ID
    to the given timeout
    """
    doc_key = get_metadata_cache_key(document_id)
    cache.touch(doc_key, timeout)


def get_thumbnail_modified_key(document_id: int) -> str:
    """
    Builds the key to store a thumbnail's timestamp
    """
    return f"doc_{document_id}_thumbnail_modified"


def clear_document_caches(document_id: int) -> None:
    """
    Removes all cached items for the given document
    """
    cache.delete_many(
        [
            get_suggestion_cache_key(document_id),
            get_metadata_cache_key(document_id),
            get_thumbnail_modified_key(document_id),
        ],
    )
