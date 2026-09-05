from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import F
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models import Window
from django.db.models.functions import Coalesce
from django.db.models.functions import RowNumber

from documents.models import Document

if TYPE_CHECKING:
    from rest_framework.request import Request


def versions_newest_first(documents: QuerySet[Document]) -> QuerySet[Document]:
    """
    Sorts versions so the newest one comes first using version_index and not on id,
    because an existing document can be merged in as a version
    """
    return documents.order_by(F("version_index").desc(nulls_last=True), "-id")


def annotate_effective_content(documents: QuerySet[Document]) -> QuerySet[Document]:
    """
    Annotates documents with the content of their newest version, falling back
    to their own, so get_effective_content() can answer from the row rather
    than querying for the versions of each document
    """
    return documents.annotate(
        effective_content=Coalesce(
            Subquery(
                versions_newest_first(
                    Document.objects.filter(root_document=OuterRef("pk")),
                ).values("content")[:1],
            ),
            F("content"),
        ),
    )


LATEST_VERSION_CONTENT_PREFETCH_ATTR = "_latest_version_content_prefetch"


def latest_version_content_prefetch() -> Prefetch:
    """
    A Prefetch for Document.versions scoped to just the newest version's
    content, for get_effective_content()'s fallback when no SQL annotation
    is present.

    Deliberately not merged into a metadata-only "versions" prefetch (the one
    used for the serialized versions list): that one fetches every historical
    version of every document, and pulling full OCR content for versions
    nobody will read wastes DB transfer/memory at scale. This one is windowed
    down to a single row per root, then bounded by Prefetch's own IN-list to
    whatever page/result set it's attached to -- one cheap bulk query total,
    not one per document and not one per version.
    """
    return Prefetch(
        "versions",
        queryset=(
            Document.objects.filter(
                root_document_id__isnull=False,
                deleted_at__isnull=True,
            )
            .annotate(
                rn=Window(
                    RowNumber(),
                    partition_by=F("root_document_id"),
                    order_by=[
                        F("version_index").desc(nulls_last=True),
                        F("id").desc(),
                    ],
                ),
            )
            .filter(rn=1)
            .only("id", "root_document_id", "content")
        ),
        to_attr=LATEST_VERSION_CONTENT_PREFETCH_ATTR,
    )


def has_prefetched_effective_content(document: Document) -> bool:
    """
    True if document.get_effective_content() can answer without an extra
    per-instance query -- an SQL ``effective_content`` annotation, the lean
    latest_version_content_prefetch(), or the metadata-only "versions"
    prefetch is already present on the instance.

    Callers that haven't set any of those up (e.g. views that build their
    own querysets independently of DocumentViewSet.get_queryset(), like
    TrashView or GlobalSearchView) intentionally don't pay for version-aware
    content resolution -- see DocumentSerializer.to_representation(), which
    uses this to decide whether to call get_effective_content() at all.
    """
    if hasattr(document, "effective_content"):
        return True
    if getattr(document, LATEST_VERSION_CONTENT_PREFETCH_ATTR, None) is not None:
        return True
    prefetched_cache = getattr(document, "_prefetched_objects_cache", None)
    return isinstance(prefetched_cache, dict) and "versions" in prefetched_cache


def sort_versions_newest_first(documents: list[Document]) -> list[Document]:
    """
    Same sorting as versions_newest_first()
    """
    return sorted(
        documents,
        key=lambda doc: (doc.version_index or 0, doc.id),
        reverse=True,
    )


class VersionResolutionError(StrEnum):
    INVALID = "invalid"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class VersionResolution:
    document: Document | None
    error: VersionResolutionError | None = None


def _document_manager(*, include_deleted: bool) -> Any:
    return Document.global_objects if include_deleted else Document.objects


def get_request_version_param(request: Request) -> str | None:
    if hasattr(request, "query_params"):
        return request.query_params.get("version")
    return None


def get_root_document(doc: Document, *, include_deleted: bool = False) -> Document:
    # Use root_document_id to avoid a query when this is already a root.
    # If root_document isn't available, fall back to the document itself.
    if doc.root_document_id is None:
        return doc
    if doc.root_document is not None:
        return doc.root_document

    manager = _document_manager(include_deleted=include_deleted)
    root_doc = manager.only("id").filter(id=doc.root_document_id).first()
    return root_doc or doc


def get_latest_version_for_root(
    root_doc: Document,
    *,
    include_deleted: bool = False,
) -> Document:
    manager = _document_manager(include_deleted=include_deleted)
    latest = versions_newest_first(manager.filter(root_document=root_doc)).first()
    return latest or root_doc


def resolve_requested_version_for_root(
    root_doc: Document,
    request: Request,
    *,
    include_deleted: bool = False,
) -> VersionResolution:
    version_param = get_request_version_param(request)
    if not version_param:
        return VersionResolution(
            document=get_latest_version_for_root(
                root_doc,
                include_deleted=include_deleted,
            ),
        )

    try:
        version_id = int(version_param)
    except (TypeError, ValueError):
        return VersionResolution(document=None, error=VersionResolutionError.INVALID)

    manager = _document_manager(include_deleted=include_deleted)
    candidate = manager.only("id", "root_document_id").filter(id=version_id).first()
    if candidate is None:
        return VersionResolution(document=None, error=VersionResolutionError.NOT_FOUND)
    if candidate.id != root_doc.id and candidate.root_document_id != root_doc.id:
        return VersionResolution(document=None, error=VersionResolutionError.NOT_FOUND)
    return VersionResolution(document=candidate)


def resolve_effective_document(
    request_doc: Document,
    request: Request,
    *,
    include_deleted: bool = False,
) -> VersionResolution:
    root_doc = get_root_document(request_doc, include_deleted=include_deleted)
    if get_request_version_param(request) is not None:
        return resolve_requested_version_for_root(
            root_doc,
            request,
            include_deleted=include_deleted,
        )
    if request_doc.root_document_id is None:
        return VersionResolution(
            document=get_latest_version_for_root(
                root_doc,
                include_deleted=include_deleted,
            ),
        )
    return VersionResolution(document=request_doc)


_EFFECTIVE_DOCUMENT_CACHE_ATTR = "_effective_document_resolution_cache"


def resolve_effective_document_by_pk(
    pk: int,
    request: Request,
    *,
    include_deleted: bool = False,
) -> VersionResolution:
    # Django's `condition()` decorator (used for ETag/Last-Modified) invokes the
    # etag_func and last_modified_func separately, and the view itself may resolve
    # again -- all against the same request. Cache per-request so a single thumb/
    # metadata/preview request doesn't redo this resolution multiple times.
    cache = getattr(request, _EFFECTIVE_DOCUMENT_CACHE_ATTR, None)
    if cache is None:
        cache = {}
        setattr(request, _EFFECTIVE_DOCUMENT_CACHE_ATTR, cache)

    key = (pk, include_deleted)
    if key in cache:
        return cache[key]

    manager = _document_manager(include_deleted=include_deleted)
    request_doc = manager.only("id", "root_document_id").filter(pk=pk).first()
    if request_doc is None:
        resolution = VersionResolution(
            document=None,
            error=VersionResolutionError.NOT_FOUND,
        )
    else:
        resolution = resolve_effective_document(
            request_doc,
            request,
            include_deleted=include_deleted,
        )

    cache[key] = resolution
    return resolution
