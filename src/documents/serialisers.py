import datetime
import math
import re
import zoneinfo
from decimal import Decimal

from django.apps import apps
import magic
from celery import states
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.validators import DecimalValidator
from django.core.validators import MaxLengthValidator
from django.core.validators import RegexValidator
from django.core.validators import integer_validator
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext as _
from drf_writable_nested.serializers import NestedUpdateMixin
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import get_users_with_perms
from guardian.utils import get_group_obj_perms_model
from guardian.utils import get_user_obj_perms_model
from rest_framework import fields
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from documents import bulk_edit
from documents.data_models import DocumentSource
from documents.models import Approval, Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.models import Warehouse
from documents.models import Folder
from documents.parsers import is_mime_type_supported
from documents.permissions import get_groups_with_only_permission, has_perms_owner_aware
from documents.permissions import set_permissions_for_object
from documents.validators import uri_validator


# https://www.django-rest-framework.org/api-guide/serializers/#example
class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop("fields", None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class MatchingModelSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)

    def get_slug(self, obj):
        return slugify(obj.name)

    slug = SerializerMethodField()

    def validate(self, data):
        # TODO: remove pending https://github.com/encode/django-rest-framework/issues/7173
        name = data.get(
            "name",
            self.instance.name if hasattr(self.instance, "name") else None,
        )
        owner = (
            data["owner"]
            if "owner" in data
            else self.user if hasattr(self, "user") else None
        )
        pk = self.instance.pk if hasattr(self.instance, "pk") else None
        if ("name" in data or "owner" in data) and self.Meta.model.objects.filter(
            name=name,
            owner=owner,
        ).exclude(pk=pk).exists():
            raise serializers.ValidationError(
                {"error": "Object violates owner / name unique constraint"},
            )
        return data

    def validate_match(self, match):
        if (
            "matching_algorithm" in self.initial_data
            and self.initial_data["matching_algorithm"] == MatchingModel.MATCH_REGEX
        ):
            try:
                re.compile(match)
            except re.error as e:
                raise serializers.ValidationError(
                    _("Invalid regular expression: %(error)s") % {"error": str(e.msg)},
                )
        return match


class SetPermissionsMixin:
    def _validate_user_ids(self, user_ids):
        users = User.objects.none()
        if user_ids is not None:
            users = User.objects.filter(id__in=user_ids)
            if not users.count() == len(user_ids):
                raise serializers.ValidationError(
                    "Some users in don't exist or were specified twice.",
                )
        return users

    def _validate_group_ids(self, group_ids):
        groups = Group.objects.none()
        if group_ids is not None:
            groups = Group.objects.filter(id__in=group_ids)
            if not groups.count() == len(group_ids):
                raise serializers.ValidationError(
                    "Some groups in don't exist or were specified twice.",
                )
        return groups

    def validate_set_permissions(self, set_permissions=None):
        permissions_dict = {
            "view": {
                "users": User.objects.none(),
                "groups": Group.objects.none(),
            },
            "change": {
                "users": User.objects.none(),
                "groups": Group.objects.none(),
            },
        }
        if set_permissions is not None:
            for action in permissions_dict:
                if action in set_permissions:
                    users = set_permissions[action]["users"]
                    permissions_dict[action]["users"] = self._validate_user_ids(users)
                    groups = set_permissions[action]["groups"]
                    permissions_dict[action]["groups"] = self._validate_group_ids(
                        groups,
                    )
        return permissions_dict

    def _set_permissions(self, permissions, object):
        set_permissions_for_object(permissions, object)


class SerializerWithPerms(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.full_perms = kwargs.pop("full_perms", False)
        super().__init__(*args, **kwargs)


class OwnedObjectSerializer(
    SerializerWithPerms,
    serializers.ModelSerializer,
    SetPermissionsMixin,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            if self.full_perms:
                self.fields.pop("user_can_change")
                self.fields.pop("is_shared_by_requester")
            else:
                self.fields.pop("permissions")
        except KeyError:
            pass

    def get_permissions(self, obj):
        view_codename = f"view_{obj.__class__.__name__.lower()}"
        change_codename = f"change_{obj.__class__.__name__.lower()}"

        return {
            "view": {
                "users": get_users_with_perms(
                    obj,
                    only_with_perms_in=[view_codename],
                    with_group_users=False,
                ).values_list("id", flat=True),
                "groups": get_groups_with_only_permission(
                    obj,
                    codename=view_codename,
                ).values_list("id", flat=True),
            },
            "change": {
                "users": get_users_with_perms(
                    obj,
                    only_with_perms_in=[change_codename],
                    with_group_users=False,
                ).values_list("id", flat=True),
                "groups": get_groups_with_only_permission(
                    obj,
                    codename=change_codename,
                ).values_list("id", flat=True),
            },
        }

    def get_user_can_change(self, obj):
        checker = ObjectPermissionChecker(self.user) if self.user is not None else None
        return (
            obj.owner is None
            or obj.owner == self.user
            or (
                self.user is not None
                and checker.has_perm(f"change_{obj.__class__.__name__.lower()}", obj)
            )
        )

    def get_is_shared_by_requester(self, obj: Document):
        ctype = ContentType.objects.get_for_model(obj)
        UserObjectPermission = get_user_obj_perms_model()
        GroupObjectPermission = get_group_obj_perms_model()
        return obj.owner == self.user and (
            UserObjectPermission.objects.filter(
                content_type=ctype,
                object_pk=obj.pk,
            ).count()
            > 0
            or GroupObjectPermission.objects.filter(
                content_type=ctype,
                object_pk=obj.pk,
            ).count()
            > 0
        )

    permissions = SerializerMethodField(read_only=True)
    user_can_change = SerializerMethodField(read_only=True)
    is_shared_by_requester = SerializerMethodField(read_only=True)

    set_permissions = serializers.DictField(
        label="Set permissions",
        allow_empty=True,
        required=False,
        write_only=True,
    )
    # other methods in mixin

    def create(self, validated_data):
        # default to current user if not set
        if "owner" not in validated_data and self.user:
            validated_data["owner"] = self.user
        permissions = None
        if "set_permissions" in validated_data:
            permissions = validated_data.pop("set_permissions")
        instance = super().create(validated_data)
        if permissions is not None:
            self._set_permissions(permissions, instance)
        return instance

    def update(self, instance, validated_data):
        if "set_permissions" in validated_data:
            self._set_permissions(validated_data["set_permissions"], instance)
        if "owner" in validated_data and "name" in self.Meta.fields:
            name = validated_data.get("name", instance.name)
            not_unique = (
                self.Meta.model.objects.exclude(pk=instance.pk)
                .filter(owner=validated_data["owner"], name=name)
                .exists()
            )
            if not_unique:
                raise serializers.ValidationError(
                    {"error": "Object violates owner / name unique constraint"},
                )
        return super().update(instance, validated_data)


class CorrespondentSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    last_correspondence = serializers.DateTimeField(read_only=True)

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


class ColorField(serializers.Field):
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

    def to_internal_value(self, data):
        for id, color in self.COLOURS:
            if id == data:
                return color
        raise serializers.ValidationError

    def to_representation(self, value):
        for id, color in self.COLOURS:
            if color == value:
                return id
        return 1


class TagSerializerVersion1(MatchingModelSerializer, OwnedObjectSerializer):
    colour = ColorField(source="color", default="#a6cee3")

    class Meta:
        model = Tag
        fields = (
            "id",
            "slug",
            "name",
            "colour",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "is_inbox_tag",
            "document_count",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        )


class TagSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    def get_text_color(self, obj):
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
        )

    def validate_color(self, color):
        regex = r"#[0-9a-fA-F]{6}"
        if not re.match(regex, color):
            raise serializers.ValidationError(_("Invalid color."))
        return color


class CorrespondentField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Correspondent.objects.all()
    
class TagsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Tag.objects.all()

class WarehouseField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Warehouse.objects.all()

class FolderField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Folder.objects.all()

class DocumentTypeField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return DocumentType.objects.all()


class StoragePathField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return StoragePath.objects.all()


class CustomFieldSerializer(serializers.ModelSerializer):
    data_type = serializers.ChoiceField(
        choices=CustomField.FieldDataType,
        read_only=False,
    )

    class Meta:
        model = CustomField
        fields = [
            "id",
            "name",
            "data_type",
        ]

    def validate(self, attrs):
        # TODO: remove pending https://github.com/encode/django-rest-framework/issues/7173
        name = attrs.get(
            "name",
            self.instance.name if hasattr(self.instance, "name") else None,
        )
        if ("name" in attrs) and self.Meta.model.objects.filter(
            name=name,
        ).exists():
            raise serializers.ValidationError(
                {"error": "Object violates name unique constraint"},
            )
        return super().validate(attrs)


class ReadWriteSerializerMethodField(serializers.SerializerMethodField):
    """
    Based on https://stackoverflow.com/a/62579804
    """

    def __init__(self, method_name=None, *args, **kwargs):
        self.method_name = method_name
        kwargs["source"] = "*"
        super(serializers.SerializerMethodField, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        return {self.field_name: data}


class CustomFieldInstanceSerializer(serializers.ModelSerializer):
    field = serializers.PrimaryKeyRelatedField(queryset=CustomField.objects.all())
    value = ReadWriteSerializerMethodField(allow_null=True)

    def create(self, validated_data):
        type_to_data_store_name_map = {
            CustomField.FieldDataType.STRING: "value_text",
            CustomField.FieldDataType.URL: "value_url",
            CustomField.FieldDataType.DATE: "value_date",
            CustomField.FieldDataType.BOOL: "value_bool",
            CustomField.FieldDataType.INT: "value_int",
            CustomField.FieldDataType.FLOAT: "value_float",
            CustomField.FieldDataType.MONETARY: "value_monetary",
            CustomField.FieldDataType.DOCUMENTLINK: "value_document_ids",
        }
        # An instance is attached to a document
        document: Document = validated_data["document"]
        # And to a CustomField
        custom_field: CustomField = validated_data["field"]
        # This key must exist, as it is validated
        data_store_name = type_to_data_store_name_map[custom_field.data_type]

        if custom_field.data_type == CustomField.FieldDataType.DOCUMENTLINK:
            # prior to update so we can look for any docs that are going to be removed
            self.reflect_doclinks(document, custom_field, validated_data["value"])

        # Actually update or create the instance, providing the value
        # to fill in the correct attribute based on the type
        instance, _ = CustomFieldInstance.objects.update_or_create(
            document=document,
            field=custom_field,
            defaults={data_store_name: validated_data["value"]},
        )
        return instance

    def get_value(self, obj: CustomFieldInstance):
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
            elif field.data_type == CustomField.FieldDataType.MONETARY:
                try:
                    # First try to validate as a number from legacy format
                    DecimalValidator(max_digits=12, decimal_places=2)(
                        Decimal(str(data["value"])),
                    )
                except Exception:
                    # If that fails, try to validate as a monetary string
                    RegexValidator(
                        regex=r"^[A-Z]{3}-?\d+(\.\d{2,2})$",
                        message="Must be a two-decimal number with optional currency code e.g. GBP123.45",
                    )(data["value"])
            elif field.data_type == CustomField.FieldDataType.STRING:
                MaxLengthValidator(limit_value=128)(data["value"])

        return data

    def reflect_doclinks(
        self,
        document: Document,
        field: CustomField,
        target_doc_ids: list[int],
    ):
        """
        Add or remove 'symmetrical' links to `document` on all `target_doc_ids`
        """

        if target_doc_ids is None:
            target_doc_ids = []

        # Check if any documents are going to be removed from the current list of links and remove the symmetrical links
        current_field_instance = CustomFieldInstance.objects.filter(
            field=field,
            document=document,
        ).first()
        if (
            current_field_instance is not None
            and current_field_instance.value is not None
        ):
            for doc_id in current_field_instance.value:
                if doc_id not in target_doc_ids:
                    self.remove_doclink(document, field, doc_id)

        # Create an instance if target doc doesn't have this field or append it to an existing one
        existing_custom_field_instances = {
            custom_field.document_id: custom_field
            for custom_field in CustomFieldInstance.objects.filter(
                field=field,
                document_id__in=target_doc_ids,
            )
        }
        custom_field_instances_to_create = []
        custom_field_instances_to_update = []
        for target_doc_id in target_doc_ids:
            target_doc_field_instance = existing_custom_field_instances.get(
                target_doc_id,
            )
            if target_doc_field_instance is None:
                custom_field_instances_to_create.append(
                    CustomFieldInstance(
                        document_id=target_doc_id,
                        field=field,
                        value_document_ids=[document.id],
                    ),
                )
            elif target_doc_field_instance.value is None:
                target_doc_field_instance.value_document_ids = [document.id]
                custom_field_instances_to_update.append(target_doc_field_instance)
            elif document.id not in target_doc_field_instance.value:
                target_doc_field_instance.value_document_ids.append(document.id)
                custom_field_instances_to_update.append(target_doc_field_instance)

        CustomFieldInstance.objects.bulk_create(custom_field_instances_to_create)
        CustomFieldInstance.objects.bulk_update(
            custom_field_instances_to_update,
            ["value_document_ids"],
        )
        Document.objects.filter(id__in=target_doc_ids).update(modified=timezone.now())

    @staticmethod
    def remove_doclink(
        document: Document,
        field: CustomField,
        target_doc_id: int,
    ):
        """
        Removes a 'symmetrical' link to `document` from the target document's existing custom field instance
        """
        target_doc_field_instance = CustomFieldInstance.objects.filter(
            document_id=target_doc_id,
            field=field,
        ).first()
        if (
            target_doc_field_instance is not None
            and document.id in target_doc_field_instance.value
        ):
            target_doc_field_instance.value.remove(document.id)
            target_doc_field_instance.save()
        Document.objects.filter(id=target_doc_id).update(modified=timezone.now())

    class Meta:
        model = CustomFieldInstance
        fields = [
            "value",
            "field",
        ]


class DocumentSerializer(
    OwnedObjectSerializer,
    NestedUpdateMixin,
    DynamicFieldsModelSerializer,
):
    approvals = serializers.SerializerMethodField(read_only=True)
    correspondent = CorrespondentField(allow_null=True)
    tags = TagsField(many=True)
    warehouse = WarehouseField(allow_null=True)
    folder = FolderField(allow_null=True)
    document_type = DocumentTypeField(allow_null=True)
    storage_path = StoragePathField(allow_null=True)

    original_file_name = SerializerMethodField()
    archived_file_name = SerializerMethodField()
    created_date = serializers.DateField(required=False)

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

    exploit = serializers.SerializerMethodField(read_only=True)

    def get_exploit(self, obj):
        doc = Document.objects.get(pk=obj.pk)
        current_user = self.context.get("request").user
        
        if current_user is not None and has_perms_owner_aware(
            current_user,
            "view_document",
            doc,
        ):
            return 1
        elif Approval.objects.filter(object_pk=obj.pk, status="PENDING", submitted_by=current_user):
            return 2
        else:
            return 3
        
    

    def get_approvals(self, obj):
        doc = Document.objects.get(pk=obj.pk)
        currentUser = self.context.get("request").user
        if currentUser is not None and not has_perms_owner_aware(
            currentUser,
            "view_document",
            doc,
        ):
            return None
        approvals = Approval.objects.filter(object_pk=obj.pk, status="SUCCESS")
        serializer = ApprovalSerializer(approvals, many=True)
        return serializer.data

    def get_original_file_name(self, obj):
        return obj.original_filename

    def get_archived_file_name(self, obj):
        if obj.has_archive_version:
            return obj.get_public_filename(archive=True)
        else:
            return None

    def to_representation(self, instance):
        doc = super().to_representation(instance)
        if self.truncate_content and "content" in self.fields:
            doc["content"] = doc.get("content")[0:550]
        return doc

    def update(self, instance: Document, validated_data):
        if "created_date" in validated_data and "created" not in validated_data:
            new_datetime = datetime.datetime.combine(
                validated_data.get("created_date"),
                datetime.time(0, 0, 0, 0, zoneinfo.ZoneInfo(settings.TIME_ZONE)),
            )
            instance.created = new_datetime
            instance.save()
        if "created_date" in validated_data:
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
                        CustomFieldInstanceSerializer.remove_doclink(
                            instance,
                            custom_field_instance.field,
                            doc_id,
                        )
        if validated_data.get("remove_inbox_tags"):
            tag_ids_being_added = (
                [
                    tag.id
                    for tag in validated_data["tags"]
                    if tag not in instance.tags.all()
                ]
                if "tags" in validated_data
                else []
            )
            inbox_tags_not_being_added = Tag.objects.filter(is_inbox_tag=True).exclude(
                id__in=tag_ids_being_added,
            )
            if "tags" in validated_data:
                validated_data["tags"] = [
                    tag
                    for tag in validated_data["tags"]
                    if tag not in inbox_tags_not_being_added
                ]
            else:
                validated_data["tags"] = [
                    tag
                    for tag in instance.tags.all()
                    if tag not in inbox_tags_not_being_added
                ]
        super().update(instance, validated_data)
        return instance

    def __init__(self, *args, **kwargs):
        self.truncate_content = kwargs.pop("truncate_content", False)

        # return full permissions if we're doing a PATCH or PUT
        context = kwargs.get("context")
        if (
            context.get("request").method == "PATCH"
            or context.get("request").method == "PUT"
        ):
            kwargs["full_perms"] = True

        super().__init__(*args, **kwargs)
    
    class Meta:
        model = Document
        depth = 1
        fields = (
            "id",
            "approvals",
            "correspondent",
            "document_type",
            "storage_path",
            "warehouse",
            "folder",
            "title",
            "content",
            "tags",
            "created",
            "created_date",
            "modified",
            "added",
            "archive_serial_number",
            "original_file_name",
            "archived_file_name",
            "owner",
            "permissions",
            "user_can_change",
            "is_shared_by_requester",
            "set_permissions",
            "notes",
            "custom_fields",
            "exploit",
            "remove_inbox_tags",
        ) 
    

class SavedViewFilterRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedViewFilterRule
        fields = ["rule_type", "value"]


class SavedViewSerializer(OwnedObjectSerializer):
    filter_rules = SavedViewFilterRuleSerializer(many=True)

    class Meta:
        model = SavedView
        fields = [
            "id",
            "name",
            "show_on_dashboard",
            "show_in_sidebar",
            "sort_field",
            "sort_reverse",
            "filter_rules",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        ]

    def update(self, instance, validated_data):
        if "filter_rules" in validated_data:
            rules_data = validated_data.pop("filter_rules")
        else:
            rules_data = None
        if "user" in validated_data:
            # backwards compatibility
            validated_data["owner"] = validated_data.pop("user")
        super().update(instance, validated_data)
        if rules_data is not None:
            SavedViewFilterRule.objects.filter(saved_view=instance).delete()
            for rule_data in rules_data:
                SavedViewFilterRule.objects.create(saved_view=instance, **rule_data)
        return instance

    def create(self, validated_data):
        rules_data = validated_data.pop("filter_rules")
        if "user" in validated_data:
            # backwards compatibility
            validated_data["owner"] = validated_data.pop("user")
        saved_view = SavedView.objects.create(**validated_data)
        for rule_data in rules_data:
            SavedViewFilterRule.objects.create(saved_view=saved_view, **rule_data)
        return saved_view


class DocumentListSerializer(serializers.Serializer):
    documents = serializers.ListField(
        required=True,
        label="Documents",
        write_only=True,
        child=serializers.IntegerField(),
    )

    def _validate_document_id_list(self, documents, name="documents"):
        if not isinstance(documents, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in documents):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = Document.objects.filter(id__in=documents).count()
        if not count == len(documents):
            raise serializers.ValidationError(
                f"Some documents in {name} don't exist or were specified twice.",
            )

    def validate_documents(self, documents):
        self._validate_document_id_list(documents)
        return documents


class BulkEditSerializer(
    SerializerWithPerms,
    DocumentListSerializer,
    SetPermissionsMixin,
):
    method = serializers.ChoiceField(
        choices=[
            "set_correspondent",
            "set_document_type",
            "set_storage_path",
            "set_warehouse"
            "set_folder",
            "add_tag",
            "remove_tag",
            "modify_tags",
            "delete",
            "redo_ocr",
            "set_permissions",
            "rotate",
            "merge",
            "split",
        ],
        label="Method",
        write_only=True,
    )

    parameters = serializers.DictField(allow_empty=True, default={}, write_only=True)

    def _validate_tag_id_list(self, tags, name="tags"):
        if not isinstance(tags, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in tags):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = Tag.objects.filter(id__in=tags).count()
        if not count == len(tags):
            raise serializers.ValidationError(
                f"Some tags in {name} don't exist or were specified twice.",
            )

    def validate_method(self, method):
        if method == "set_correspondent":
            return bulk_edit.set_correspondent
        elif method == "set_document_type":
            return bulk_edit.set_document_type
        elif method == "set_storage_path":
            return bulk_edit.set_storage_path
        elif method == "set_warehouse":
            return bulk_edit.set_warehouse
        elif method == "set_folder":
            return bulk_edit.set_folder
        elif method == "add_tag":
            return bulk_edit.add_tag
        elif method == "remove_tag":
            return bulk_edit.remove_tag
        elif method == "modify_tags":
            return bulk_edit.modify_tags
        elif method == "delete":
            return bulk_edit.delete
        elif method == "redo_ocr":
            return bulk_edit.redo_ocr
        elif method == "set_permissions":
            return bulk_edit.set_permissions
        elif method == "rotate":
            return bulk_edit.rotate
        elif method == "merge":
            return bulk_edit.merge
        elif method == "split":
            return bulk_edit.split
        else:
            raise serializers.ValidationError("Unsupported method.")

    def _validate_parameters_tags(self, parameters):
        if "tag" in parameters:
            tag_id = parameters["tag"]
            try:
                Tag.objects.get(id=tag_id)
            except Tag.DoesNotExist:
                raise serializers.ValidationError("Tag does not exist")
        else:
            raise serializers.ValidationError("tag not specified")

    def _validate_parameters_document_type(self, parameters):
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

    def _validate_parameters_correspondent(self, parameters):
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
        
    def _validate_parameters_warehouse(self, parameters):
        if "warehouse" in parameters:
            warehouse_id = parameters["warehouse"]
            if warehouse_id is None:
                return
            try:
                Warehouse.objects.get(id=warehouse_id)
            except Warehouse.DoesNotExist:
                raise serializers.ValidationError("Warehouse does not exist")
        else:
            raise serializers.ValidationError("warehouse not specified")
    
    def _validate_parameters_folder(self, parameters):
        if "folder" in parameters:
            folder_id = parameters["folder"]
            if folder_id is None:
                return
            try:
                Folder.objects.get(id=folder_id)
            except Folder.DoesNotExist:
                raise serializers.ValidationError("Folder does not exist")
        else:
            raise serializers.ValidationError("folder not specified")
    
    def _validate_storage_path(self, parameters):
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

    def _validate_parameters_modify_tags(self, parameters):
        if "add_tags" in parameters:
            self._validate_tag_id_list(parameters["add_tags"], "add_tags")
        else:
            raise serializers.ValidationError("add_tags not specified")

        if "remove_tags" in parameters:
            self._validate_tag_id_list(parameters["remove_tags"], "remove_tags")
        else:
            raise serializers.ValidationError("remove_tags not specified")

    def _validate_owner(self, owner):
        ownerUser = User.objects.get(pk=owner)
        if ownerUser is None:
            raise serializers.ValidationError("Specified owner cannot be found")
        return ownerUser

    def _validate_parameters_set_permissions(self, parameters):
        parameters["set_permissions"] = self.validate_set_permissions(
            parameters["set_permissions"],
        )
        if "owner" in parameters and parameters["owner"] is not None:
            self._validate_owner(parameters["owner"])
        if "merge" not in parameters:
            parameters["merge"] = False

    def _validate_parameters_rotate(self, parameters):
        try:
            if (
                "degrees" not in parameters
                or not float(parameters["degrees"]).is_integer()
            ):
                raise serializers.ValidationError("invalid rotation degrees")
        except ValueError:
            raise serializers.ValidationError("invalid rotation degrees")

    def _validate_parameters_split(self, parameters):
        if "pages" not in parameters:
            raise serializers.ValidationError("pages not specified")
        try:
            pages = []
            docs = parameters["pages"].split(",")
            for doc in docs:
                if "-" in doc:
                    pages.append(
                        [
                            x
                            for x in range(
                                int(doc.split("-")[0]),
                                int(doc.split("-")[1]) + 1,
                            )
                        ],
                    )
                else:
                    pages.append([int(doc)])
            parameters["pages"] = pages
        except ValueError:
            raise serializers.ValidationError("invalid pages specified")

    def validate(self, attrs):
        method = attrs["method"]
        parameters = attrs["parameters"]

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
        elif method == bulk_edit.set_warehouse:
            self._validate_parameters_warehouse(parameters)
        elif method == bulk_edit.set_folder:
            self._validate_parameters_folder(parameters)
        elif method == bulk_edit.set_permissions:
            self._validate_parameters_set_permissions(parameters)
        elif method == bulk_edit.rotate:
            self._validate_parameters_rotate(parameters)
        elif method == bulk_edit.split:
            if len(attrs["documents"]) > 1:
                raise serializers.ValidationError(
                    "Split method only supports one document",
                )
            self._validate_parameters_split(parameters)

        return attrs


class PostDocumentSerializer(serializers.Serializer):
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
    
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(),
        label="Folder",
        allow_null=True,
        write_only=True,
        required=False,
    )
    
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(),
        label="Warehouse",
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

    custom_fields = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomField.objects.all(),
        label="Custom fields",
        write_only=True,
        required=False,
    )

    def validate_document(self, document):
        document_data = document.file.read()
        mime_type = magic.from_buffer(document_data, mime=True)

        if not is_mime_type_supported(mime_type):
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
    
    def validate_folder(self, folder):
        if folder:
            return folder.id
        else:
            return None
        
    def validate_warehouse(self, warehouse):
        if warehouse:
            return warehouse.id
        else:
            return None

    def validate_tags(self, tags):
        if tags:
            return [tag.id for tag in tags]
        else:
            return None

    def validate_custom_fields(self, custom_fields):
        if custom_fields:
            return [custom_field.id for custom_field in custom_fields]
        else:
            return None


class BulkDownloadSerializer(DocumentListSerializer):
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

    def validate_path(self, path):
        try:
            path.format(
                title="title",
                correspondent="correspondent",
                document_type="document_type",
                folder="folder",
                warehouse="warehouse",
                created="created",
                created_year="created_year",
                created_year_short="created_year_short",
                created_month="created_month",
                created_month_name="created_month_name",
                created_month_name_short="created_month_name_short",
                created_day="created_day",
                added="added",
                added_year="added_year",
                added_year_short="added_year_short",
                added_month="added_month",
                added_month_name="added_month_name",
                added_month_name_short="added_month_name_short",
                added_day="added_day",
                asn="asn",
                tags="tags",
                tag_list="tag_list",
                owner_username="someone",
                original_name="testfile",
                doc_pk="doc_pk",
            )

        except KeyError as err:
            raise serializers.ValidationError(_("Invalid variable detected.")) from err

        return path

    def update(self, instance, validated_data):
        """
        When a storage path is updated, see if documents
        using it require a rename/move
        """
        doc_ids = [doc.id for doc in instance.documents.all()]
        if len(doc_ids):
            bulk_edit.bulk_update_documents.delay(doc_ids)

        return super().update(instance, validated_data)


class UiSettingsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiSettings
        depth = 1
        fields = [
            "id",
            "settings",
        ]

    def validate_settings(self, settings):
        # we never save update checking backend setting
        if "update_checking" in settings:
            try:
                settings["update_checking"].pop("backend_setting")
            except KeyError:
                pass
        return settings

    def create(self, validated_data):
        ui_settings = UiSettings.objects.update_or_create(
            user=validated_data.get("user"),
            defaults={"settings": validated_data.get("settings", None)},
        )
        return ui_settings


class TasksViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperlessTask
        depth = 1
        fields = (
            "id",
            "task_id",
            "task_file_name",
            "date_created",
            "date_done",
            "type",
            "status",
            "result",
            "acknowledged",
            "related_document",
        )

    type = serializers.SerializerMethodField()

    def get_type(self, obj):
        # just file tasks, for now
        return "file"

    related_document = serializers.SerializerMethodField()
    related_doc_re = re.compile(r"New document id (\d+) created")

    def get_related_document(self, obj):
        result = None
        if obj.status is not None and obj.status == states.SUCCESS:
            try:
                result = self.related_doc_re.search(obj.result).group(1)
            except Exception:
                pass

        return result

class ApprovalSerializer(serializers.ModelSerializer):
    # submitted_by = serializers.ReadOnlyField(source='submitted_by.username')
    ctype = serializers.ReadOnlyField(source='ctype.model')
    # submitted_by_id = serializers.PrimaryKeyRelatedField(source='submitted_by', queryset=User.objects.all(), write_only=True, allow_null=True)
    ctype_id = serializers.PrimaryKeyRelatedField(source='ctype', queryset=ContentType.objects.all(), write_only=True)
    name = serializers.SerializerMethodField(read_only=True)

    def get_name(self, obj):
        if obj.ctype:
            model_name = obj.ctype.name
            model_class = apps.get_model(obj.ctype.app_label, model_name)
            if model_class == Document:
                return model_class.objects.get(id=int(obj.object_pk)).title
        
        return None
    class Meta:
        model = Approval
        fields = "__all__"

class ApprovalViewSerializer(serializers.Serializer):
    approvals = serializers.ListField(
        required=True,
        label="approvals",
        write_only=True,
        child=serializers.IntegerField(),
    )
    status = serializers.CharField(required=True)

    def _validate_approval_id_list(self, approvals, name="approvals"):
        if not isinstance(approvals, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in approvals):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = PaperlessTask.objects.filter(id__in=approvals).count()
        if not count == len(approvals):
            raise serializers.ValidationError(
                f"Some tasks in {name} don't exist or were specified twice.",
            )

    def validate_approvals(self, approvals):
        self._validate_approval_id_list(approvals)
        return approvals

    def validate_status(self, status):
        valid_statuses = ["PENDING", "SUCCESS", "FAILURE", "REVOKED"]
        if status not in valid_statuses:
            raise serializers.ValidationError(
                f"status must be one of: {', '.join(valid_statuses)}")
        return status

class AcknowledgeTasksViewSerializer(serializers.Serializer):
    tasks = serializers.ListField(
        required=True,
        label="Tasks",
        write_only=True,
        child=serializers.IntegerField(),
    )

    def _validate_task_id_list(self, tasks, name="tasks"):
        if not isinstance(tasks, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in tasks):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = PaperlessTask.objects.filter(id__in=tasks).count()
        if not count == len(tasks):
            raise serializers.ValidationError(
                f"Some tasks in {name} don't exist or were specified twice.",
            )

    def validate_tasks(self, tasks):
        self._validate_task_id_list(tasks)
        return tasks


class ShareLinkSerializer(OwnedObjectSerializer):
    class Meta:
        model = ShareLink
        fields = (
            "id",
            "created",
            "expiration",
            "slug",
            "document",
            "file_version",
        )

    def create(self, validated_data):
        validated_data["slug"] = get_random_string(50)
        return super().create(validated_data)


class BulkEditObjectsSerializer(SerializerWithPerms, SetPermissionsMixin):
    objects = serializers.ListField(
        required=True,
        allow_empty=False,
        label="Objects",
        write_only=True,
        child=serializers.IntegerField(),
    )

    object_type = serializers.ChoiceField(
        choices=[
            "tags",
            "correspondents",
            "document_types",
            "storage_paths",
            "warehouses",
            "folders",
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

    permissions = serializers.DictField(
        label="Set permissions",
        allow_empty=False,
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
        elif object_type == "warehouses":
            object_class = Warehouse
        elif object_type == "folders":
            object_class = Folder
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

    def _validate_permissions(self, permissions):
        self.validate_set_permissions(
            permissions,
        )

    def validate(self, attrs):
        object_type = attrs["object_type"]
        objects = attrs["objects"]
        operation = attrs.get("operation")

        self._validate_objects(objects, object_type)

        if operation == "set_permissions":
            permissions = attrs.get("permissions")
            if permissions is not None:
                self._validate_permissions(permissions)

        return attrs


class WorkflowTriggerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    sources = fields.MultipleChoiceField(
        choices=WorkflowTrigger.DocumentSourceChoices.choices,
        allow_empty=True,
        default={
            DocumentSource.ConsumeFolder,
            DocumentSource.ApiUpload,
            DocumentSource.MailFetch,
        },
    )

    type = serializers.ChoiceField(
        choices=WorkflowTrigger.WorkflowTriggerType.choices,
        label="Trigger Type",
    )

    class Meta:
        model = WorkflowTrigger
        fields = [
            "id",
            "sources",
            "type",
            "filter_path",
            "filter_filename",
            "filter_mailrule",
            "matching_algorithm",
            "match",
            "is_insensitive",
            "filter_has_tags",
            "filter_has_correspondent",
            "filter_has_document_type",
            "filter_has_groups",
            "filter_has_status",
            "filter_has_content_type",
            "filter_has_access_type",
        ]

    def validate(self, attrs):
        # Empty strings treated as None to avoid unexpected behavior
        if (
            "filter_filename" in attrs
            and attrs["filter_filename"] is not None
            and len(attrs["filter_filename"]) == 0
        ):
            attrs["filter_filename"] = None
        if (
            "filter_path" in attrs
            and attrs["filter_path"] is not None
            and len(attrs["filter_path"]) == 0
        ):
            attrs["filter_path"] = None

        if (
            attrs["type"] == WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
            and "filter_mailrule" not in attrs
            and ("filter_filename" not in attrs or attrs["filter_filename"] is None)
            and ("filter_path" not in attrs or attrs["filter_path"] is None)
        ):
            raise serializers.ValidationError(
                "File name, path or mail rule filter are required",
            )

        return attrs


class WorkflowActionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    assign_correspondent = CorrespondentField(allow_null=True, required=False)
    assign_tags = TagsField(many=True, allow_null=True, required=False)
    assign_document_type = DocumentTypeField(allow_null=True, required=False)
    assign_storage_path = StoragePathField(allow_null=True, required=False)
    

    class Meta:
        model = WorkflowAction
        fields = [
            "id",
            "type",
            "assign_content_type",
            "assign_title",
            "assign_tags",
            "assign_correspondent",
            "assign_document_type",
            "assign_storage_path",
            "assign_owner",
            "assign_view_users",
            "assign_view_groups",
            "assign_change_users",
            "assign_change_groups",
            "assign_custom_fields",
            "remove_all_tags",
            "remove_tags",
            "remove_all_correspondents",
            "remove_correspondents",
            "remove_all_document_types",
            "remove_document_types",
            "remove_all_storage_paths",
            "remove_storage_paths",
            "remove_custom_fields",
            "remove_all_custom_fields",
            "remove_all_owners",
            "remove_owners",
            "remove_all_permissions",
            "remove_view_users",
            "remove_view_groups",
            "remove_change_users",
            "remove_change_groups",
        ]

    def validate(self, attrs):
        if "assign_title" in attrs and attrs["assign_title"] is not None:
            if len(attrs["assign_title"]) == 0:
                # Empty strings treated as None to avoid unexpected behavior
                attrs["assign_title"] = None
            else:
                try:
                    # test against all placeholders, see consumer.py `parse_doc_title_w_placeholders`
                    attrs["assign_title"].format(
                        correspondent="",
                        document_type="",
                        added="",
                        added_year="",
                        added_year_short="",
                        added_month="",
                        added_month_name="",
                        added_month_name_short="",
                        added_day="",
                        added_time="",
                        owner_username="",
                        original_filename="",
                        created="",
                        created_year="",
                        created_year_short="",
                        created_month="",
                        created_month_name="",
                        created_month_name_short="",
                        created_day="",
                        created_time="",
                    )
                except (ValueError, KeyError) as e:
                    raise serializers.ValidationError(
                        {"assign_title": f'Invalid f-string detected: "{e.args[0]}"'},
                    )

        return attrs


class WorkflowSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(required=False)

    triggers = WorkflowTriggerSerializer(many=True)
    actions = WorkflowActionSerializer(many=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "order",
            "enabled",
            "triggers",
            "actions",
        ]

    def update_triggers_and_actions(self, instance: Workflow, triggers, actions):
        set_triggers = []
        set_actions = []

        if triggers is not None:
            for trigger in triggers:
                filter_has_tags = trigger.pop("filter_has_tags", None)
                filter_has_groups = trigger.pop("filter_has_groups", None)
                trigger_instance, _ = WorkflowTrigger.objects.update_or_create(
                    id=trigger.get("id"),
                    defaults=trigger,
                )
                if filter_has_tags is not None:
                    trigger_instance.filter_has_tags.set(filter_has_tags)
                if filter_has_groups is not None:
                    trigger_instance.filter_has_groups.set(filter_has_groups)
                set_triggers.append(trigger_instance)

        if actions is not None:
            for action in actions:
                assign_tags = action.pop("assign_tags", None)
                assign_view_users = action.pop("assign_view_users", None)
                assign_view_groups = action.pop("assign_view_groups", None)
                assign_change_users = action.pop("assign_change_users", None)
                assign_change_groups = action.pop("assign_change_groups", None)
                assign_custom_fields = action.pop("assign_custom_fields", None)
                remove_tags = action.pop("remove_tags", None)
                remove_correspondents = action.pop("remove_correspondents", None)
                remove_document_types = action.pop("remove_document_types", None)
                remove_storage_paths = action.pop("remove_storage_paths", None)
                remove_custom_fields = action.pop("remove_custom_fields", None)
                remove_owners = action.pop("remove_owners", None)
                remove_view_users = action.pop("remove_view_users", None)
                remove_view_groups = action.pop("remove_view_groups", None)
                remove_change_users = action.pop("remove_change_users", None)
                remove_change_groups = action.pop("remove_change_groups", None)

                action_instance, _ = WorkflowAction.objects.update_or_create(
                    id=action.get("id"),
                    defaults=action,
                )

                if assign_tags is not None:
                    action_instance.assign_tags.set(assign_tags)
                if assign_view_users is not None:
                    action_instance.assign_view_users.set(assign_view_users)
                if assign_view_groups is not None:
                    action_instance.assign_view_groups.set(assign_view_groups)
                if assign_change_users is not None:
                    action_instance.assign_change_users.set(assign_change_users)
                if assign_change_groups is not None:
                    action_instance.assign_change_groups.set(assign_change_groups)
                if assign_custom_fields is not None:
                    action_instance.assign_custom_fields.set(assign_custom_fields)
                if remove_tags is not None:
                    action_instance.remove_tags.set(remove_tags)
                if remove_correspondents is not None:
                    action_instance.remove_correspondents.set(remove_correspondents)
                if remove_document_types is not None:
                    action_instance.remove_document_types.set(remove_document_types)
                if remove_storage_paths is not None:
                    action_instance.remove_storage_paths.set(remove_storage_paths)
                if remove_custom_fields is not None:
                    action_instance.remove_custom_fields.set(remove_custom_fields)
                if remove_owners is not None:
                    action_instance.remove_owners.set(remove_owners)
                if remove_view_users is not None:
                    action_instance.remove_view_users.set(remove_view_users)
                if remove_view_groups is not None:
                    action_instance.remove_view_groups.set(remove_view_groups)
                if remove_change_users is not None:
                    action_instance.remove_change_users.set(remove_change_users)
                if remove_change_groups is not None:
                    action_instance.remove_change_groups.set(remove_change_groups)

                set_actions.append(action_instance)

        instance.triggers.set(set_triggers)
        instance.actions.set(set_actions)
        instance.save()

    def prune_triggers_and_actions(self):
        """
        ManyToMany fields dont support e.g. on_delete so we need to discard unattached
        triggers and actionas manually
        """
        for trigger in WorkflowTrigger.objects.all():
            if trigger.workflows.all().count() == 0:
                trigger.delete()

        for action in WorkflowAction.objects.all():
            if action.workflows.all().count() == 0:
                action.delete()

    def create(self, validated_data) -> Workflow:
        if "triggers" in validated_data:
            triggers = validated_data.pop("triggers")

        if "actions" in validated_data:
            actions = validated_data.pop("actions")

        instance = super().create(validated_data)

        self.update_triggers_and_actions(instance, triggers, actions)

        return instance

    def update(self, instance: Workflow, validated_data) -> Workflow:
        if "triggers" in validated_data:
            triggers = validated_data.pop("triggers")

        if "actions" in validated_data:
            actions = validated_data.pop("actions")

        instance = super().update(instance, validated_data)

        self.update_triggers_and_actions(instance, triggers, actions)

        self.prune_triggers_and_actions()

        return instance






class WarehouseSerializer(MatchingModelSerializer, OwnedObjectSerializer):
    document_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Warehouse
        fields = '__all__'
    
    def get_document_count(self, obj):
        return self.get_total_document_count(obj)

    def get_total_document_count(self, warehouse):
        if warehouse.type == Warehouse.BOXCASE:
            return Document.objects.filter(warehouse=warehouse).count()
        elif warehouse.type == Warehouse.SHELF:
            child_warehouses = Warehouse.objects.filter(parent_warehouse=warehouse)
            total_count = 0
            for child_warehouse in child_warehouses:
                total_count += self.get_total_document_count(child_warehouse)
            return total_count
        elif warehouse.type == Warehouse.WAREHOUSE:
            child_warehouses = Warehouse.objects.filter(parent_warehouse=warehouse)
            total_count = 0
            for child_warehouse in child_warehouses:
                total_count += self.get_total_document_count(child_warehouse)
            return total_count
        else:
            return 0
    
    
class FolderSerializer(MatchingModelSerializer, OwnedObjectSerializer):
        
    class Meta:
        model = Folder
        fields = '__all__'   

    