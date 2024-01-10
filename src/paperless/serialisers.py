import logging

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import serializers

from paperless.models import ApplicationConfiguration

logger = logging.getLogger("paperless.settings")


class ObfuscatedUserPasswordField(serializers.Field):
    """
    Sends *** string instead of password in the clear
    """

    def to_representation(self, value):
        return "**********" if len(value) > 0 else ""

    def to_internal_value(self, data):
        return data


class UserSerializer(serializers.ModelSerializer):
    password = ObfuscatedUserPasswordField(required=False)
    user_permissions = serializers.SlugRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        slug_field="codename",
        required=False,
    )
    inherited_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "date_joined",
            "is_staff",
            "is_active",
            "is_superuser",
            "groups",
            "user_permissions",
            "inherited_permissions",
        )

    def get_inherited_permissions(self, obj):
        return obj.get_group_permissions()

    def update(self, instance, validated_data):
        if "password" in validated_data:
            if len(validated_data.get("password").replace("*", "")) > 0:
                instance.set_password(validated_data.get("password"))
                instance.save()
            validated_data.pop("password")
        super().update(instance, validated_data)
        return instance

    def create(self, validated_data):
        groups = None
        if "groups" in validated_data:
            groups = validated_data.pop("groups")
        user_permissions = None
        if "user_permissions" in validated_data:
            user_permissions = validated_data.pop("user_permissions")
        password = None
        if (
            "password" in validated_data
            and len(validated_data.get("password").replace("*", "")) > 0
        ):
            password = validated_data.pop("password")
        user = User.objects.create(**validated_data)
        # set groups
        if groups:
            user.groups.set(groups)
        # set permissions
        if user_permissions:
            user.user_permissions.set(user_permissions)
        # set password
        if password:
            user.set_password(password)
        user.save()
        return user


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        slug_field="codename",
    )

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "permissions",
        )


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(allow_null=False)
    password = ObfuscatedUserPasswordField(required=False, allow_null=False)
    auth_token = serializers.SlugRelatedField(read_only=True, slug_field="key")

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "auth_token",
        )


class ApplicationConfigurationSerializer(serializers.ModelSerializer):
    user_args = serializers.JSONField(binary=True, allow_null=True)

    def run_validation(self, data):
        # Empty strings treated as None to avoid unexpected behavior
        if "user_args" in data and data["user_args"] == "":
            data["user_args"] = None
        if "language" in data and data["language"] == "":
            data["language"] = None
        return super().run_validation(data)

    class Meta:
        model = ApplicationConfiguration
        fields = "__all__"
