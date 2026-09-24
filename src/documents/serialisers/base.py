from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import get_users_with_perms
from guardian.utils import get_group_obj_perms_model
from guardian.utils import get_user_obj_perms_model
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.fields import SerializerMethodField
from rest_framework.utils import model_meta

from documents import bulk_edit
from documents.models import Document
from documents.models import MatchingModel
from documents.models import Note
from documents.permissions import get_groups_with_only_permission
from documents.permissions import set_permissions_for_object
from documents.regex import validate_regex_pattern

if TYPE_CHECKING:
    from collections.abc import Iterable


logger = logging.getLogger("paperless.serializers")


# https://www.django-rest-framework.org/api-guide/serializers/#example
class DynamicFieldsModelSerializer(serializers.ModelSerializer[Any]):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs) -> None:
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


class DocumentUpdateFieldsModelSerializer(DynamicFieldsModelSerializer):
    stale_update_excluded_fields = frozenset({"filename", "archive_filename"})

    def _get_update_fields(self, validated_data) -> list[str]:
        model_fields = {
            field.name
            for field in self.Meta.model._meta.concrete_fields
            if field.name not in self.stale_update_excluded_fields
        }
        update_fields = [
            field_name for field_name in validated_data if field_name in model_fields
        ]
        if "modified" in model_fields and "modified" not in update_fields:
            update_fields.append("modified")
        return update_fields

    def update(self, instance, validated_data):
        serializers.raise_errors_on_nested_writes("update", self, validated_data)
        info = model_meta.get_field_info(instance)

        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)

        # File names are managed by post-save file handling.  Saving only the
        # serializer-updated fields prevents stale in-memory path values from
        # overwriting a concurrent move.
        instance.save(update_fields=self._get_update_fields(validated_data))

        for attr, value in m2m_fields:
            field = getattr(instance, attr)
            field.set(value)

        return instance


class MatchingModelSerializer(serializers.ModelSerializer[Any]):
    document_count = serializers.IntegerField(read_only=True)

    def get_slug(self, obj) -> str:
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
            else self.user
            if hasattr(self, "user")
            else None
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
                validate_regex_pattern(match)
            except ValueError as e:
                logger.debug(f"Invalid regular expression: {e!s}")
                raise serializers.ValidationError(
                    "Invalid regular expression, see log for details.",
                )
        return match


PERMISSION_ACTIONS = ("view", "change")


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
        permissions_dict = {action: {} for action in PERMISSION_ACTIONS}
        if set_permissions is not None:
            for action in PERMISSION_ACTIONS:
                if action in set_permissions:
                    if "users" in set_permissions[action]:
                        users = set_permissions[action]["users"]
                        permissions_dict[action]["users"] = self._validate_user_ids(
                            users,
                        )
                    if "groups" in set_permissions[action]:
                        groups = set_permissions[action]["groups"]
                        permissions_dict[action]["groups"] = self._validate_group_ids(
                            groups,
                        )
                else:
                    del permissions_dict[action]
        return permissions_dict

    def _set_permissions(self, permissions, object) -> None:
        set_permissions_for_object(permissions, object)


class SerializerWithPerms(serializers.Serializer[dict[str, Any]]):
    def __init__(self, *args, **kwargs) -> None:
        self.user = kwargs.pop("user", None)
        self.full_perms = kwargs.pop("full_perms", False)
        self.all_fields = kwargs.pop("all_fields", False)
        super().__init__(*args, **kwargs)


class PermissionSetSerializer(serializers.Serializer[dict[str, Any]]):
    users = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
    )
    groups = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
    )


class SetPermissionsSerializer(serializers.Serializer[dict[str, Any]]):
    view = PermissionSetSerializer(required=False)
    change = PermissionSetSerializer(required=False)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown_keys = set(data) - set(PERMISSION_ACTIONS)
            if unknown_keys:
                raise serializers.ValidationError(
                    {key: "Unknown permission action." for key in sorted(unknown_keys)},
                )
        return super().to_internal_value(data)


class OwnedObjectSerializer(
    SerializerWithPerms,
    serializers.ModelSerializer[Any],
    SetPermissionsMixin,
):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if not self.all_fields:
            try:
                if self.full_perms:
                    self.fields.pop("user_can_change")
                    self.fields.pop("is_shared_by_requester")
                else:
                    self.fields.pop("permissions")
            except KeyError:
                pass

    def _get_perms(self, obj, codename: str, target: Literal["users", "groups"]):
        """
        Get the given permissions from context or from django-guardian.

        :param codename: The permission codename, e.g. 'view' or 'change'
        :param target: 'users' or 'groups'
        """
        key = f"{target}_{codename}_perms"
        cached = self.context.get(key, {}).get(obj.pk)
        if cached is not None:
            return list(cached)

        # Permission not found in the context, get it from guardian
        if target == "users":
            return list(
                get_users_with_perms(
                    obj,
                    only_with_perms_in=[f"{codename}_{obj.__class__.__name__.lower()}"],
                    with_group_users=False,
                ).values_list("id", flat=True),
            )
        else:  # groups
            return list(
                get_groups_with_only_permission(
                    obj,
                    codename=f"{codename}_{obj.__class__.__name__.lower()}",
                ).values_list("id", flat=True),
            )

    @extend_schema_field(
        field={
            "type": "object",
            "properties": {
                "view": {
                    "type": "object",
                    "properties": {
                        "users": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "groups": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                },
                "change": {
                    "type": "object",
                    "properties": {
                        "users": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "groups": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                },
            },
        },
    )
    def get_permissions(self, obj) -> dict:
        return {
            "view": {
                "users": self._get_perms(obj, "view", "users"),
                "groups": self._get_perms(obj, "view", "groups"),
            },
            "change": {
                "users": self._get_perms(obj, "change", "users"),
                "groups": self._get_perms(obj, "change", "groups"),
            },
        }

    def get_user_can_change(self, obj) -> bool:
        if obj.owner is None or obj.owner == self.user:
            return True
        if self.user is None:
            return False
        if self.user.is_active and self.user.is_superuser:
            # Mirrors guardian's own ObjectPermissionChecker.has_perm() shortcut --
            # superusers aren't necessarily granted explicit object permissions,
            # so the batched context below would otherwise incorrectly say no.
            return True

        # Prefer the page-level batch computed by BulkPermissionMixin
        # (get_serializer_context) over a fresh per-object guardian check,
        # which would otherwise query the permission tables once per row.
        users_change_perms = self.context.get("users_change_perms")
        groups_change_perms = self.context.get("groups_change_perms")
        if users_change_perms is not None and groups_change_perms is not None:
            if self.user.pk in users_change_perms.get(obj.pk, []):
                return True
            user_group_ids = getattr(self, "_user_group_ids", None)
            if user_group_ids is None:
                user_group_ids = set(self.user.groups.values_list("id", flat=True))
                self._user_group_ids = user_group_ids
            return bool(
                user_group_ids.intersection(groups_change_perms.get(obj.pk, [])),
            )

        checker = ObjectPermissionChecker(self.user)
        return checker.has_perm(f"change_{obj.__class__.__name__.lower()}", obj)

    @staticmethod
    def get_shared_object_pks(objects: Iterable):
        """
        Return the primary keys of the subset of objects that are shared.
        """
        try:
            first_obj = next(iter(objects))
        except StopIteration:
            return set()

        ctype = ContentType.objects.get_for_model(first_obj)
        object_pks = list(obj.pk for obj in objects)
        pk_type = type(first_obj.pk)

        def get_pks_for_permission_type(model):
            return map(
                pk_type,  # coerce the pk to be the same type of the provided objects
                model.objects.filter(
                    content_type=ctype,
                    object_pk__in=object_pks,
                )
                .values_list("object_pk", flat=True)
                .distinct(),
            )

        UserObjectPermission = get_user_obj_perms_model()
        GroupObjectPermission = get_group_obj_perms_model()
        user_permission_pks = get_pks_for_permission_type(UserObjectPermission)
        group_permission_pks = get_pks_for_permission_type(GroupObjectPermission)

        return set(user_permission_pks) | set(group_permission_pks)

    def get_is_shared_by_requester(self, obj: Document) -> bool:
        # First check the context to see if `shared_object_pks` is set by the parent.
        shared_object_pks = self.context.get("shared_object_pks")
        # If not just check if the current object is shared.
        if shared_object_pks is None:
            shared_object_pks = self.get_shared_object_pks([obj])
        return obj.owner == self.user and obj.id in shared_object_pks

    permissions = SerializerMethodField(read_only=True, required=False)
    user_can_change = SerializerMethodField(read_only=True, required=False)
    is_shared_by_requester = SerializerMethodField(read_only=True, required=False)

    set_permissions = SetPermissionsSerializer(
        label="Set permissions",
        required=False,
        write_only=True,
    )
    # other methods in mixin

    def validate_unique_together(self, validated_data, instance=None) -> None:
        # workaround for https://github.com/encode/django-rest-framework/issues/9358
        if "owner" in validated_data and "name" in self.Meta.fields:
            name = validated_data.get("name", instance.name if instance else None)
            objects = (
                self.Meta.model.objects.exclude(pk=instance.pk)
                if instance
                else self.Meta.model.objects.all()
            )
            not_unique = objects.filter(
                owner=validated_data["owner"],
                name=name,
            ).exists()
            if not_unique:
                raise serializers.ValidationError(
                    {"error": "Object violates owner / name unique constraint"},
                )

    def create(self, validated_data):
        # default to current user if not set
        request = self.context.get("request")
        if (
            "owner" not in validated_data
            or (request is not None and "owner" not in request.data)
        ) and self.user:
            validated_data["owner"] = self.user
        permissions = None
        if "set_permissions" in validated_data:
            permissions = validated_data.pop("set_permissions")
        self.validate_unique_together(validated_data)
        instance = super().create(validated_data)
        if permissions is not None:
            self._set_permissions(permissions, instance)
        return instance

    def update(self, instance, validated_data):
        user = getattr(self, "user", None)
        is_superuser = user.is_superuser if user is not None else False
        is_owner = instance.owner == user if user is not None else False
        is_unowned = instance.owner is None

        if (
            ("owner" in validated_data and validated_data["owner"] != instance.owner)
            or "set_permissions" in validated_data
        ) and not (is_superuser or is_owner or is_unowned):
            raise PermissionDenied(
                _("Insufficient permissions."),
            )

        if "set_permissions" in validated_data:
            self._set_permissions(validated_data["set_permissions"], instance)
        self.validate_unique_together(validated_data, instance)
        return super().update(instance, validated_data)


class OwnedObjectListSerializer(serializers.ListSerializer[Any]):
    def to_representation(self, documents):
        self.child.context["shared_object_pks"] = self.child.get_shared_object_pks(
            documents,
        )
        return super().to_representation(documents)


class ReadWriteSerializerMethodField(serializers.SerializerMethodField):
    """
    Based on https://stackoverflow.com/a/62579804
    """

    def __init__(self, method_name=None, *args, **kwargs) -> None:
        self.method_name = method_name
        kwargs["source"] = "*"
        super(serializers.SerializerMethodField, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        return {self.field_name: data}


class DocumentListSerializer(serializers.Serializer[dict[str, list[int]]]):
    documents = serializers.ListField(
        required=True,
        label="Documents",
        write_only=True,
        child=serializers.IntegerField(),
    )

    def _validate_document_id_list(self, documents, name="documents") -> None:
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


class DocumentSelectionSerializer(DocumentListSerializer):
    documents = serializers.ListField(
        required=False,
        label="Documents",
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

    excluded_documents = serializers.ListField(
        required=False,
        default=list,
        write_only=True,
        child=serializers.IntegerField(),
    )

    def validate(self, attrs):
        if attrs.get("all", False):
            attrs.setdefault("documents", [])
            return attrs

        if attrs["excluded_documents"]:
            raise serializers.ValidationError(
                "excluded_documents is only supported when all is true.",
            )

        if "documents" not in attrs:
            raise serializers.ValidationError(
                "documents is required unless all is true.",
            )

        documents = attrs["documents"]
        self._validate_document_id_list(documents)
        return attrs


class SourceModeValidationMixin:
    def validate_source_mode(self, source_mode: str) -> str:
        if source_mode not in bulk_edit.SourceModeChoices.__dict__.values():
            raise serializers.ValidationError("Invalid source_mode")
        return source_mode


class BasicUserSerializer(serializers.ModelSerializer[User]):
    # Different than paperless.serializers.UserSerializer
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class NotesSerializer(serializers.ModelSerializer[Note]):
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = Note
        fields = ["id", "note", "created", "user"]
        ordering = ["-created"]
