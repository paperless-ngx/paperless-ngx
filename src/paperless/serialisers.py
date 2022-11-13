from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):

    inherited_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "date_joined",
            "last_login",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
            "inherited_permissions",
        )

    def get_inherited_permissions(self, obj):
        inherited_permissions_ids = []
        inherited_permissions = obj.get_group_permissions()
        for permission in inherited_permissions:
            inherited_permissions_ids.append(
                perm_to_permission(permission).pk,
            )
        return list(set(inherited_permissions_ids))


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "permissions",
        )


def perm_to_permission(perm):

    """
    Convert a identifier string permission format in 'app_label.codename'
    (teremd as *perm*) to a django permission instance.

    Examples
    --------
    >>> permission = perm_to_permission('auth.add_user')
    >>> permission.content_type.app_label == 'auth'
    True
    >>> permission.codename == 'add_user'
    True
    """

    try:
        app_label, codename = perm.split(".", 1)
    except IndexError:
        raise AttributeError(
            "The format of identifier string permission (perm) is wrong. "
            "It should be in 'app_label.codename'.",
        )
    else:
        permission = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
        return permission
