from datetime import datetime
from datetime import timezone

from django.conf import settings
from django.core.cache import cache

from documents.caching import CACHE_5_MINUTES
from documents.caching import CACHE_50_MINUTES
from documents.caching import CLASSIFIER_HASH_KEY
from documents.caching import CLASSIFIER_MODIFIED_KEY
from documents.caching import CLASSIFIER_VERSION_KEY
from documents.caching import get_thumbnail_modified_key
from documents.classifier import DocumentClassifier
from documents.models import Document


def suggestions_etag(request, pk: int) -> str | None:
    """
    Returns an optional string for the ETag, allowing browser caching of
    suggestions if the classifier has not been changed and the suggested dates
    setting is also unchanged

    """
    # If no model file, no etag at all
    if not settings.MODEL_FILE.exists():
        return None
    # Check cache information
    cache_hits = cache.get_many(
        [CLASSIFIER_VERSION_KEY, CLASSIFIER_HASH_KEY],
    )
    # If the version differs somehow, no etag
    if (
        CLASSIFIER_VERSION_KEY in cache_hits
        and cache_hits[CLASSIFIER_VERSION_KEY] != DocumentClassifier.FORMAT_VERSION
    ):
        return None
    elif CLASSIFIER_HASH_KEY in cache_hits:
        # Refresh the cache and return the hash digest and the dates setting
        cache.touch(CLASSIFIER_HASH_KEY, CACHE_5_MINUTES)
        return f"{cache_hits[CLASSIFIER_HASH_KEY]}:{settings.NUMBER_OF_SUGGESTED_DATES}"
    return None


def suggestions_last_modified(request, pk: int) -> datetime | None:
    """
    Returns the datetime of classifier last modification.  This is slightly off,
    as there is not way to track the suggested date setting modification, but it seems
    unlikely that changes too often
    """
    # No file, no last modified
    if not settings.MODEL_FILE.exists():
        return None
    cache_hits = cache.get_many(
        [CLASSIFIER_VERSION_KEY, CLASSIFIER_MODIFIED_KEY],
    )
    # If the version differs somehow, no last modified
    if (
        CLASSIFIER_VERSION_KEY in cache_hits
        and cache_hits[CLASSIFIER_VERSION_KEY] != DocumentClassifier.FORMAT_VERSION
    ):
        return None
    elif CLASSIFIER_MODIFIED_KEY in cache_hits:
        # Refresh the cache and return the last modified
        cache.touch(CLASSIFIER_MODIFIED_KEY, CACHE_5_MINUTES)
        return cache_hits[CLASSIFIER_MODIFIED_KEY]
    return None


def metadata_etag(request, pk: int) -> str | None:
    """
    Metadata is extracted from the original file, so use its checksum as the
    ETag
    """
    try:
        doc = Document.objects.only("checksum").get(pk=pk)
        return doc.checksum
    except Document.DoesNotExist:  # pragma: no cover
        return None
    return None


def metadata_last_modified(request, pk: int) -> datetime | None:
    """
    Metadata is extracted from the original file, so use its modified.  Strictly speaking, this is
    not the modification of the original file, but of the database object, but might as well
    error on the side of more cautious
    """
    try:
        doc = Document.objects.only("modified").get(pk=pk)
        return doc.modified
    except Document.DoesNotExist:  # pragma: no cover
        return None
    return None


def preview_etag(request, pk: int) -> str | None:
    """
    ETag for the document preview, using the original or archive checksum, depending on the request
    """
    try:
        doc = Document.objects.only("checksum", "archive_checksum").get(pk=pk)
        use_original = (
            "original" in request.query_params
            and request.query_params["original"] == "true"
        )
        return doc.checksum if use_original else doc.archive_checksum
    except Document.DoesNotExist:  # pragma: no cover
        return None
    return None


def preview_last_modified(request, pk: int) -> datetime | None:
    """
    Uses the documents modified time to set the Last-Modified header.  Not strictly
    speaking correct, but close enough and quick
    """
    try:
        doc = Document.objects.only("modified").get(pk=pk)
        return doc.modified
    except Document.DoesNotExist:  # pragma: no cover
        return None
    return None


def thumbnail_last_modified(request, pk: int) -> datetime | None:
    """
    Returns the filesystem last modified either from cache or from filesystem.
    Cache should be (slightly?) faster than filesystem
    """
    try:
        doc = Document.objects.only("storage_type").get(pk=pk)
        if not doc.thumbnail_path.exists():
            return None
        doc_key = get_thumbnail_modified_key(pk)

        cache_hit = cache.get(doc_key)
        if cache_hit is not None:
            cache.touch(doc_key, CACHE_50_MINUTES)
            return cache_hit

        # No cache, get the timestamp and cache the datetime
        last_modified = datetime.fromtimestamp(
            doc.thumbnail_path.stat().st_mtime,
            tz=timezone.utc,
        )
        cache.set(doc_key, last_modified, CACHE_50_MINUTES)
        return last_modified
    except Document.DoesNotExist:  # pragma: no cover
        return None
