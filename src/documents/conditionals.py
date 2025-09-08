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


def _resolve_effective_doc(pk: int, request) -> Document | None:
    """
    Resolve which Document row should be considered for caching keys:
    - If a version is requested, use that version
    - If pk is a head doc, use its newest child version if present, else the head.
    - Else, pk is a version, use that version.
    Returns None if resolution fails (treat as no-cache).
    """
    try:
        request_doc = Document.objects.only("id", "head_version_id").get(pk=pk)
    except Document.DoesNotExist:
        return None

    head_doc = (
        request_doc
        if request_doc.head_version_id is None
        else Document.objects.only("id").get(id=request_doc.head_version_id)
    )

    version_param = (
        request.query_params.get("version")
        if hasattr(request, "query_params")
        else None
    )
    if version_param:
        try:
            version_id = int(version_param)
            candidate = Document.objects.only("id", "head_version_id").get(
                id=version_id,
            )
            if candidate.id != head_doc.id and candidate.head_version_id != head_doc.id:
                return None
            return candidate
        except Exception:
            return None

    # Default behavior: if pk is a head doc, prefer its newest child version
    if request_doc.head_version_id is None:
        latest = head_doc.versions.only("id").order_by("id").last()
        return latest or head_doc

    # pk is already a version
    return request_doc


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
    doc = _resolve_effective_doc(pk, request)
    if doc is None:
        return None
    return doc.checksum
    return None


def metadata_last_modified(request, pk: int) -> datetime | None:
    """
    Metadata is extracted from the original file, so use its modified.  Strictly speaking, this is
    not the modification of the original file, but of the database object, but might as well
    error on the side of more cautious
    """
    doc = _resolve_effective_doc(pk, request)
    if doc is None:
        return None
    return doc.modified
    return None


def preview_etag(request, pk: int) -> str | None:
    """
    ETag for the document preview, using the original or archive checksum, depending on the request
    """
    doc = _resolve_effective_doc(pk, request)
    if doc is None:
        return None
    use_original = (
        hasattr(request, "query_params")
        and "original" in request.query_params
        and request.query_params["original"] == "true"
    )
    return doc.checksum if use_original else doc.archive_checksum
    return None


def preview_last_modified(request, pk: int) -> datetime | None:
    """
    Uses the documents modified time to set the Last-Modified header.  Not strictly
    speaking correct, but close enough and quick
    """
    doc = _resolve_effective_doc(pk, request)
    if doc is None:
        return None
    return doc.modified
    return None


def thumbnail_last_modified(request, pk: int) -> datetime | None:
    """
    Returns the filesystem last modified either from cache or from filesystem.
    Cache should be (slightly?) faster than filesystem
    """
    try:
        doc = _resolve_effective_doc(pk, request)
        if doc is None:
            return None
        if not doc.thumbnail_path.exists():
            return None
        # Use the effective document id for cache key
        doc_key = get_thumbnail_modified_key(doc.id)

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
