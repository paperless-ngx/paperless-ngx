from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):

    groups = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    inherited_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "date_joined",
            "is_staff",
            "is_active",
            "is_superuser",
            "groups",
            "permissions",
            "inherited_permissions",
        )

    def get_groups(self, obj):
        return list(obj.groups.values_list("name", flat=True))

    def get_permissions(self, obj):
        # obj.get_user_permissions() returns more permissions than desired
        permission_natural_keys = []
        permissions = obj.user_permissions.all()
        for permission in permissions:
            permission_natural_keys.append(
                permission.natural_key()[1] + "." + permission.natural_key()[0],
            )
        return permission_natural_keys

    def get_inherited_permissions(self, obj):
        return obj.get_group_permissions()


class GroupSerializer(serializers.ModelSerializer):

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "permissions",
        )

    def get_permissions(self, obj):
        permission_natural_keys = []
        permissions = obj.permissions.all()
        for permission in permissions:
            permission_natural_keys.append(
                permission.natural_key()[1] + "." + permission.natural_key()[0],
            )
        return permission_natural_keys
