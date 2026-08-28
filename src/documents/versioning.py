from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import F
from django.db.models import OuterRef
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models import Window
from django.db.models.functions import Coalesce
from django.db.models.functions import RowNumber

from documents.models import Document

if TYPE_CHECKING:
    from rest_framework.request import Request


# Ordering for "newest version first": version_index before id, because an
# existing (low-id) document can be merged in as a newer version. Defined once
# so the ORDER BY and the window function below sort identically.
def _newest_version_ordering() -> list:
    return [F("version_index").desc(nulls_last=True), F("id").desc()]


def versions_newest_first(documents: QuerySet[Document]) -> QuerySet[Document]:
    """
    Sorts versions so the newest one comes first using version_index and not on id,
    because an existing document can be merged in as a version
    """
    return documents.order_by(*_newest_version_ordering())


def latest_version_content_subquery() -> Subquery:
    """
    Returns the content of a root document's newest version as a subquery
    correlated on the root document's ``OuterRef("pk")``.

    Written to avoid a MariaDB optimizer misstep: a directly correlated
    subquery with ``ORDER BY version_index DESC, id DESC LIMIT 1`` tricks the
    optimizer into a full primary-key backward scan per outer row (instead of
    using the root_document_id index), which is >250x slower on large document
    sets. Instead the primary keys of the newest version per root are computed
    once, de-correlated, via a ROW_NUMBER() window and then matched with a
    plain ``pk__in``. The result is identical to
    ``versions_newest_first(...).values("content")[:1]``.
    """
    # De-correlated: exactly the newest version per root_document_id (rank == 1).
    latest_version_pks = (
        Document.objects.filter(root_document__isnull=False)
        .annotate(
            _version_rank=Window(
                expression=RowNumber(),
                partition_by=[F("root_document_id")],
                order_by=_newest_version_ordering(),
            ),
        )
        .filter(_version_rank=1)
        .values("pk")
    )
    # Only correlated on the root document; pk__in stays un-correlated and is
    # materialized once by the database. order_by() drops the model's
    # Meta.ordering (-created), which would otherwise add a needless filesort.
    return Subquery(
        Document.objects.filter(
            root_document_id=OuterRef("pk"),
            pk__in=latest_version_pks,
        )
        .order_by()
        .values("content")[:1],
    )


def annotate_effective_content(documents: QuerySet[Document]) -> QuerySet[Document]:
    """
    Annotates documents with the content of their newest version, falling back
    to their own, so get_effective_content() can answer from the row rather
    than querying for the versions of each document
    """
    return documents.annotate(
        effective_content=Coalesce(
            latest_version_content_subquery(),
            F("content"),
        ),
    )


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
