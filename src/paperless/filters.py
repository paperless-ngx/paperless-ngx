from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django_filters.rest_framework import FilterSet

from documents.filters import CaseFoldNameFilter


class UserFilterSet(FilterSet):
    username__icontains = CaseFoldNameFilter(lookup_expr="icontains")
    username__istartswith = CaseFoldNameFilter(lookup_expr="istartswith")
    username__iendswith = CaseFoldNameFilter(lookup_expr="iendswith")
    username__iexact = CaseFoldNameFilter(lookup_expr="iexact")

    class Meta:
        model = User
        fields = {}


class GroupFilterSet(FilterSet):
    name__icontains = CaseFoldNameFilter(lookup_expr="icontains")
    name__istartswith = CaseFoldNameFilter(lookup_expr="istartswith")
    name__iendswith = CaseFoldNameFilter(lookup_expr="iendswith")
    name__iexact = CaseFoldNameFilter(lookup_expr="iexact")

    class Meta:
        model = Group
        fields = {}
