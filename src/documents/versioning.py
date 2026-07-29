from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import Any

from documents.models import Document

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rest_framework.request import Request


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
    latest = manager.filter(root_document=root_doc).order_by("-id").first()
    return latest or root_doc


def normalize_to_root_ids(
    document_ids: Iterable[int],
    *,
    include_deleted: bool = False,
) -> list[int]:
    """
    Map a mixed collection of root and version document ids onto the ids of their
    root documents, in a single query.

    The order of first appearance is preserved and duplicates are dropped, so a
    selection containing both a root and one of its versions yields that root
    exactly once. Ids that no longer exist are silently skipped.
    """
    ordered_ids = list(dict.fromkeys(document_ids))
    if not ordered_ids:
        return []

    manager = _document_manager(include_deleted=include_deleted)
    root_id_by_id = {
        doc_id: root_id if root_id is not None else doc_id
        for doc_id, root_id in manager.filter(id__in=ordered_ids).values_list(
            "id",
            "root_document_id",
        )
    }
    return list(
        dict.fromkeys(
            root_id_by_id[doc_id] for doc_id in ordered_ids if doc_id in root_id_by_id
        ),
    )


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
