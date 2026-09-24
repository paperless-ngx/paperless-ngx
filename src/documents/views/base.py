import logging
from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from typing import Literal
from typing import NamedTuple
from unicodedata import normalize
from urllib.parse import quote

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.db.models import Model
from django.http import FileResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from guardian.utils import get_group_obj_perms_model
from guardian.utils import get_user_obj_perms_model
from rest_framework import parsers
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents import bulk_edit
from documents.filters import DocumentFilterSet
from documents.models import Document
from documents.models import PaperlessTask
from documents.permissions import annotate_document_count_for_related_queryset
from documents.permissions import get_document_count_filter_for_user
from documents.permissions import has_perms_owner_aware
from documents.permissions import permitted_document_ids
from documents.search import SearchHit
from documents.serialisers.base import SerializerWithPerms
from documents.utils import get_boolean
from documents.versioning import get_root_document

logger = logging.getLogger("paperless.api")

_TANTIVY_SEARCH_PARAM_NAMES = ("text", "title_search", "query", "more_like_id")

# whoosh-compat's fieldname tagger (used only for SearchMode.QUERY, via the
# whoosh grammar in parse_user_query) is O(n^2) in plain word characters:
# measured at ~0.96s/10k chars, ~3.67s/20k, ~14.4s/40k against the real field
# registry. Django's DATA_UPLOAD_MAX_MEMORY_SIZE default (2.5 MB) does not
# bound this on the POST-body selection-filter path, so an unbounded query
# is a single-request CPU exhaustion vector. 4096 chars caps the worst case
# at roughly 0.16s (quadratic extrapolation from the measurements above),
# far beyond any plausible hand-typed advanced query, while still being fast
# enough to absorb inside a request handler. Applied to all three modes at
# this shared choke point: TEXT and TITLE route through simple_search_tokens
# instead and measure linear even at 20k chars, so the cap is hygiene for
# them, not a fix, but a single limit here is simpler than one exemption.
# Not exposed as a PAPERLESS_* setting: this is a hard security boundary,
# not a tunable, and a raisable ceiling would let a misconfiguration
# reintroduce the exact hazard this exists to close.
_MAX_QUERY_LENGTH: Final[int] = 4096


def _get_tantivy_query_and_mode(params):
    from documents.search import QueryTooLongError
    from documents.search import SearchMode

    if "text" in params:
        raw, mode = str(params["text"]), SearchMode.TEXT
    elif "title_search" in params:
        raw, mode = str(params["title_search"]), SearchMode.TITLE
    elif "query" in params:
        raw, mode = str(params["query"]), SearchMode.QUERY
    else:
        return None  # pragma: no cover

    if len(raw) > _MAX_QUERY_LENGTH:
        raise QueryTooLongError(len(raw), _MAX_QUERY_LENGTH)
    return raw, mode


def _get_more_like_id(query_params: dict[str, Any], user: User | None) -> int:
    try:
        more_like_doc_id = int(query_params["more_like_id"])
        more_like_doc = Document.objects.select_related("owner").get(
            pk=more_like_doc_id,
        )
    except (TypeError, ValueError, Document.DoesNotExist):
        raise PermissionDenied(_("Invalid more_like_id"))

    if user and not has_perms_owner_aware(
        user,
        "view_document",
        more_like_doc,
    ):
        raise PermissionDenied(_("Insufficient permissions."))

    return more_like_doc_id


class SearchParams(NamedTuple):
    sort_field_name: str | None
    sort_reverse: bool
    use_tantivy_sort: bool
    page_num: int
    page_size: int


class SearchResultPage(NamedTuple):
    ordered_ids: list[int]
    hits: list[SearchHit]
    page_offset: int


class ResolvedRequestDocs(NamedTuple):
    request_doc: Document
    root_doc: Document


class PassUserMixin(GenericAPIView[Any]):
    """
    Pass a user object to serializer
    """

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        if isinstance(serializer_class, type) and issubclass(
            serializer_class,
            SerializerWithPerms,
        ):
            kwargs.setdefault("user", self.request.user)
            try:
                full_perms = get_boolean(
                    str(self.request.query_params.get("full_perms", "false")),
                )
            except ValueError:
                full_perms = False
            kwargs.setdefault(
                "full_perms",
                full_perms,
            )
        return super().get_serializer(*args, **kwargs)


class BulkPermissionMixin:
    """
    Prefetch Django-Guardian permissions for a list before serialization, to avoid N+1 queries.
    """

    def _get_object_perms(
        self,
        objects: list,
        perm_codenames: list[str],
        actor: Literal["users", "groups"],
    ) -> dict[int, dict[str, list[int]]]:
        """
        Collect object-level permissions for either users or groups.
        """
        model = self.queryset.model
        obj_perm_model = (
            get_user_obj_perms_model(model)
            if actor == "users"
            else get_group_obj_perms_model(model)
        )
        id_field = "user_id" if actor == "users" else "group_id"
        ctype = ContentType.objects.get_for_model(model)
        object_pks = [obj.pk for obj in objects]

        perms_qs = obj_perm_model.objects.filter(
            content_type=ctype,
            object_pk__in=object_pks,
            permission__codename__in=perm_codenames,
        ).values_list("object_pk", id_field, "permission__codename")

        perms: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for object_pk, actor_id, codename in perms_qs:
            perms[int(object_pk)][codename].append(actor_id)

        # Ensure that all objects have all codenames, even if empty
        for pk in object_pks:
            for codename in perm_codenames:
                perms[pk][codename]

        return perms

    def get_serializer_context(self):
        """
        Get all permissions of the current list of objects at once and pass them to the serializer.
        This avoid fetching permissions object by object in database.
        """
        context = super().get_serializer_context()

        if getattr(self, "action", None) != "list":
            # Batching only pays off across a page of objects; for single-object
            # actions (retrieve, update, ...) the per-object fallback in
            # get_user_can_change()/_get_perms() is cheap and avoids scanning
            # the whole queryset here.
            return context

        # Check which objects are being paginated
        page = getattr(self, "paginator", None)
        if page and hasattr(page, "page"):
            queryset = page.page.object_list
        elif hasattr(self, "page"):
            queryset = self.page
        else:
            queryset = self.filter_queryset(self.get_queryset())

        model_name = self.queryset.model.__name__.lower()
        permission_name_view = f"view_{model_name}"
        permission_name_change = f"change_{model_name}"

        user_perms = self._get_object_perms(
            objects=queryset,
            perm_codenames=[permission_name_view, permission_name_change],
            actor="users",
        )
        group_perms = self._get_object_perms(
            objects=queryset,
            perm_codenames=[permission_name_view, permission_name_change],
            actor="groups",
        )

        context["users_view_perms"] = {
            pk: user_perms[pk][permission_name_view] for pk in user_perms
        }
        context["users_change_perms"] = {
            pk: user_perms[pk][permission_name_change] for pk in user_perms
        }
        context["groups_view_perms"] = {
            pk: group_perms[pk][permission_name_view] for pk in group_perms
        }
        context["groups_change_perms"] = {
            pk: group_perms[pk][permission_name_change] for pk in group_perms
        }

        return context


class PermissionsAwareDocumentCountMixin(BulkPermissionMixin, PassUserMixin):
    """Mixin to add document count to queryset, permissions-aware if needed"""

    # Direct FK/M2M relation name from this model to Document, used for the
    # cheap Count(filter=...) path (Correspondent, DocumentType, StoragePath).
    document_count_related_name: str = "documents"

    # Set both of these instead, for models that only reach Document through
    # an M2M/through-model table (Tag, CustomField). A plain Count(filter=...)
    # over such a relation is fine for a direct FK, but forces a much more
    # expensive plan once an M2M bridge table is involved -- see
    # annotate_document_count_for_related_queryset() for why.
    document_count_through: type[Model] | None = None
    document_count_source_field: str | None = None

    def _get_document_count_source_field(self) -> str:
        if self.document_count_source_field is None:
            msg = (
                "document_count_source_field must be set when "
                "document_count_through is configured"
            )
            raise ValueError(msg)
        return self.document_count_source_field

    def get_document_count_filter(self):
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        return get_document_count_filter_for_user(
            user,
            related_name=self.document_count_related_name,
        )

    def get_queryset(self):
        base_qs = super().get_queryset()

        if self.document_count_through:
            user = getattr(getattr(self, "request", None), "user", None)
            return annotate_document_count_for_related_queryset(
                base_qs,
                through_model=self.document_count_through,
                related_object_field=self._get_document_count_source_field(),
                user=user,
            )

        filter = self.get_document_count_filter()
        return base_qs.annotate(
            document_count=Count(
                self.document_count_related_name,
                filter=filter,
                distinct=True,
            ),
        )


class DocumentSelectionMixin:
    def _get_search_document_ids(
        self,
        *,
        user: User,
        filters: dict[str, Any],
    ) -> list[int] | None:
        search_filters = [
            filter_name
            for filter_name in _TANTIVY_SEARCH_PARAM_NAMES
            if filter_name in filters
        ]
        if not search_filters:
            return None
        if len(search_filters) > 1:
            raise ValidationError(
                {
                    "detail": _(
                        "Specify only one of text, title_search, query, or more_like_id.",
                    ),
                },
            )

        from documents.search import SearchQueryError
        from documents.search import get_backend
        from documents.search import search_query_error_messages

        filter_name = search_filters[0]
        backend = get_backend()
        search_user = None if user.is_superuser else user

        try:
            if filter_name == "more_like_id":
                more_like_doc_id = _get_more_like_id(filters, user)

                search_ids = backend.more_like_this_ids(
                    more_like_doc_id,
                    user=search_user,
                )
            else:
                query_str, search_mode = _get_tantivy_query_and_mode(filters)
                search_ids = backend.search_ids(
                    query_str,
                    user=search_user,
                    search_mode=search_mode,
                )
        except SearchQueryError as e:
            # Same user-fixable-query mapping as the search list endpoint:
            # a bad date/number in a bulk selection filter is a 400 naming
            # the value, never a 500.
            raise ValidationError({"query": search_query_error_messages(e)}) from e

        return search_ids

    def _resolve_document_ids(
        self,
        *,
        user: User,
        validated_data: dict[str, Any],
    ) -> list[int]:
        if not validated_data.get("all", False):
            # if all is not true, just pass through the provided document ids
            return validated_data["documents"]

        # otherwise, reconstruct the document list based on the provided filters
        filters = validated_data.get("filters") or {}
        orm_filters = {
            key: value
            for key, value in filters.items()
            if key not in _TANTIVY_SEARCH_PARAM_NAMES
        }
        # Operations are addressed to roots, a caller that wants
        # to act on a specific version passes its id explicitly instead
        permitted_documents = Document.objects.filter(
            id__in=permitted_document_ids(user),
            root_document__isnull=True,
        )
        # orm-filtered docs
        filtered_documents = DocumentFilterSet(
            data=orm_filters,
            queryset=permitted_documents,
            user=user,
        ).qs.distinct()
        # tantivy-filtered docs (if search params provided)
        search_filtered_ids = self._get_search_document_ids(
            user=user,
            filters=filters,
        )
        if search_filtered_ids is not None:
            filtered_documents = filtered_documents.filter(pk__in=search_filtered_ids)
        if validated_data.get("excluded_documents"):
            filtered_documents = filtered_documents.exclude(
                pk__in=validated_data["excluded_documents"],
            )
        return list(filtered_documents.values_list("pk", flat=True))


class DocumentOperationPermissionMixin(PassUserMixin, DocumentSelectionMixin):
    permission_classes = (IsAuthenticated,)
    parser_classes = (parsers.JSONParser,)
    METHOD_NAMES_REQUIRING_USER = {
        "split",
        "merge",
        "rotate",
        "delete_pages",
        "edit_pdf",
        "remove_password",
        "merge_as_versions",
    }
    # merge_as_versions doesn't queue any consume tasks
    METHOD_NAMES_REQUIRING_TRIGGER_SOURCE = METHOD_NAMES_REQUIRING_USER - {
        "merge_as_versions",
    }

    def _has_document_permissions(
        self,
        *,
        user: User,
        documents: list[int],
        method,
        parameters: dict[str, Any],
    ) -> bool:
        if user.is_superuser:
            return True

        root_docs = {
            get_root_document(doc)
            for doc in Document.objects.select_related(
                "owner",
                "root_document__owner",
            ).filter(pk__in=documents)
        }
        user_is_owner_of_all_documents = all(
            (doc.owner == user or doc.owner is None) for doc in root_docs
        )

        # check global and object permissions for all documents
        has_perms = (
            user.has_perm(
                "documents.change_document",
            )
            and not Document.global_objects.filter(
                pk__in=[doc.pk for doc in root_docs],
            )
            .exclude(
                pk__in=permitted_document_ids(user, perm="change_document"),
            )
            .exists()
        )

        # check ownership for methods that change original document
        if (
            (
                has_perms
                and method
                in [
                    bulk_edit.set_permissions,
                    bulk_edit.delete,
                    bulk_edit.rotate,
                    bulk_edit.delete_pages,
                    bulk_edit.edit_pdf,
                    bulk_edit.merge_as_versions,
                    bulk_edit.remove_password,
                ]
            )
            or (
                method in [bulk_edit.merge, bulk_edit.split]
                and parameters.get("delete_originals")
            )
            or (method == bulk_edit.edit_pdf and parameters.get("update_document"))
        ):
            has_perms = has_perms and user_is_owner_of_all_documents

        # check global add permissions for methods that create documents
        if (
            has_perms
            and (
                method in [bulk_edit.split, bulk_edit.merge]
                or (
                    method in [bulk_edit.edit_pdf, bulk_edit.remove_password]
                    and not parameters.get("update_document")
                )
            )
            and not user.has_perm("documents.add_document")
        ):
            has_perms = False

        # check global delete permissions for methods that delete documents
        if (
            has_perms
            and (
                method == bulk_edit.delete
                # Sources stop being documents of their own, and removing one
                # again afterwards needs delete_document
                or method == bulk_edit.merge_as_versions
                or (
                    method in [bulk_edit.merge, bulk_edit.split]
                    and parameters.get("delete_originals")
                )
                or (
                    method in [bulk_edit.edit_pdf, bulk_edit.remove_password]
                    and parameters.get("delete_original")
                    and not parameters.get("update_document")
                )
            )
            and not user.has_perm("documents.delete_document")
        ):
            has_perms = False

        return has_perms

    def _execute_document_action(
        self,
        *,
        method,
        validated_data: dict[str, Any],
        operation_label: str,
    ):
        documents = self._resolve_document_ids(
            user=self.request.user,
            validated_data=validated_data,
        )
        parameters = {
            k: v
            for k, v in validated_data.items()
            if k
            not in {
                "documents",
                "all",
                "filters",
                "excluded_documents",
                "from_webui",
            }
        }
        user = self.request.user
        from_webui = validated_data.get("from_webui", False)

        if method.__name__ in self.METHOD_NAMES_REQUIRING_USER:
            parameters["user"] = user
        if method.__name__ in self.METHOD_NAMES_REQUIRING_TRIGGER_SOURCE:
            parameters["trigger_source"] = (
                PaperlessTask.TriggerSource.WEB_UI
                if from_webui
                else PaperlessTask.TriggerSource.API_UPLOAD
            )

        if not self._has_document_permissions(
            user=user,
            documents=documents,
            method=method,
            parameters=parameters,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        try:
            result = method(documents, **parameters)
            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred performing {operation_label}: {e!s}")
            return HttpResponseBadRequest(
                f"Error performing {operation_label}, check logs for more detail.",
            )


def serve_file(
    *,
    doc: Document,
    use_archive: bool,
    disposition: str,
    follow_formatting: bool = False,
) -> FileResponse:
    if use_archive:
        if TYPE_CHECKING:
            assert doc.archive_filename

        file_handle = doc.archive_file
        filename = (
            doc.archive_filename
            if follow_formatting
            else doc.get_public_filename(archive=True)
        )
        mime_type = "application/pdf"
    else:
        if TYPE_CHECKING:
            assert doc.filename

        file_handle = doc.source_file
        filename = doc.filename if follow_formatting else doc.get_public_filename()
        mime_type = doc.mime_type
        # Support browser previewing csv files by using text mime type
        if mime_type in {"application/csv", "text/csv"} and disposition == "inline":
            mime_type = "text/plain"
        # Tell browsers to use UTF-8 for the text files we parse as UTF-8
        if mime_type in {"text/plain", "text/csv", "application/csv"}:
            mime_type = f"{mime_type}; charset=utf-8"

    response = FileResponse(file_handle, content_type=mime_type)
    # Firefox is not able to handle unicode characters in filename field
    # RFC 5987 addresses this issue
    # see https://datatracker.ietf.org/doc/html/rfc5987#section-4.2
    # Chromium cannot handle commas in the filename
    filename_normalized = (
        normalize("NFKD", filename.replace(",", "_"))
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
        .replace("\\", "_")
        .replace('"', "_")
    )
    filename_encoded = quote(filename)
    content_disposition = (
        f"{disposition}; "
        f'filename="{filename_normalized}"; '
        f"filename*=utf-8''{filename_encoded}"
    )
    response["Content-Disposition"] = content_disposition
    return response
