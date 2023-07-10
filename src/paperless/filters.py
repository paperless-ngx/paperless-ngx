from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django_filters.rest_framework import FilterSet

from documents.filters import CHAR_KWARGS
from paperless.models import SSOGroup


class UserFilterSet(FilterSet):
    class Meta:
        model = User
        fields = {"username": CHAR_KWARGS}


class GroupFilterSet(FilterSet):
    class Meta:
        model = Group
        fields = {"name": CHAR_KWARGS}


class SSOGroupFilterSet(FilterSet):
    class Meta:
        model = SSOGroup
        fields = {"name": CHAR_KWARGS}
