from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any

from documents.models import Document

if TYPE_CHECKING:
    from django.http import HttpRequest


class VersionResolutionError(str, Enum):
    INVALID = "invalid"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class VersionResolution:
    document: Document | None
    error: VersionResolutionError | None = None


def _document_manager(*, include_deleted: bool) -> Any:
    return Document.global_objects if include_deleted else Document.objects


def get_request_version_param(request: HttpRequest) -> str | None:
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


def resolve_requested_version_for_root(
    root_doc: Document,
    request: Any,
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
    request: Any,
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


def resolve_effective_document_by_pk(
    pk: int,
    request: Any,
    *,
    include_deleted: bool = False,
) -> VersionResolution:
    manager = _document_manager(include_deleted=include_deleted)
    request_doc = manager.only("id", "root_document_id").filter(pk=pk).first()
    if request_doc is None:
        return VersionResolution(document=None, error=VersionResolutionError.NOT_FOUND)
    return resolve_effective_document(
        request_doc,
        request,
        include_deleted=include_deleted,
    )
