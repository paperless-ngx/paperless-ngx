from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import get_current_timezone
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.utils import extend_schema_serializer
from drf_writable_nested.serializers import NestedUpdateMixin
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

if settings.AUDIT_LOG_ENABLED:
    from auditlog.context import set_actor


from documents import bulk_edit
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Tag
from documents.permissions import permitted_document_ids
from documents.versioning import has_prefetched_effective_content
from documents.versioning import sort_versions_newest_first

from .base import DocumentUpdateFieldsModelSerializer
from .base import NotesSerializer
from .base import OwnedObjectListSerializer
from .base import OwnedObjectSerializer
from .metadata import CorrespondentField
from .metadata import CustomFieldInstanceSerializer
from .metadata import DocumentTypeField
from .metadata import StoragePathField
from .metadata import TagsField
from .upload import PostDocumentSerializer

if TYPE_CHECKING:
    from datetime import datetime

    from django.db.models.query import QuerySet
    from rest_framework.relations import ManyRelatedField
    from rest_framework.relations import RelatedField


logger = logging.getLogger("paperless.serializers")


def _get_viewable_duplicates(
    document: Document,
    user: User | None,
) -> QuerySet[Document]:
    checksums = {document.checksum}
    if document.archive_checksum:
        checksums.add(document.archive_checksum)
    duplicates = Document.global_objects.filter(
        Q(checksum__in=checksums) | Q(archive_checksum__in=checksums),
    ).exclude(pk=document.pk)
    duplicates = duplicates.filter(root_document__isnull=True)
    duplicates = duplicates.order_by("-created")
    allowed_ids = permitted_document_ids(user, include_deleted=True)
    return duplicates.filter(id__in=allowed_ids)


class DuplicateDocumentSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    title = serializers.CharField()
    deleted_at = serializers.DateTimeField(allow_null=True)


class _DocumentVersionInfo(TypedDict):
    id: int
    added: datetime
    version_label: str | None
    checksum: str | None
    is_root: bool


class DocumentVersionInfoSerializer(serializers.Serializer[_DocumentVersionInfo]):
    id = serializers.IntegerField()
    added = serializers.DateTimeField()
    version_label = serializers.CharField(required=False, allow_null=True)
    checksum = serializers.CharField(required=False, allow_null=True)
    is_root = serializers.BooleanField()


@extend_schema_serializer(
    deprecate_fields=["created_date"],
)
class DocumentSerializer(
    OwnedObjectSerializer,
    NestedUpdateMixin,
    DocumentUpdateFieldsModelSerializer,
):
    correspondent = CorrespondentField(allow_null=True)
    tags = TagsField(many=True)
    document_type = DocumentTypeField(allow_null=True)
    storage_path = StoragePathField(allow_null=True)

    original_file_name = SerializerMethodField()
    archived_file_name = SerializerMethodField()
    created_date = serializers.DateField(required=False)
    page_count = SerializerMethodField()
    duplicate_documents = SerializerMethodField()

    notes = NotesSerializer(many=True, required=False, read_only=True)
    root_document: RelatedField[Document, Document, Any] | ManyRelatedField = (
        serializers.PrimaryKeyRelatedField(read_only=True)
    )
    versions = SerializerMethodField()

    custom_fields = CustomFieldInstanceSerializer(
        many=True,
        allow_null=False,
        required=False,
    )

    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    remove_inbox_tags = serializers.BooleanField(
        default=False,
        write_only=True,
        allow_null=True,
        required=False,
    )

    def get_page_count(self, obj) -> int | None:
        return obj.page_count

    @extend_schema_field(DuplicateDocumentSummarySerializer(many=True))
    def get_duplicate_documents(self, obj):
        view = self.context.get("view")
        if view and getattr(view, "action", None) != "retrieve":
            return []
        request = self.context.get("request")
        user = request.user if request else None
        duplicates = _get_viewable_duplicates(obj, user)
        return list(duplicates.values("id", "title", "deleted_at"))

    @extend_schema_field(DocumentVersionInfoSerializer(many=True))
    def get_versions(self, obj):
        root_doc = obj if obj.root_document_id is None else obj.root_document
        if root_doc is None:
            return []

        prefetched_cache = getattr(obj, "_prefetched_objects_cache", None)
        prefetched_versions = (
            prefetched_cache.get("versions")
            if isinstance(prefetched_cache, dict)
            else None
        )

        versions: list[Document]
        if prefetched_versions is not None:
            versions = [*prefetched_versions, root_doc]
        else:
            versions_qs = Document.objects.filter(root_document=root_doc).only(
                "id",
                "added",
                "checksum",
                "version_label",
                "root_document_id",
                "version_index",
            )
            versions = [*versions_qs, root_doc]

        versions = sort_versions_newest_first(versions)

        def build_info(doc: Document) -> _DocumentVersionInfo:
            return {
                "id": doc.id,
                "added": doc.added,
                "version_label": doc.version_label,
                "checksum": doc.checksum,
                "is_root": doc.id == root_doc.id,
            }

        return [build_info(doc) for doc in versions]

    def get_original_file_name(self, obj) -> str | None:
        return obj.original_filename

    def get_archived_file_name(self, obj) -> str | None:
        if obj.has_archive_version:
            return obj.get_public_filename(archive=True)
        else:
            return None

    def to_representation(self, instance):
        doc = super().to_representation(instance)
        if "content" in self.fields and has_prefetched_effective_content(instance):
            # Only resolve version-aware content when it's cheap: an SQL
            # annotation or a versions prefetch is already on the instance.
            # A caller that set up neither (e.g. TrashView, GlobalSearchView,
            # which build their own querysets) gets the document's own,
            # unresolved content instead of paying for an extra per-instance
            # query -- same as before effective_content resolution existed.
            doc["content"] = instance.get_effective_content() or ""
        if self.truncate_content and "content" in self.fields:
            doc["content"] = doc.get("content")[0:550]
        return doc

    def to_internal_value(self, data):
        if (
            "created" in data
            and isinstance(data["created"], str)
            and ":" in data["created"]
        ):
            # Handle old format of isoformat datetime string
            parsed = parse_datetime(data["created"])
            if parsed:
                if is_naive(parsed):
                    parsed = make_aware(parsed, get_current_timezone())
                data["created"] = parsed.astimezone().date()
        return super().to_internal_value(data)

    def validate(self, attrs):
        if (
            "archive_serial_number" in attrs
            and attrs["archive_serial_number"] is not None
            and len(str(attrs["archive_serial_number"])) > 0
            and Document.deleted_objects.filter(
                archive_serial_number=attrs["archive_serial_number"],
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "archive_serial_number": [
                        "Document with this Archive Serial Number already exists in the trash.",
                    ],
                },
            )
        return super().validate(attrs)

    def update(self, instance: Document, validated_data):
        if "created_date" in validated_data:
            if "created" not in validated_data:
                validated_data["created"] = validated_data["created_date"]
            logger.warning(
                "created_date is deprecated, use created instead",
            )
            validated_data.pop("created_date")
        if instance.custom_fields.count() > 0 and "custom_fields" in validated_data:
            incoming_custom_fields = [
                field["field"] for field in validated_data["custom_fields"]
            ]
            for custom_field_instance in instance.custom_fields.filter(
                field__data_type=CustomField.FieldDataType.DOCUMENTLINK,
            ):
                if (
                    custom_field_instance.field not in incoming_custom_fields
                    and custom_field_instance.value is not None
                ):
                    # Doc link field is being removed entirely
                    for doc_id in custom_field_instance.value:
                        bulk_edit.remove_doclink(
                            instance,
                            custom_field_instance.field,
                            doc_id,
                        )
        if "tags" in validated_data:
            # Respect tag hierarchy on updates:
            # - Adding a child adds its ancestors
            # - Removing a parent removes all its descendants
            prev_tags = set(instance.tags.all())
            requested_tags = set(validated_data["tags"])

            # Tags newly added in this update and the ancestors they require
            added_tags = requested_tags - prev_tags
            required_by_add_tags = set(added_tags)
            for t in added_tags:
                required_by_add_tags.update(t.get_ancestors())

            # Tags being removed in this update and all descendants, except
            # those required by a tag that is being added in this same update
            removed_tags = prev_tags - requested_tags
            blocked_tags = set(removed_tags)
            for t in removed_tags:
                blocked_tags.update(t.get_descendants())
            blocked_tags.difference_update(required_by_add_tags)

            # Add all parent tags
            final_tags = set(requested_tags)
            for t in requested_tags:
                final_tags.update(t.get_ancestors())

            # Drop removed parents and their descendants
            final_tags.difference_update(blocked_tags)

            validated_data["tags"] = list(final_tags)
        if validated_data.get("remove_inbox_tags"):
            current_tag_ids = {t.pk for t in instance.tags.all()}
            tags = (
                validated_data["tags"]
                if "tags" in validated_data
                else list(instance.tags.all())
            )

            # Tags newly added in this update, plus their ancestors, are kept
            keep_ids: set[int] = set()
            for tag in tags:
                if tag.pk not in current_tag_ids:
                    keep_ids.add(tag.pk)
                    keep_ids.update(int(pk) for pk in tag.get_ancestors_pks())

            # Remove inbox tags and their descendants, except those being kept
            remove_ids: set[int] = set()
            for inbox_tag in (
                Tag.objects.filter(is_inbox_tag=True)
                .exclude(pk__in=keep_ids)
                .only("pk", "tn_descendants_pks")
            ):
                remove_ids.add(inbox_tag.pk)
                remove_ids.update(int(pk) for pk in inbox_tag.get_descendants_pks())

            validated_data["tags"] = [t for t in tags if t.pk not in remove_ids]

        if settings.AUDIT_LOG_ENABLED:
            with set_actor(self.user):
                super().update(instance, validated_data)
        else:
            super().update(instance, validated_data)

        # hard delete custom field instances that were soft deleted
        CustomFieldInstance.deleted_objects.filter(document=instance).delete()
        return instance

    def __init__(self, *args, **kwargs) -> None:
        self.truncate_content = kwargs.pop("truncate_content", False)

        # return full permissions if we're doing a PATCH or PUT
        context = kwargs.get("context")
        if context is not None and (
            context.get("request").method == "PATCH"
            or context.get("request").method == "PUT"
        ):
            kwargs["full_perms"] = True

        super().__init__(*args, **kwargs)

    class Meta:
        model = Document
        fields = (
            "id",
            "correspondent",
            "document_type",
            "storage_path",
            "title",
            "content",
            "tags",
            "created",
            "created_date",
            "modified",
            "added",
            "deleted_at",
            "archive_serial_number",
            "original_file_name",
            "archived_file_name",
            "duplicate_documents",
            "owner",
            "permissions",
            "user_can_change",
            "is_shared_by_requester",
            "set_permissions",
            "notes",
            "custom_fields",
            "remove_inbox_tags",
            "page_count",
            "mime_type",
            "root_document",
            "versions",
        )
        read_only_fields = ("deleted_at",)
        list_serializer_class = OwnedObjectListSerializer


class SearchResultListSerializer(serializers.ListSerializer[Document]):
    def to_representation(self, hits):
        document_ids = [hit["id"] for hit in hits]
        # Fetch all Document objects in the list in one SQL query.
        documents = self.child.fetch_documents(document_ids)
        self.child.context["documents"] = documents
        # Also check if they are shared with other users / groups.
        self.child.context["shared_object_pks"] = self.child.get_shared_object_pks(
            documents.values(),
        )

        return super().to_representation(hits)


class SearchResultSerializer(DocumentSerializer):
    @staticmethod
    def fetch_documents(ids):
        """
        Return a dict that maps given document IDs to Document objects.
        """
        return {
            document.id: document
            for document in Document.objects.select_related(
                "correspondent",
                "storage_path",
                "document_type",
                "owner",
            )
            .prefetch_related("tags", "custom_fields", "notes")
            .filter(id__in=ids)
        }

    def to_representation(self, hit):
        # Again we first check if the parent has already fetched the documents.
        documents = self.context.get("documents")
        # Otherwise we fetch this document.
        if documents is None:  # pragma: no cover
            # In practice we only serialize **lists** of SearchHit dicts.
            # Keeping this check for completeness but marking it no cover for now.
            documents = self.fetch_documents([hit["id"]])
        document = documents[hit["id"]]

        highlights = hit.get("highlights", {})
        r = super().to_representation(document)
        r["__search_hit__"] = {
            "score": hit["score"],
            "highlights": highlights.get("content", ""),
            "note_highlights": highlights.get("notes") or None,
            "rank": hit["rank"],
        }

        return r

    class Meta(DocumentSerializer.Meta):
        list_serializer_class = SearchResultListSerializer


class DocumentVersionSerializer(serializers.Serializer[dict[str, Any]]):
    document = serializers.FileField(
        label="Document",
        write_only=True,
    )
    version_label = serializers.CharField(
        label="Version label",
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )

    validate_document = PostDocumentSerializer().validate_document


class DocumentVersionLabelSerializer(serializers.Serializer[dict[str, str | None]]):
    version_label = serializers.CharField(
        label="Version label",
        required=True,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )

    def validate_version_label(self, value):
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
