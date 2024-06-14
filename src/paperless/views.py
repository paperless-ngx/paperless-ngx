import os
from collections import OrderedDict

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.views.generic import View
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.authtoken.models import Token
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from documents.permissions import PaperlessObjectPermissions
from paperless.filters import GroupFilterSet
from paperless.filters import UserFilterSet
from paperless.models import ApplicationConfiguration
from paperless.serialisers import ApplicationConfigurationSerializer
from paperless.serialisers import GroupSerializer
from paperless.serialisers import ProfileSerializer
from paperless.serialisers import UserSerializer


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100000

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("all", self.get_all_result_ids()),
                    ("results", data),
                ],
            ),
        )

    def get_all_result_ids(self):
        ids = []
        if hasattr(self.page.paginator.object_list, "saved_results"):
            results_page = self.page.paginator.object_list.saved_results[0]
            if results_page is not None:
                for i in range(len(results_page.results.docs())):
                    try:
                        fields = results_page.results.fields(i)
                        if "id" in fields:
                            ids.append(fields["id"])
                    except Exception:
                        pass
        else:
            ids = self.page.paginator.object_list.values_list("pk", flat=True)
        return ids

    def get_paginated_response_schema(self, schema):
        response_schema = super().get_paginated_response_schema(schema)
        response_schema["properties"]["all"] = {
            "type": "array",
            "example": "[1, 2, 3]",
        }
        return response_schema


class FaviconView(View):
    def get(self, request, *args, **kwargs):  # pragma: no cover
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


class ProfileView(GenericAPIView):
    """
    User profile view, only available when logged in
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer

    def get(self, request, *args, **kwargs):
        user = self.request.user

        serializer = self.get_serializer(data=request.data)
        return Response(serializer.to_representation(user))

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.request.user if hasattr(self.request, "user") else None

        if len(serializer.validated_data.get("password").replace("*", "")) > 0:
            user.set_password(serializer.validated_data.get("password"))
            user.save()
        serializer.validated_data.pop("password")

        for key, value in serializer.validated_data.items():
            setattr(user, key, value)
        user.save()

        return Response(serializer.to_representation(user))


class GenerateAuthTokenView(GenericAPIView):
    """
    Generates (or re-generates) an auth token, requires a logged in user
    unlike the default DRF endpoint
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user

        existing_token = Token.objects.filter(user=user).first()
        if existing_token is not None:
            existing_token.delete()
        token = Token.objects.create(user=user)
        return Response(
            token.key,
        )


class ApplicationConfigurationViewSet(ModelViewSet):
    model = ApplicationConfiguration

    queryset = ApplicationConfiguration.objects

    serializer_class = ApplicationConfigurationSerializer
    permission_classes = (IsAuthenticated, DjangoModelPermissions)


class DisconnectSocialAccountView(GenericAPIView):
    """
    Disconnects a social account provider from the user account
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user

        try:
            account = user.socialaccount_set.get(pk=request.data["id"])
            account_id = account.id
            account.delete()
            return Response(account_id)
        except SocialAccount.DoesNotExist:
            return HttpResponseBadRequest("Social account not found")


class SocialAccountProvidersView(APIView):
    """
    List of social account providers
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        adapter = get_adapter()
        providers = adapter.list_providers(request)
        resp = [
            {"name": p.name, "login_url": p.get_login_url(request, process="connect")}
            for p in providers
            if p.id != "openid"
        ]

        for openid_provider in filter(lambda p: p.id == "openid", providers):
            resp += [
                {
                    "name": b["name"],
                    "login_url": openid_provider.get_login_url(
                        request,
                        process="connect",
                        openid=b["openid_url"],
                    ),
                }
                for b in openid_provider.get_brands()
            ]

        return Response(sorted(resp, key=lambda p: p["name"]))
