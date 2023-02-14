import os

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.views.generic import View
from django_filters.rest_framework import DjangoFilterBackend
from documents.permissions import PaperlessObjectPermissions
from paperless.filters import GroupFilterSet
from paperless.filters import UserFilterSet
from paperless.serialisers import GroupSerializer
from paperless.serialisers import UserSerializer
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100000


class FaviconView(View):
    def get(self, request, *args, **kwargs):  # pragma: nocover
        favicon = os.path.join(
            os.path.dirname(__file__),
            "static",
            "paperless",
            "img",
            "favicon.ico",
        )
        with open(favicon, "rb") as f:
            return HttpResponse(f, content_type="image/x-icon")


class UserViewSet(ModelViewSet):
    model = User

    queryset = User.objects.exclude(
        username__in=["consumer", "AnonymousUser"],
    ).order_by(Lower("username"))

    serializer_class = UserSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = UserFilterSet
    ordering_fields = ("username",)


class GroupViewSet(ModelViewSet):
    model = Group

    queryset = Group.objects.order_by(Lower("name"))

    serializer_class = GroupSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupFilterSet
    ordering_fields = ("name",)
