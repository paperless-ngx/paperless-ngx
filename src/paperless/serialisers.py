from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):

    user_permissions = serializers.SlugRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        slug_field="codename",
    )
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
            "user_permissions",
            "inherited_permissions",
        )

    def get_inherited_permissions(self, obj):
        return obj.get_group_permissions()


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
