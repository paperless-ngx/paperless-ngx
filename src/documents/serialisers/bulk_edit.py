from __future__ import annotations

import logging

from django.contrib.auth.models import User
from rest_framework import serializers

from documents import bulk_edit
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag

from .base import DocumentListSerializer
from .base import DocumentSelectionSerializer
from .base import SerializerWithPerms
from .base import SetPermissionsMixin
from .base import SetPermissionsSerializer
from .base import SourceModeValidationMixin
from .metadata import CustomFieldInstanceSerializer

logger = logging.getLogger("paperless.serializers")


def _validate_rotation_degrees(degrees: int, field: str = "degrees") -> int:
    # QPDF refuses any other angle, which would otherwise fail inside the task
    if degrees % 90 != 0:
        raise serializers.ValidationError(f"{field} must be a multiple of 90")
    return degrees


class RotateDocumentsSerializer(DocumentSelectionSerializer, SourceModeValidationMixin):
    degrees = serializers.IntegerField(required=True)
    source_mode = serializers.CharField(
        required=False,
        default=bulk_edit.SourceModeChoices.LATEST_VERSION,
    )
    from_webui = serializers.BooleanField(required=False, default=False)

    def validate_degrees(self, value: int) -> int:
        return _validate_rotation_degrees(value)


class MergeDocumentsSerializer(DocumentListSerializer, SourceModeValidationMixin):
    metadata_document_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    delete_originals = serializers.BooleanField(required=False, default=False)
    archive_fallback = serializers.BooleanField(required=False, default=False)
    source_mode = serializers.CharField(
        required=False,
        default=bulk_edit.SourceModeChoices.LATEST_VERSION,
    )
    from_webui = serializers.BooleanField(required=False, default=False)


class MergeDocumentsAsVersionsSerializer(DocumentListSerializer):
    root_document_id = serializers.IntegerField(required=True)
    version_label = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )

    def validate_version_label(self, value):
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def validate(self, attrs):
        documents = attrs["documents"]
        if len(documents) < 2:
            raise serializers.ValidationError(
                "At least two documents are required.",
            )
        if attrs.get("version_label") is not None and len(documents) != 2:
            raise serializers.ValidationError(
                "version_label can only be used when merging one source document.",
            )
        if attrs["root_document_id"] not in documents:
            raise serializers.ValidationError(
                "root_document_id must be one of the selected documents.",
            )

        selected_documents = Document.objects.filter(id__in=documents)
        if selected_documents.filter(root_document__isnull=False).exists():
            raise serializers.ValidationError(
                "Only top-level documents can be merged as versions.",
            )

        source_document_ids = set(documents) - {attrs["root_document_id"]}
        if Document.global_objects.filter(
            root_document_id__in=source_document_ids,
        ).exists():
            raise serializers.ValidationError(
                "Documents with existing versions cannot be merged into another document.",
            )
        return attrs


class PdfEditOperationSerializer(serializers.Serializer[dict[str, int]]):
    page = serializers.IntegerField(min_value=1)
    rotate = serializers.IntegerField(required=False)
    doc = serializers.IntegerField(required=False, min_value=0)

    def validate_rotate(self, value: int) -> int:
        return _validate_rotation_degrees(value, field="rotate")


class EditPdfDocumentsSerializer(DocumentListSerializer, SourceModeValidationMixin):
    operations = serializers.ListField(
        child=PdfEditOperationSerializer(),
        required=True,
        allow_empty=False,
    )
    delete_original = serializers.BooleanField(required=False, default=False)
    update_document = serializers.BooleanField(required=False, default=False)
    include_metadata = serializers.BooleanField(required=False, default=True)
    source_mode = serializers.CharField(
        required=False,
        default=bulk_edit.SourceModeChoices.LATEST_VERSION,
    )
    from_webui = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        documents = attrs["documents"]
        if len(documents) > 1:
            raise serializers.ValidationError(
                "Edit PDF method only supports one document",
            )

        operations = attrs["operations"]

        if any(op.get("doc", 0) >= len(operations) for op in operations):
            raise serializers.ValidationError("doc index is out of bounds")

        if attrs["update_document"]:
            max_idx = max(op.get("doc", 0) for op in operations)
            if max_idx > 0:
                raise serializers.ValidationError(
                    "update_document only allowed with a single output document",
                )

        doc = Document.objects.get(id=documents[0])
        if doc.page_count:
            for op in operations:
                if op["page"] > doc.page_count:
                    raise serializers.ValidationError(
                        f"Page {op['page']} is out of bounds for document with {doc.page_count} pages.",
                    )
        return attrs


class RemovePasswordDocumentsSerializer(
    DocumentListSerializer,
    SourceModeValidationMixin,
):
    password = serializers.CharField(required=True)
    update_document = serializers.BooleanField(required=False, default=False)
    delete_original = serializers.BooleanField(required=False, default=False)
    include_metadata = serializers.BooleanField(required=False, default=True)
    source_mode = serializers.CharField(
        required=False,
        default=bulk_edit.SourceModeChoices.LATEST_VERSION,
    )
    from_webui = serializers.BooleanField(required=False, default=False)


class DeleteDocumentsSerializer(DocumentSelectionSerializer):
    pass


class ReprocessDocumentsSerializer(DocumentSelectionSerializer):
    remote_ocr = serializers.BooleanField(required=False, default=False)


class BulkEditSerializer(
    SerializerWithPerms,
    DocumentSelectionSerializer,
    SetPermissionsMixin,
    SourceModeValidationMixin,
):
    # TODO: remove this and related backwards compatibility code when API v9 is dropped
    # split, delete_pages can be removed entirely
    MOVED_DOCUMENT_ACTION_ENDPOINTS = {
        "delete": "/api/documents/delete/",
        "reprocess": "/api/documents/reprocess/",
        "rotate": "/api/documents/rotate/",
        "merge": "/api/documents/merge/",
        "edit_pdf": "/api/documents/edit_pdf/",
        "remove_password": "/api/documents/remove_password/",
        "split": "/api/documents/edit_pdf/",
        "delete_pages": "/api/documents/edit_pdf/",
    }
    LEGACY_DOCUMENT_ACTION_METHODS = tuple(MOVED_DOCUMENT_ACTION_ENDPOINTS.keys())

    method = serializers.ChoiceField(
        choices=[
            "set_correspondent",
            "set_document_type",
            "set_storage_path",
            "add_tag",
            "remove_tag",
            "modify_tags",
            "modify_custom_fields",
            "set_permissions",
            *LEGACY_DOCUMENT_ACTION_METHODS,
        ],
        label="Method",
        write_only=True,
    )

    parameters = serializers.DictField(allow_empty=True, default={}, write_only=True)
    from_webui = serializers.BooleanField(required=False, default=False)

    def _validate_tag_id_list(self, tags, name="tags") -> None:
        if not isinstance(tags, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in tags):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = Tag.objects.filter(id__in=tags).count()
        if not count == len(tags):
            raise serializers.ValidationError(
                f"Some tags in {name} don't exist or were specified twice.",
            )

    def _validate_custom_field_id_list_or_dict(
        self,
        custom_fields,
        name="custom_fields",
    ) -> None:
        ids = custom_fields
        if isinstance(custom_fields, dict):
            try:
                ids = [int(i[0]) for i in custom_fields.items()]
            except Exception as e:
                logger.exception(f"Error validating custom fields: {e}")
                raise serializers.ValidationError(
                    f"{name} must be a list of integers or a dict of id:value pairs, see the log for details",
                )
        elif not isinstance(custom_fields, list) or not all(
            isinstance(i, int) for i in ids
        ):
            raise serializers.ValidationError(
                f"{name} must be a list of integers or a dict of id:value pairs",
            )
        count = CustomField.objects.filter(id__in=ids).count()
        if not count == len(ids):
            raise serializers.ValidationError(
                f"Some custom fields in {name} don't exist or were specified twice.",
            )

    def _validate_custom_field_values(self, custom_fields, name):
        if not isinstance(custom_fields, dict):
            return custom_fields

        validated = {}
        errors = {}
        for raw_field_id, value in custom_fields.items():
            field_id = int(raw_field_id)
            validator = CustomFieldInstanceSerializer(
                data={"field": field_id, "value": value},
                context=self.context,
            )
            if validator.is_valid():
                validated[field_id] = validator.validated_data["value"]
            else:
                errors[str(field_id)] = validator.errors

        if errors:
            raise serializers.ValidationError({name: errors})

        return validated

    def validate_method(self, method):
        if method == "set_correspondent":
            return bulk_edit.set_correspondent
        elif method == "set_document_type":
            return bulk_edit.set_document_type
        elif method == "set_storage_path":
            return bulk_edit.set_storage_path
        elif method == "add_tag":
            return bulk_edit.add_tag
        elif method == "remove_tag":
            return bulk_edit.remove_tag
        elif method == "modify_tags":
            return bulk_edit.modify_tags
        elif method == "modify_custom_fields":
            return bulk_edit.modify_custom_fields
        elif method == "delete":
            return bulk_edit.delete
        elif method == "redo_ocr" or method == "reprocess":
            return bulk_edit.reprocess
        elif method == "set_permissions":
            return bulk_edit.set_permissions
        elif method == "rotate":
            return bulk_edit.rotate
        elif method == "merge":
            return bulk_edit.merge
        elif method == "split":
            return bulk_edit.split
        elif method == "delete_pages":
            return bulk_edit.delete_pages
        elif method == "edit_pdf":
            return bulk_edit.edit_pdf
        elif method == "remove_password":
            return bulk_edit.remove_password
        else:
            raise serializers.ValidationError("Unsupported method.")

    def _validate_parameters_tags(self, parameters) -> None:
        if "tag" in parameters:
            tag_id = parameters["tag"]
            try:
                Tag.objects.get(id=tag_id)
            except Tag.DoesNotExist:
                raise serializers.ValidationError("Tag does not exist")
        else:
            raise serializers.ValidationError("tag not specified")

    def _validate_parameters_document_type(self, parameters) -> None:
        if "document_type" in parameters:
            document_type_id = parameters["document_type"]
            if document_type_id is None:
                # None is ok
                return
            try:
                DocumentType.objects.get(id=document_type_id)
            except DocumentType.DoesNotExist:
                raise serializers.ValidationError("Document type does not exist")
        else:
            raise serializers.ValidationError("document_type not specified")

    def _validate_parameters_correspondent(self, parameters) -> None:
        if "correspondent" in parameters:
            correspondent_id = parameters["correspondent"]
            if correspondent_id is None:
                return
            try:
                Correspondent.objects.get(id=correspondent_id)
            except Correspondent.DoesNotExist:
                raise serializers.ValidationError("Correspondent does not exist")
        else:
            raise serializers.ValidationError("correspondent not specified")

    def _validate_storage_path(self, parameters) -> None:
        if "storage_path" in parameters:
            storage_path_id = parameters["storage_path"]
            if storage_path_id is None:
                return
            try:
                StoragePath.objects.get(id=storage_path_id)
            except StoragePath.DoesNotExist:
                raise serializers.ValidationError(
                    "Storage path does not exist",
                )
        else:
            raise serializers.ValidationError("storage path not specified")

    def _validate_parameters_modify_tags(self, parameters) -> None:
        if "add_tags" in parameters:
            self._validate_tag_id_list(parameters["add_tags"], "add_tags")
        else:
            raise serializers.ValidationError("add_tags not specified")

        if "remove_tags" in parameters:
            self._validate_tag_id_list(parameters["remove_tags"], "remove_tags")
        else:
            raise serializers.ValidationError("remove_tags not specified")

    def _validate_parameters_modify_custom_fields(self, parameters) -> None:
        if "add_custom_fields" in parameters:
            self._validate_custom_field_id_list_or_dict(
                parameters["add_custom_fields"],
                "add_custom_fields",
            )
            parameters["add_custom_fields"] = self._validate_custom_field_values(
                parameters["add_custom_fields"],
                "add_custom_fields",
            )
        else:
            raise serializers.ValidationError("add_custom_fields not specified")

        if "remove_custom_fields" in parameters:
            self._validate_custom_field_id_list_or_dict(
                parameters["remove_custom_fields"],
                "remove_custom_fields",
            )
        else:
            raise serializers.ValidationError("remove_custom_fields not specified")

    def _validate_owner(self, owner) -> User:
        owner_field = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
        try:
            return owner_field.run_validation(owner)
        except serializers.ValidationError as e:
            raise serializers.ValidationError(
                "Specified owner cannot be found",
            ) from e

    def _validate_parameters_set_permissions(self, parameters) -> None:
        if "set_permissions" not in parameters:
            raise serializers.ValidationError("set_permissions not specified")
        set_permissions = parameters["set_permissions"]
        if set_permissions is not None:
            set_permissions = SetPermissionsSerializer().run_validation(
                set_permissions,
            )
        parameters["set_permissions"] = self.validate_set_permissions(
            set_permissions,
        )
        if "owner" in parameters and parameters["owner"] is not None:
            parameters["owner"] = self._validate_owner(parameters["owner"]).pk
        if "merge" not in parameters:
            parameters["merge"] = False

    def _validate_parameters_rotate(self, parameters) -> None:
        if "degrees" not in parameters:
            raise serializers.ValidationError("invalid rotation degrees")
        try:
            degrees = serializers.IntegerField().run_validation(parameters["degrees"])
        except serializers.ValidationError as e:
            raise serializers.ValidationError("invalid rotation degrees") from e
        parameters["degrees"] = _validate_rotation_degrees(degrees)

    def _validate_source_mode(self, parameters) -> None:
        source_mode = parameters.get(
            "source_mode",
            bulk_edit.SourceModeChoices.LATEST_VERSION,
        )
        parameters["source_mode"] = self.validate_source_mode(source_mode)

    def _validate_parameters_split(self, parameters, document_id) -> None:
        if "pages" not in parameters:
            raise serializers.ValidationError("pages not specified")
        if not isinstance(parameters["pages"], str):
            raise serializers.ValidationError("invalid pages specified")
        page_count = Document.objects.get(id=document_id).page_count
        if not page_count:
            raise serializers.ValidationError("document page count is unknown")
        pages = []
        for group in parameters["pages"].split(","):
            start, is_range, end = group.partition("-")
            try:
                first = int(start)
                last = int(end) if is_range else first
            except ValueError as e:
                raise serializers.ValidationError("invalid pages specified") from e
            # Bound the range before building it, a huge one would exhaust memory
            if not 1 <= first <= last <= page_count:
                raise serializers.ValidationError("invalid pages specified")
            pages.append(list(range(first, last + 1)))
        parameters["pages"] = pages

        if "delete_originals" in parameters:
            if not isinstance(parameters["delete_originals"], bool):
                raise serializers.ValidationError("delete_originals must be a boolean")
        else:
            parameters["delete_originals"] = False

    def _validate_parameters_delete_pages(self, parameters) -> None:
        if "pages" not in parameters:
            raise serializers.ValidationError("pages not specified")
        if not isinstance(parameters["pages"], list):
            raise serializers.ValidationError("pages must be a list")
        if not all(isinstance(i, int) for i in parameters["pages"]):
            raise serializers.ValidationError("pages must be a list of integers")

    def _validate_parameters_merge(self, parameters) -> None:
        if "delete_originals" in parameters:
            if not isinstance(parameters["delete_originals"], bool):
                raise serializers.ValidationError("delete_originals must be a boolean")
        else:
            parameters["delete_originals"] = False
        if "archive_fallback" in parameters:
            if not isinstance(parameters["archive_fallback"], bool):
                raise serializers.ValidationError("archive_fallback must be a boolean")
        else:
            parameters["archive_fallback"] = False

    def _validate_parameters_edit_pdf(self, parameters, document_id) -> None:
        if "operations" not in parameters:
            raise serializers.ValidationError("operations not specified")
        operations_field = serializers.ListField(
            child=PdfEditOperationSerializer(),
            allow_empty=False,
        )
        try:
            operations = operations_field.run_validation(parameters["operations"])
        except serializers.ValidationError as e:
            # Key the errors under "operations" so they match what the
            # dedicated edit_pdf endpoint returns
            raise serializers.ValidationError({"operations": e.detail}) from e
        parameters["operations"] = operations

        if "update_document" in parameters:
            if not isinstance(parameters["update_document"], bool):
                raise serializers.ValidationError("update_document must be a boolean")
        else:
            parameters["update_document"] = False
        if "include_metadata" in parameters:
            if not isinstance(parameters["include_metadata"], bool):
                raise serializers.ValidationError("include_metadata must be a boolean")
        else:
            parameters["include_metadata"] = True

        if any(op.get("doc", 0) >= len(operations) for op in operations):
            raise serializers.ValidationError("doc index is out of bounds")

        if parameters["update_document"]:
            max_idx = max(op.get("doc", 0) for op in operations)
            if max_idx > 0:
                raise serializers.ValidationError(
                    "update_document only allowed with a single output document",
                )

        doc = Document.objects.get(id=document_id)
        # doc existence is already validated
        if doc.page_count:
            for op in operations:
                if op["page"] > doc.page_count:
                    raise serializers.ValidationError(
                        f"Page {op['page']} is out of bounds for document with {doc.page_count} pages.",
                    )

    def _validate_parameters_reprocess(self, parameters) -> None:
        if "remote_ocr" in parameters:
            if not isinstance(parameters["remote_ocr"], bool):
                raise serializers.ValidationError("remote_ocr must be a boolean")
        else:
            parameters["remote_ocr"] = False

    def validate_parameters_remove_password(self, parameters):
        if "password" not in parameters:
            raise serializers.ValidationError("password not specified")
        if not isinstance(parameters["password"], str):
            raise serializers.ValidationError("password must be a string")

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs.get("all", False) and attrs["method"] in [
            bulk_edit.merge,
            bulk_edit.split,
            bulk_edit.delete_pages,
            bulk_edit.edit_pdf,
            bulk_edit.remove_password,
        ]:
            raise serializers.ValidationError(
                "This method does not support all=true.",
            )

        method = attrs["method"]
        parameters = attrs["parameters"]

        if "source_mode" in parameters:
            self._validate_source_mode(parameters)

        if method == bulk_edit.set_correspondent:
            self._validate_parameters_correspondent(parameters)
        elif method == bulk_edit.set_document_type:
            self._validate_parameters_document_type(parameters)
        elif method == bulk_edit.add_tag or method == bulk_edit.remove_tag:
            self._validate_parameters_tags(parameters)
        elif method == bulk_edit.modify_tags:
            self._validate_parameters_modify_tags(parameters)
        elif method == bulk_edit.set_storage_path:
            self._validate_storage_path(parameters)
        elif method == bulk_edit.modify_custom_fields:
            self._validate_parameters_modify_custom_fields(parameters)
        elif method == bulk_edit.set_permissions:
            self._validate_parameters_set_permissions(parameters)
        elif method == bulk_edit.rotate:
            self._validate_parameters_rotate(parameters)
        elif method == bulk_edit.split:
            if len(attrs["documents"]) > 1:
                raise serializers.ValidationError(
                    "Split method only supports one document",
                )
            self._validate_parameters_split(parameters, attrs["documents"][0])
        elif method == bulk_edit.delete_pages:
            if len(attrs["documents"]) > 1:
                raise serializers.ValidationError(
                    "Delete pages method only supports one document",
                )
            self._validate_parameters_delete_pages(parameters)
        elif method == bulk_edit.merge:
            self._validate_parameters_merge(parameters)
        elif method == bulk_edit.edit_pdf:
            if len(attrs["documents"]) > 1:
                raise serializers.ValidationError(
                    "Edit PDF method only supports one document",
                )
            self._validate_parameters_edit_pdf(parameters, attrs["documents"][0])
        elif method == bulk_edit.remove_password:
            self.validate_parameters_remove_password(parameters)
        elif method == bulk_edit.reprocess:
            self._validate_parameters_reprocess(parameters)

        return attrs


class BulkDownloadSerializer(DocumentSelectionSerializer):
    content = serializers.ChoiceField(
        choices=["archive", "originals", "both"],
        default="archive",
    )

    compression = serializers.ChoiceField(
        choices=["none", "deflated", "bzip2", "lzma"],
        default="none",
    )

    follow_formatting = serializers.BooleanField(
        default=False,
    )

    def validate_compression(self, compression):
        import zipfile

        return {
            "none": zipfile.ZIP_STORED,
            "deflated": zipfile.ZIP_DEFLATED,
            "bzip2": zipfile.ZIP_BZIP2,
            "lzma": zipfile.ZIP_LZMA,
        }[compression]


class BulkEditObjectsSerializer(SerializerWithPerms, SetPermissionsMixin):
    objects = serializers.ListField(
        required=False,
        allow_empty=True,
        label="Objects",
        write_only=True,
        child=serializers.IntegerField(),
    )

    all = serializers.BooleanField(
        default=False,
        required=False,
        write_only=True,
    )

    filters = serializers.DictField(
        required=False,
        allow_empty=True,
        write_only=True,
    )

    object_type = serializers.ChoiceField(
        choices=[
            "tags",
            "correspondents",
            "document_types",
            "storage_paths",
        ],
        label="Object Type",
        write_only=True,
    )

    operation = serializers.ChoiceField(
        choices=[
            "set_permissions",
            "delete",
        ],
        label="Operation",
        required=True,
        write_only=True,
    )

    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    permissions = SetPermissionsSerializer(
        label="Set permissions",
        required=False,
        write_only=True,
    )

    merge = serializers.BooleanField(
        default=False,
        write_only=True,
        required=False,
    )

    def get_object_class(self, object_type):
        object_class = None
        if object_type == "tags":
            object_class = Tag
        elif object_type == "correspondents":
            object_class = Correspondent
        elif object_type == "document_types":
            object_class = DocumentType
        elif object_type == "storage_paths":
            object_class = StoragePath
        return object_class

    def _validate_objects(self, objects, object_type):
        if not isinstance(objects, list):
            raise serializers.ValidationError("objects must be a list")
        if not all(isinstance(i, int) for i in objects):
            raise serializers.ValidationError("objects must be a list of integers")
        object_class = self.get_object_class(object_type)
        count = object_class.objects.filter(id__in=objects).count()
        if not count == len(objects):
            raise serializers.ValidationError(
                "Some ids in objects don't exist or were specified twice.",
            )
        return objects

    def _validate_permissions(self, permissions) -> dict:
        return self.validate_set_permissions(
            permissions,
        )

    def validate(self, attrs):
        object_type = attrs["object_type"]
        objects = attrs.get("objects")
        apply_to_all = attrs.get("all", False)
        operation = attrs.get("operation")

        if apply_to_all:
            attrs.setdefault("objects", [])
        else:
            if objects is None:
                raise serializers.ValidationError(
                    "objects is required unless all is true.",
                )
            if len(objects) == 0:
                raise serializers.ValidationError("objects must not be empty")
            self._validate_objects(objects, object_type)

        if operation == "set_permissions":
            permissions = attrs.get("permissions")
            if permissions is not None:
                if not permissions:
                    raise serializers.ValidationError(
                        "permissions must not be empty",
                    )
                attrs["permissions"] = self._validate_permissions(permissions)

        return attrs
