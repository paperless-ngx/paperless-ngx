from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django_filters.rest_framework import FilterSet

CHAR_KWARGS = ["istartswith", "iendswith", "icontains", "iexact"]
ID_KWARGS = ["in", "exact"]
INT_KWARGS = ["exact", "gt", "gte", "lt", "lte", "isnull"]
DATE_KWARGS = ["year", "month", "day", "date__gt", "gt", "date__lt", "lt"]


class UserFilterSet(FilterSet):
    class Meta:
        model = User
        fields = {"username": CHAR_KWARGS}


class GroupFilterSet(FilterSet):
    class Meta:
        model = Group
        fields = {"name": CHAR_KWARGS}
