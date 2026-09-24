from __future__ import annotations

import logging
import math
import re
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.core.validators import MaxLengthValidator
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.core.validators import integer_validator
from django.db.models import Count
from django.db.models.functions import Lower
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter

from documents import bulk_edit
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import PaperlessTask
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import get_document_count_filter_for_user
from documents.permissions import permitted_document_ids
from documents.permissions import restrict_queryset_to_visible
from documents.templating.filepath import validate_filepath_template_and_render
from documents.templating.utils import convert_format_str_to_template_format
from documents.validators import uri_validator

from .base import MatchingModelSerializer
from .base import OwnedObjectSerializer
from .base import ReadWriteSerializerMethodField
from .base import SerializerWithPerms

logger = logging.getLogger("paperless.serializers")


class CorrespondentSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    last_correspondence = serializers.DateField(read_only=True, required=False)

    class Meta:
        model = Correspondent
        fields = (
            "id",
            "slug",
            "name",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
            "last_correspondence",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        )


class DocumentTypeSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    class Meta:
        model = DocumentType
        fields = (
            "id",
            "slug",
            "name",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        )


class DeprecatedColors:
    COLOURS = (
        (1, "#a6cee3"),
        (2, "#1f78b4"),
        (3, "#b2df8a"),
        (4, "#33a02c"),
        (5, "#fb9a99"),
        (6, "#e31a1c"),
        (7, "#fdbf6f"),
        (8, "#ff7f00"),
        (9, "#cab2d6"),
        (10, "#6a3d9a"),
        (11, "#b15928"),
        (12, "#000000"),
        (13, "#cccccc"),
    )


@extend_schema_field(
    serializers.ChoiceField(
        choices=DeprecatedColors.COLOURS,
    ),
)
class ColorField(serializers.Field):
    def to_internal_value(self, data):
        for id, color in DeprecatedColors.COLOURS:
            if id == data:
                return color
        raise serializers.ValidationError

    def to_representation(self, value):
        for id, color in DeprecatedColors.COLOURS:
            if color == value:
                return id
        return 1


class TagSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    def get_text_color(self, obj) -> str:
        try:
            h = obj.color.lstrip("#")
            rgb = tuple(int(h[i : i + 2], 16) / 256 for i in (0, 2, 4))
            luminance = math.sqrt(
                0.299 * math.pow(rgb[0], 2)
                + 0.587 * math.pow(rgb[1], 2)
                + 0.114 * math.pow(rgb[2], 2),
            )
            return "#ffffff" if luminance < 0.53 else "#000000"
        except ValueError:
            return "#000000"

    text_color = serializers.SerializerMethodField()

    # map to treenode's tn_parent
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        allow_null=True,
        required=False,
        source="tn_parent",
    )

    @extend_schema_field(
        field=serializers.ListSerializer(
            child=serializers.PrimaryKeyRelatedField(
                queryset=Tag.objects.all(),
            ),
        ),
    )
    def get_children(self, obj):
        children_map = self.context.get("children_map")
        if children_map is not None:
            children = children_map.get(obj.pk, [])
        else:
            filter_q = self.context.get("document_count_filter")
            request = self.context.get("request")
            if filter_q is None:
                user = getattr(request, "user", None) if request else None
                filter_q = get_document_count_filter_for_user(user)
                self.context["document_count_filter"] = filter_q

            children = (
                obj.get_children_queryset()
                .select_related("owner")
                .annotate(document_count=Count("documents", filter=filter_q))
            )
            user = getattr(request, "user", None) if request else self.user
            children = restrict_queryset_to_visible(children, user, "view_tag")

            view = self.context.get("view")
            ordering = (
                OrderingFilter().get_ordering(request, children, view)
                if request and view
                else None
            )
            ordering = ordering or (Lower("name"),)
            children = children.order_by(*ordering)

        if not children:
            return []

        serializer = TagSerializer(
            children,
            many=True,
            user=self.user,
            full_perms=self.full_perms,
            all_fields=self.all_fields,
            context=self.context,
        )
        return serializer.data

    # children as nested Tag objects
    children = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = (
            "id",
            "slug",
            "name",
            "color",
            "text_color",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "is_inbox_tag",
            "document_count",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
            "parent",
            "children",
        )

    def validate_color(self, color):
        regex = r"#[0-9a-fA-F]{6}"
        if not re.match(regex, color):
            raise serializers.ValidationError(_("Invalid color."))
        return color

    def validate(self, attrs):
        # Validate when changing parent
        parent = attrs.get(
            "tn_parent",
            self.instance.get_parent() if self.instance else None,
        )

        if self.instance:
            # Temporarily set parent on the instance if updating and use model clean()
            original_parent = self.instance.get_parent()
            try:
                # Temporarily set tn_parent in-memory to validate clean()
                self.instance.tn_parent = parent
                self.instance.clean()
            except ValidationError as e:
                logger.debug("Tag parent validation failed: %s", e)
                raise e
            finally:
                self.instance.tn_parent = original_parent
        else:
            # For new instances, create a transient Tag and validate
            temp = Tag(tn_parent=parent)
            try:
                temp.clean()
            except ValidationError as e:
                logger.debug("Tag parent validation failed: %s", e)
                raise e

        return super().validate(attrs)


class CorrespondentField(serializers.PrimaryKeyRelatedField[Correspondent]):
    def get_queryset(self):
        return Correspondent.objects.all()


class TagsField(serializers.PrimaryKeyRelatedField[Tag]):
    def get_queryset(self):
        return Tag.objects.all()


class DocumentTypeField(serializers.PrimaryKeyRelatedField[DocumentType]):
    def get_queryset(self):
        return DocumentType.objects.all()


class StoragePathField(serializers.PrimaryKeyRelatedField[StoragePath]):
    def get_queryset(self):
        return StoragePath.objects.all()


class CustomFieldSerializer(serializers.ModelSerializer[CustomField]):
    data_type = serializers.ChoiceField(
        choices=CustomField.FieldDataType,
        read_only=False,
    )

    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomField
        fields = [
            "id",
            "name",
            "data_type",
            "extra_data",
            "document_count",
        ]

    def validate(self, attrs):
        # TODO: remove pending https://github.com/encode/django-rest-framework/issues/7173
        name = attrs.get(
            "name",
            self.instance.name if hasattr(self.instance, "name") else None,
        )
        objects = (
            self.Meta.model.objects.exclude(
                pk=self.instance.pk,
            )
            if self.instance is not None
            else self.Meta.model.objects.all()
        )
        if ("name" in attrs) and objects.filter(
            name=name,
        ).exists():
            raise serializers.ValidationError(
                {"error": "Object violates name unique constraint"},
            )
        if (
            "data_type" in attrs
            and attrs["data_type"] == CustomField.FieldDataType.SELECT
        ) or (
            self.instance
            and self.instance.data_type == CustomField.FieldDataType.SELECT
        ):
            if (
                "extra_data" not in attrs
                or "select_options" not in attrs["extra_data"]
                or not isinstance(attrs["extra_data"]["select_options"], list)
                or len(attrs["extra_data"]["select_options"]) == 0
                or not all(
                    len(option.get("label", "")) > 0
                    for option in attrs["extra_data"]["select_options"]
                )
            ):
                raise serializers.ValidationError(
                    {"error": "extra_data.select_options must be a valid list"},
                )
            # labels are valid, generate ids if not present
            for option in attrs["extra_data"]["select_options"]:
                if option.get("id") is None:
                    option["id"] = get_random_string(length=16)
        elif (
            "data_type" in attrs
            and attrs["data_type"] == CustomField.FieldDataType.MONETARY
            and "extra_data" in attrs
            and "default_currency" in attrs["extra_data"]
            and attrs["extra_data"]["default_currency"] is not None
            and (
                not isinstance(attrs["extra_data"]["default_currency"], str)
                or (
                    len(attrs["extra_data"]["default_currency"]) > 0
                    and len(attrs["extra_data"]["default_currency"]) != 3
                )
            )
        ):
            raise serializers.ValidationError(
                {"error": "extra_data.default_currency must be a 3-character string"},
            )
        return super().validate(attrs)


def validate_documentlink_targets(user, doc_ids):
    if Document.objects.filter(id__in=doc_ids).count() != len(doc_ids):
        raise serializers.ValidationError(
            "Some documents in value don't exist or were specified twice.",
        )

    if user is None:
        return

    if (
        Document.objects.filter(id__in=doc_ids)
        .exclude(id__in=permitted_document_ids(user, perm="change_document"))
        .exists()
    ):
        raise PermissionDenied(
            _("Insufficient permissions."),
        )


class CustomFieldInstanceSerializer(serializers.ModelSerializer[CustomFieldInstance]):
    field = serializers.PrimaryKeyRelatedField(queryset=CustomField.objects.all())
    value = ReadWriteSerializerMethodField(allow_null=True)

    def create(self, validated_data):
        # An instance is attached to a document
        document: Document = validated_data["document"]
        # And to a CustomField
        custom_field: CustomField = validated_data["field"]
        # This key must exist, as it is validated
        data_store_name = CustomFieldInstance.get_value_field_name(
            custom_field.data_type,
        )

        if custom_field.data_type == CustomField.FieldDataType.DOCUMENTLINK:
            # prior to update so we can look for any docs that are going to be removed
            bulk_edit.reflect_doclinks(document, custom_field, validated_data["value"])

        # Actually update or create the instance, providing the value
        # to fill in the correct attribute based on the type
        instance, _ = CustomFieldInstance.objects.update_or_create(
            document=document,
            field=custom_field,
            defaults={data_store_name: validated_data["value"]},
        )
        return instance

    def get_value(self, obj: CustomFieldInstance) -> str | int | float | dict | None:
        return obj.value

    def validate(self, data):
        """
        Probably because we're kind of doing it odd, validation from the model
        doesn't run against the field "value", so we have to re-create it here.

        Don't like it, but it is better than returning an HTTP 500 when the database
        hates the value
        """
        data = super().validate(data)
        field: CustomField = data["field"]
        if "value" in data and data["value"] is not None:
            if (
                field.data_type == CustomField.FieldDataType.URL
                and len(data["value"]) > 0
            ):
                uri_validator(data["value"])
            elif field.data_type == CustomField.FieldDataType.INT:
                integer_validator(data["value"])
                try:
                    value_int = int(data["value"])
                except (TypeError, ValueError):
                    raise serializers.ValidationError("Enter a valid integer.")
                # Keep values within the PostgreSQL integer range
                MinValueValidator(-2147483648)(value_int)
                MaxValueValidator(2147483647)(value_int)
            elif (
                field.data_type == CustomField.FieldDataType.MONETARY
                and data["value"] != ""
            ):
                try:
                    # First try to validate as a number from legacy format
                    DecimalValidator(max_digits=12, decimal_places=2)(
                        Decimal(str(data["value"])),
                    )
                except Exception:
                    # If that fails, try to validate as a monetary string
                    RegexValidator(
                        regex=r"^[A-Z]{3}-?\d+(\.\d{1,2})$",
                        message="Must be a two-decimal number with optional currency code e.g. GBP123.45",
                    )(data["value"])
            elif field.data_type == CustomField.FieldDataType.STRING:
                MaxLengthValidator(limit_value=128)(data["value"])
            elif field.data_type == CustomField.FieldDataType.SELECT:
                select_options = field.extra_data["select_options"]
                try:
                    next(
                        option
                        for option in select_options
                        if option["id"] == data["value"]
                    )
                except Exception:
                    raise serializers.ValidationError(
                        f"Value must be an id of an element in {select_options}",
                    )
            elif field.data_type == CustomField.FieldDataType.DOCUMENTLINK:
                if not (isinstance(data["value"], list) or data["value"] is None):
                    raise serializers.ValidationError(
                        "Value must be a list",
                    )
                doc_ids = data["value"]
                request = self.context.get("request")
                validate_documentlink_targets(
                    getattr(request, "user", None) if request is not None else None,
                    doc_ids,
                )
            elif field.data_type == CustomField.FieldDataType.DATE:
                data["value"] = serializers.DateField().to_internal_value(data["value"])

        return data

    class Meta:
        model = CustomFieldInstance
        fields = [
            "value",
            "field",
        ]


class StoragePathSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    class Meta:
        model = StoragePath
        fields = (
            "id",
            "slug",
            "name",
            "path",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        )

    def validate_path(self, path: str):
        converted_path = convert_format_str_to_template_format(path)
        if converted_path != path:
            logger.warning(
                f"Storage path {path} is not using the new style format, consider updating",
            )
        result = validate_filepath_template_and_render(converted_path)

        if result is None:
            raise serializers.ValidationError(_("Invalid variable detected."))

        return converted_path

    def update(self, instance, validated_data):
        """
        When a storage path is updated, see if documents
        using it require a rename/move
        """
        doc_ids = [doc.id for doc in instance.documents.all()]
        if doc_ids:
            bulk_edit.bulk_update_documents.apply_async(
                kwargs={"document_ids": doc_ids},
                headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
            )

        return super().update(instance, validated_data)


class StoragePathTestSerializer(SerializerWithPerms):
    path = serializers.CharField(
        required=True,
        label="Path",
        write_only=True,
    )

    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.none(),
        required=True,
        label="Document",
        write_only=True,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user is not None and user.is_authenticated:
            document_field = self.fields.get("document")
            if not isinstance(document_field, serializers.PrimaryKeyRelatedField):
                return
            document_field.queryset = Document.objects.filter(
                id__in=permitted_document_ids(user),
            )
