from __future__ import annotations

import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.fields import SerializerMethodField

from documents.models import Document
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.permissions import has_perms_owner_aware

from .base import DocumentListSerializer
from .base import OwnedObjectSerializer

logger = logging.getLogger("paperless.serializers")


class EmailSerializer(DocumentListSerializer):
    addresses = serializers.CharField(
        required=True,
        label="Email addresses",
        help_text="Comma-separated email addresses",
    )

    subject = serializers.CharField(
        required=True,
        label="Email subject",
    )

    message = serializers.CharField(
        required=True,
        label="Email message",
    )

    use_archive_version = serializers.BooleanField(
        default=True,
        label="Use archive version",
        help_text="Use archive version of documents if available",
    )

    def validate_addresses(self, addresses):
        address_list = [addr.strip() for addr in addresses.split(",")]
        if not address_list:
            raise serializers.ValidationError("At least one email address is required")

        email_validator = EmailValidator()
        try:
            for address in address_list:
                email_validator(address)
        except ValidationError:
            raise serializers.ValidationError(f"Invalid email address: {address}")

        return ",".join(address_list)

    def validate_documents(self, documents):
        super().validate_documents(documents)
        if not documents:
            raise serializers.ValidationError("At least one document is required")

        return documents


class ShareLinkSerializer(OwnedObjectSerializer):
    document_title = serializers.CharField(
        source="document.title",
        read_only=True,
    )

    class Meta:
        model = ShareLink
        fields = (
            "id",
            "created",
            "expiration",
            "slug",
            "document",
            "document_title",
            "file_version",
        )

    def create(self, validated_data):
        validated_data["slug"] = get_random_string(50)
        return super().create(validated_data)

    def validate_document(self, document):
        if (
            self.user is not None
            and self.user.has_perm("documents.view_document")
            and has_perms_owner_aware(
                self.user,
                "view_document",
                document,
            )
        ):
            return document
        raise PermissionDenied(
            _("Insufficient permissions."),
        )


class ShareLinkBundleSerializer(OwnedObjectSerializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        write_only=True,
    )
    expiration_days = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        write_only=True,
    )
    documents = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )
    document_count = SerializerMethodField()

    class Meta:
        model = ShareLinkBundle
        fields = (
            "id",
            "created",
            "expiration",
            "expiration_days",
            "slug",
            "file_version",
            "status",
            "size_bytes",
            "last_error",
            "built_at",
            "documents",
            "document_ids",
            "document_count",
        )
        read_only_fields = (
            "id",
            "created",
            "expiration",
            "slug",
            "status",
            "size_bytes",
            "last_error",
            "built_at",
            "documents",
            "document_count",
        )

    def validate_document_ids(self, value):
        unique_ids = set(value)
        if len(unique_ids) != len(value):
            raise serializers.ValidationError(
                _("Duplicate document identifiers are not allowed."),
            )
        return value

    def create(self, validated_data):
        document_ids = validated_data.pop("document_ids")
        expiration_days = validated_data.pop("expiration_days", None)
        validated_data["slug"] = get_random_string(50)
        if expiration_days:
            validated_data["expiration"] = timezone.now() + timedelta(
                days=expiration_days,
            )
        else:
            validated_data["expiration"] = None

        share_link_bundle = super().create(validated_data)

        documents = list(
            Document.objects.filter(pk__in=document_ids).only(
                "pk",
            ),
        )
        documents_by_id = {doc.pk: doc for doc in documents}
        missing = [
            str(doc_id) for doc_id in document_ids if doc_id not in documents_by_id
        ]
        if missing:
            raise serializers.ValidationError(
                {
                    "document_ids": _(
                        "Documents not found: %(ids)s",
                    )
                    % {"ids": ", ".join(missing)},
                },
            )

        ordered_documents = [documents_by_id[doc_id] for doc_id in document_ids]
        share_link_bundle.documents.set(ordered_documents)
        share_link_bundle.document_total = len(ordered_documents)

        return share_link_bundle

    def get_document_count(self, obj: ShareLinkBundle) -> int:
        return getattr(obj, "document_total") or obj.documents.count()
