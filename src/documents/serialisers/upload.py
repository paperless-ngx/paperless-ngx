from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import magic
from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import serializers

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.parsers import is_mime_type_supported

from .metadata import CustomFieldInstanceSerializer

logger = logging.getLogger("paperless.serializers")


class PostDocumentSerializer(serializers.Serializer[dict[str, Any]]):
    created = serializers.DateTimeField(
        label="Created",
        allow_null=True,
        write_only=True,
        required=False,
    )

    document = serializers.FileField(
        label="Document",
        write_only=True,
    )

    title = serializers.CharField(
        label="Title",
        write_only=True,
        required=False,
    )

    correspondent = serializers.PrimaryKeyRelatedField(
        queryset=Correspondent.objects.all(),
        label="Correspondent",
        allow_null=True,
        write_only=True,
        required=False,
    )

    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        label="Document type",
        allow_null=True,
        write_only=True,
        required=False,
    )

    storage_path = serializers.PrimaryKeyRelatedField(
        queryset=StoragePath.objects.all(),
        label="Storage path",
        allow_null=True,
        write_only=True,
        required=False,
    )

    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        label="Tags",
        write_only=True,
        required=False,
    )

    archive_serial_number = serializers.IntegerField(
        label="ASN",
        write_only=True,
        required=False,
        min_value=Document.ARCHIVE_SERIAL_NUMBER_MIN,
        max_value=Document.ARCHIVE_SERIAL_NUMBER_MAX,
    )

    # Accept either a list of custom field ids or a dict mapping id -> value
    custom_fields = serializers.JSONField(
        label="Custom fields",
        write_only=True,
        required=False,
    )

    from_webui = serializers.BooleanField(
        label="Documents are from Paperless-ngx WebUI",
        write_only=True,
        required=False,
    )

    def validate_document(self, document):
        document_data = document.file.read()
        mime_type = magic.from_buffer(document_data, mime=True)

        if not is_mime_type_supported(mime_type):
            if (
                mime_type in settings.CONSUMER_PDF_RECOVERABLE_MIME_TYPES
                and document.name.endswith(
                    ".pdf",
                )
            ):
                # If the file is an invalid PDF, we can try to recover it later in the consumer
                mime_type = "application/pdf"
            else:
                raise serializers.ValidationError(
                    _("File type %(type)s not supported") % {"type": mime_type},
                )

        return document.name, document_data

    def validate_correspondent(self, correspondent):
        if correspondent:
            return correspondent.id
        else:
            return None

    def validate_document_type(self, document_type):
        if document_type:
            return document_type.id
        else:
            return None

    def validate_storage_path(self, storage_path):
        if storage_path:
            return storage_path.id
        else:
            return None

    def validate_tags(self, tags):
        if tags:
            return [tag.id for tag in tags]
        else:
            return None

    def validate_custom_fields(self, custom_fields):
        if not custom_fields:
            return None

        # Normalize single values to a list
        if isinstance(custom_fields, int):
            custom_fields = [custom_fields]
        if isinstance(custom_fields, dict):
            custom_field_serializer = CustomFieldInstanceSerializer()
            normalized = {}
            for field_id, value in custom_fields.items():
                try:
                    field_id_int = int(field_id)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        _("Custom field id must be an integer: %(id)s")
                        % {"id": field_id},
                    )
                try:
                    field = CustomField.objects.get(id=field_id_int)
                except CustomField.DoesNotExist:
                    raise serializers.ValidationError(
                        _("Custom field with id %(id)s does not exist")
                        % {"id": field_id_int},
                    )
                custom_field_serializer.validate(
                    {
                        "field": field,
                        "value": value,
                    },
                )
                normalized[field_id_int] = value
            return normalized
        elif isinstance(custom_fields, list):
            try:
                ids = [int(i) for i in custom_fields]
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    _(
                        "Custom fields must be a list of integers or an object mapping ids to values.",
                    ),
                )
            if CustomField.objects.filter(id__in=ids).count() != len(set(ids)):
                raise serializers.ValidationError(
                    _("Some custom fields don't exist or were specified twice."),
                )
            return ids
        raise serializers.ValidationError(
            _(
                "Custom fields must be a list of integers or an object mapping ids to values.",
            ),
        )

    # custom_fields_w_values handled via validate_custom_fields

    def validate_created(self, created):
        # support datetime format for created for backwards compatibility
        if isinstance(created, datetime):
            return created.date()
