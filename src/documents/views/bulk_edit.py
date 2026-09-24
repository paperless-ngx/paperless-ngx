import logging
import os
import tempfile
import zipfile
from http import HTTPStatus
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from rest_framework import parsers
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents import bulk_edit
from documents.bulk_download import ArchiveOnlyStrategy
from documents.bulk_download import OriginalAndArchiveStrategy
from documents.bulk_download import OriginalsOnlyStrategy
from documents.filters import CorrespondentFilterSet
from documents.filters import DocumentTypeFilterSet
from documents.filters import StoragePathFilterSet
from documents.filters import TagFilterSet
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import PaperlessTask
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import permitted_document_ids
from documents.permissions import permitted_object_ids
from documents.permissions import set_permissions_for_objects
from documents.serialisers.bulk_edit import BulkDownloadSerializer
from documents.serialisers.bulk_edit import BulkEditObjectsSerializer
from documents.serialisers.bulk_edit import BulkEditSerializer
from documents.serialisers.bulk_edit import DeleteDocumentsSerializer
from documents.serialisers.bulk_edit import EditPdfDocumentsSerializer
from documents.serialisers.bulk_edit import MergeDocumentsAsVersionsSerializer
from documents.serialisers.bulk_edit import MergeDocumentsSerializer
from documents.serialisers.bulk_edit import RemovePasswordDocumentsSerializer
from documents.serialisers.bulk_edit import ReprocessDocumentsSerializer
from documents.serialisers.bulk_edit import RotateDocumentsSerializer
from documents.versioning import get_latest_version_for_root
from documents.versioning import get_root_document

from .base import DocumentOperationPermissionMixin
from .base import DocumentSelectionMixin
from .base import PassUserMixin

if settings.AUDIT_LOG_ENABLED:
    from auditlog.models import LogEntry


logger = logging.getLogger("paperless.api")


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_edit",
        description="Perform a bulk edit operation on a list of documents",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#bulk-editing",
        },
        responses={
            200: inline_serializer(
                name="BulkEditDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class BulkEditView(DocumentOperationPermissionMixin):
    MODIFIED_FIELD_BY_METHOD = {
        "set_correspondent": "correspondent",
        "set_document_type": "document_type",
        "set_storage_path": "storage_path",
        "add_tag": "tags",
        "remove_tag": "tags",
        "modify_tags": "tags",
        "modify_custom_fields": "custom_fields",
        "set_permissions": None,
        "delete": "deleted_at",
        # These operations create new documents/versions no longer altering
        # fields on the selected document in place
        "rotate": None,
        "delete_pages": None,
        "split": None,
        "merge": None,
        "edit_pdf": None,
        "reprocess": "checksum",
        "remove_password": None,
    }

    serializer_class = BulkEditSerializer

    @staticmethod
    def _snapshot_field(doc_ids: list[int], field: str) -> dict[int, Any]:
        """
        Returns each document's current value of field, for the audit log.

        Tags and custom fields are one row per value, so they are gathered
        into a sorted list of pks per document (empty when there are none).
        Reading them through Document.values() instead would join those rows
        and return one arbitrary value per document.
        """
        if field == "tags":
            rows = (
                Document.tags.through.objects.filter(document_id__in=doc_ids)
                .order_by("tag_id")
                .values_list("document_id", "tag_id")
            )
        elif field == "custom_fields":
            rows = (
                CustomFieldInstance.objects.filter(document_id__in=doc_ids)
                .order_by("pk")
                .values_list("document_id", "pk")
            )
        else:
            return dict(
                Document.objects.filter(pk__in=doc_ids).values_list("pk", field),
            )

        values: dict[int, list[int]] = {doc_id: [] for doc_id in doc_ids}
        for doc_id, pk in rows:
            values[doc_id].append(pk)
        return values

    def post(self, request, *args, **kwargs):
        request_method = request.data.get("method")
        api_version = int(request.version or settings.REST_FRAMEWORK["DEFAULT_VERSION"])
        # TODO: remove this and related backwards compatibility code when API v9 is dropped
        if request_method in BulkEditSerializer.LEGACY_DOCUMENT_ACTION_METHODS:
            endpoint = BulkEditSerializer.MOVED_DOCUMENT_ACTION_ENDPOINTS[
                request_method
            ]
            logger.warning(
                "Deprecated bulk_edit method '%s' requested on API version %s. "
                "Use '%s' instead.",
                request_method,
                api_version,
                endpoint,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.request.user
        method = serializer.validated_data.get("method")
        parameters = serializer.validated_data.get("parameters")
        from_webui = serializer.validated_data.get("from_webui", False)
        documents = self._resolve_document_ids(
            user=user,
            validated_data=serializer.validated_data,
        )
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
            modified_field = self.MODIFIED_FIELD_BY_METHOD.get(method.__name__, None)
            if settings.AUDIT_LOG_ENABLED and modified_field:
                old_values = self._snapshot_field(documents, modified_field)

            result = method(documents, **parameters)

            if settings.AUDIT_LOG_ENABLED and modified_field:
                new_values = self._snapshot_field(documents, modified_field)
                for doc in Document.objects.filter(pk__in=documents):
                    LogEntry.objects.log_create(
                        instance=doc,
                        changes={
                            modified_field: [
                                old_values[doc.pk],
                                new_values[doc.pk],
                            ],
                        },
                        action=LogEntry.Action.UPDATE,
                        actor=user,
                        additional_data={
                            "reason": f"Bulk edit: {method.__name__}",
                        },
                    )

            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred performing bulk edit: {e!s}")
            return HttpResponseBadRequest(
                "Error performing bulk edit, check logs for more detail.",
            )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_rotate",
        description="Rotate one or more documents",
        responses={
            200: inline_serializer(
                name="RotateDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class RotateDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = RotateDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.rotate,
            validated_data=serializer.validated_data,
            operation_label="document rotate",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_merge",
        description="Merge selected documents into a new document",
        responses={
            200: inline_serializer(
                name="MergeDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class MergeDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = MergeDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.merge,
            validated_data=serializer.validated_data,
            operation_label="document merge",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_merge_as_versions",
        description="Merge selected documents as versions of a chosen root document",
        responses={
            200: inline_serializer(
                name="MergeDocumentsAsVersionsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class MergeDocumentsAsVersionsView(DocumentOperationPermissionMixin):
    serializer_class = MergeDocumentsAsVersionsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.merge_as_versions,
            validated_data=serializer.validated_data,
            operation_label="document merge as versions",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_delete",
        description="Move selected documents to trash",
        responses={
            200: inline_serializer(
                name="DeleteDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class DeleteDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = DeleteDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.delete,
            validated_data=serializer.validated_data,
            operation_label="document delete",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_reprocess",
        description="Reprocess selected documents",
        responses={
            200: inline_serializer(
                name="ReprocessDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class ReprocessDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = ReprocessDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.reprocess,
            validated_data=serializer.validated_data,
            operation_label="document reprocess",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_edit_pdf",
        description="Perform PDF edit operations on a selected document",
        responses={
            200: inline_serializer(
                name="EditPdfDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class EditPdfDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = EditPdfDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.edit_pdf,
            validated_data=serializer.validated_data,
            operation_label="PDF edit",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_remove_password",
        description="Remove password protection from selected PDFs",
        responses={
            200: inline_serializer(
                name="RemovePasswordDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class RemovePasswordDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = RemovePasswordDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.remove_password,
            validated_data=serializer.validated_data,
            operation_label="password removal",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_download",
        description="Download multiple documents as a ZIP archive.",
        responses={
            (HTTPStatus.OK, "application/zip"): OpenApiTypes.BINARY,
            HTTPStatus.FORBIDDEN: None,
        },
    ),
)
class BulkDownloadView(DocumentSelectionMixin, GenericAPIView[Any]):
    permission_classes = (IsAuthenticated, ViewDocumentsPermissions)
    serializer_class = BulkDownloadSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = self._resolve_document_ids(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        documents = Document.objects.filter(pk__in=ids)
        versioned_documents = []
        compression = serializer.validated_data.get("compression")
        content = serializer.validated_data.get("content")
        follow_filename_format = serializer.validated_data.get("follow_formatting")

        permitted_ids = set(permitted_document_ids(request.user))
        for document in documents:
            root_doc = get_root_document(document)
            if root_doc.pk not in permitted_ids:
                return HttpResponseForbidden("Insufficient permissions")
            versioned_documents.append(
                get_latest_version_for_root(
                    root_doc,
                ),
            )

        if content == "both":
            strategy_class = OriginalAndArchiveStrategy
        elif content == "originals":
            strategy_class = OriginalsOnlyStrategy
        else:
            strategy_class = ArchiveOnlyStrategy

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=settings.SCRATCH_DIR,
            suffix="-compressed-archive",
        )
        os.close(fd)
        temp_path = Path(temp_name)

        try:
            with zipfile.ZipFile(temp_path, "w", compression) as zipf:
                strategy = strategy_class(
                    zipf,
                    follow_formatting=follow_filename_format,
                )
                for document in versioned_documents:
                    strategy.add_document(document)

            f = temp_path.open("rb")
            temp_path.unlink()
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        return FileResponse(
            f,
            as_attachment=True,
            filename="documents.zip",
            content_type="application/zip",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_edit_objects",
        description="Perform a bulk edit operation on a list of objects",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#objects",
        },
        responses={
            200: inline_serializer(
                name="BulkEditResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class BulkEditObjectsView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = BulkEditObjectsSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.request.user
        object_type = serializer.validated_data.get("object_type")
        object_ids = serializer.validated_data.get("objects")
        apply_to_all = serializer.validated_data.get("all")
        object_class = serializer.get_object_class(object_type)
        operation = serializer.validated_data.get("operation")
        model_name = object_class._meta.model_name
        perm_codename = (
            f"change_{model_name}"
            if operation == "set_permissions"
            else f"delete_{model_name}"
        )

        if apply_to_all:
            # Support all to avoid sending large lists of ids for bulk operations, with optional filters
            filters = serializer.validated_data.get("filters") or {}
            filterset_class = {
                "tags": TagFilterSet,
                "correspondents": CorrespondentFilterSet,
                "document_types": DocumentTypeFilterSet,
                "storage_paths": StoragePathFilterSet,
            }[object_type]
            user_permitted_objects = object_class.objects.filter(
                id__in=permitted_object_ids(user, object_class, perm_codename),
            )
            objs = filterset_class(
                data=filters,
                queryset=user_permitted_objects,
            ).qs
            if object_type == "tags":
                editable_ids = set(user_permitted_objects.values_list("pk", flat=True))
                all_ids = set(objs.values_list("pk", flat=True))
                for tag in objs:
                    all_ids.update(
                        descendant.pk
                        for descendant in tag.get_descendants()
                        if descendant.pk in editable_ids
                    )
                objs = object_class.objects.filter(pk__in=all_ids)
            objs = objs.select_related("owner")
            object_ids = list(objs.values_list("pk", flat=True))
        else:
            objs = object_class.objects.select_related("owner").filter(
                pk__in=object_ids,
            )

        if not user.is_superuser:
            perm = f"documents.{perm_codename}"
            # Limited to the owner (or unowned), same as documents, see BulkEditView
            has_perms = (
                user.has_perm(perm)
                and not objs.exclude(
                    Q(owner=user) | Q(owner__isnull=True),
                ).exists()
            )

            if not has_perms:
                return HttpResponseForbidden("Insufficient permissions")

        if operation == "set_permissions":
            permissions = serializer.validated_data.get("permissions")
            owner = serializer.validated_data.get("owner")
            merge = serializer.validated_data.get("merge")

            try:
                qs = object_class.objects.filter(id__in=object_ids)

                # if merge is true, we dont want to remove the owner
                if "owner" in serializer.validated_data and (
                    not merge or (merge and owner is not None)
                ):
                    # if merge is true, we dont want to overwrite the owner
                    qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                    qs_owner_update.update(owner=owner)

                if "permissions" in serializer.validated_data:
                    set_permissions_for_objects(
                        permissions=permissions,
                        model=object_class,
                        pks=qs.values_list("pk", flat=True),
                        merge=merge,
                    )

            except Exception as e:
                logger.warning(
                    f"An error occurred performing bulk permissions edit: {e!s}",
                )
                return HttpResponseBadRequest(
                    "Error performing bulk permissions edit, check logs for more detail.",
                )

        elif operation == "delete":
            objs.delete()

        return Response({"result": "OK"})
