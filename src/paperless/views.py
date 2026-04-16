from collections import OrderedDict
from pathlib import Path
from typing import Any

from allauth.mfa import signals
from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.base.internal.flows import delete_and_cleanup
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.flows import auto_generate_recovery_codes
from allauth.mfa.totp.internal import auth as totp_auth
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models.functions import Lower
from django.http import FileResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.views.generic import View
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.fields import BooleanField
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import ModelViewSet

from documents.models import PaperlessTask
from documents.permissions import PaperlessObjectPermissions
from documents.tasks import llmindex_index
from paperless.filters import GroupFilterSet
from paperless.filters import UserFilterSet
from paperless.models import ApplicationConfiguration
from paperless.serialisers import ApplicationConfigurationSerializer
from paperless.serialisers import GroupSerializer
from paperless.serialisers import PaperlessAuthTokenSerializer
from paperless.serialisers import ProfileSerializer
from paperless.serialisers import UserSerializer
from paperless_ai.indexing import vector_store_file_exists


class PaperlessObtainAuthTokenView(ObtainAuthToken):
    serializer_class = PaperlessAuthTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100000

    def _get_api_version(self) -> int:
        request = getattr(self, "request", None)
        default_version = settings.REST_FRAMEWORK["DEFAULT_VERSION"]
        return int(request.version if request else default_version)

    def _should_include_all(self) -> bool:
        # TODO: remove legacy `all` support when API v9 is dropped.
        return self._get_api_version() < 10

    def get_paginated_response(self, data):
        response_data = [
            ("count", self.page.paginator.count),
            ("next", self.get_next_link()),
            ("previous", self.get_previous_link()),
        ]
        if self._should_include_all():
            response_data.append(("all", self.get_all_result_ids()))
        response_data.append(("results", data))

        return Response(
            OrderedDict(response_data),
        )

    def get_all_result_ids(self):
        from documents.search import TantivyRelevanceList

        query = self.page.paginator.object_list
        if isinstance(query, TantivyRelevanceList):
            return query.get_all_ids()
        return self.page.paginator.object_list.values_list("pk", flat=True)

    def get_paginated_response_schema(self, schema):
        response_schema = super().get_paginated_response_schema(schema)
        if self._should_include_all():
            response_schema["properties"]["all"] = {
                "type": "array",
                "example": "[1, 2, 3]",
                "items": {"type": "integer"},
            }
        else:
            response_schema["properties"].pop("all", None)
        return response_schema


class FaviconView(View):
    def get(self, request, *args, **kwargs):
        try:
            path = Path(staticfiles_storage.path("paperless/img/favicon.ico"))
            return FileResponse(path.open("rb"), content_type="image/x-icon")
        except FileNotFoundError:
            return HttpResponseNotFound("favicon.ico not found")


class UserViewSet(ModelViewSet[User]):
    _BOOL_NOT_PROVIDED = object()
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

    @staticmethod
    def _parse_requested_bool(data, key: str):
        if key not in data:
            return UserViewSet._BOOL_NOT_PROVIDED
        try:
            return BooleanField().to_internal_value(data.get(key))
        except ValidationError:
            # Let serializer validation report invalid values as 400 responses
            return UserViewSet._BOOL_NOT_PROVIDED

    def create(self, request, *args, **kwargs):
        requested_is_superuser = self._parse_requested_bool(
            request.data,
            "is_superuser",
        )
        requested_is_staff = self._parse_requested_bool(request.data, "is_staff")

        if not request.user.is_superuser:
            if requested_is_superuser is True:
                return HttpResponseForbidden(
                    "Superuser status can only be granted by a superuser",
                )
            if requested_is_staff is True:
                return HttpResponseForbidden(
                    "Staff status can only be granted by a superuser",
                )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user_to_update: User = self.get_object()

        if not request.user.is_superuser and user_to_update.is_superuser:
            return HttpResponseForbidden(
                "Superusers can only be modified by other superusers",
            )

        requested_is_superuser = self._parse_requested_bool(
            request.data,
            "is_superuser",
        )
        requested_is_staff = self._parse_requested_bool(request.data, "is_staff")

        if (
            not request.user.is_superuser
            and requested_is_superuser is not self._BOOL_NOT_PROVIDED
            and requested_is_superuser != user_to_update.is_superuser
        ):
            return HttpResponseForbidden(
                "Superuser status can only be changed by a superuser",
            )
        if (
            not request.user.is_superuser
            and requested_is_staff is not self._BOOL_NOT_PROVIDED
            and requested_is_staff != user_to_update.is_staff
        ):
            return HttpResponseForbidden(
                "Staff status can only be changed by a superuser",
            )
        return super().update(request, *args, **kwargs)

    @extend_schema(
        request=None,
        responses={
            200: OpenApiTypes.BOOL,
            404: OpenApiTypes.STR,
        },
    )
    @action(detail=True, methods=["post"])
    def deactivate_totp(self, request, pk=None):
        request_user = request.user
        user = User.objects.get(pk=pk)
        if not request_user.is_superuser and request_user != user:
            return HttpResponseForbidden(
                "You do not have permission to deactivate TOTP for this user",
            )
        authenticator = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).first()
        if authenticator is not None:
            delete_and_cleanup(request, authenticator)
            return Response(data=True)
        else:
            return HttpResponseNotFound("TOTP not found")


class GroupViewSet(ModelViewSet[Group]):
    model = Group

    queryset = Group.objects.order_by(Lower("name"))

    serializer_class = GroupSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupFilterSet
    ordering_fields = ("name",)


class ProfileView(GenericAPIView[Any]):
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

        password = serializer.validated_data.pop("password", None)
        if password and password.replace("*", ""):
            user.set_password(password)
            user.save()

        for key, value in serializer.validated_data.items():
            setattr(user, key, value)
        user.save()

        return Response(serializer.to_representation(user))


@extend_schema_view(
    get=extend_schema(
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
    post=extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "secret": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["secret", "code"],
            },
        },
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
    delete=extend_schema(
        responses={
            (200, "application/json"): OpenApiTypes.BOOL,
            404: OpenApiTypes.STR,
        },
    ),
)
class TOTPView(GenericAPIView[Any]):
    """
    TOTP views
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Generates a new TOTP secret and returns the URL and SVG
        """
        user = self.request.user
        mfa_adapter = get_mfa_adapter()
        secret = totp_auth.get_totp_secret(regenerate=True)
        url = mfa_adapter.build_totp_url(user, secret)
        svg = mfa_adapter.build_totp_svg(url)
        return Response(
            {
                "url": url,
                "qr_svg": svg,
                "secret": secret,
            },
        )

    def post(self, request, *args, **kwargs):
        """
        Validates a TOTP code and activates the TOTP authenticator
        """
        valid = totp_auth.validate_totp_code(
            request.data["secret"],
            request.data["code"],
        )
        recovery_codes = None
        if valid:
            auth = totp_auth.TOTP.activate(
                request.user,
                request.data["secret"],
            ).instance
            signals.authenticator_added.send(
                sender=Authenticator,
                request=request,
                user=request.user,
                authenticator=auth,
            )
            rc_auth: Authenticator = auto_generate_recovery_codes(request)
            if rc_auth:
                recovery_codes = rc_auth.wrap().get_unused_codes()
        return Response(
            {
                "success": valid,
                "recovery_codes": recovery_codes,
            },
        )

    def delete(self, request, *args, **kwargs):
        """
        Deactivates the TOTP authenticator
        """
        user = self.request.user
        authenticator = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).first()
        if authenticator is not None:
            delete_and_cleanup(request, authenticator)
            return Response(data=True)
        else:
            return HttpResponseNotFound("TOTP not found")


@extend_schema_view(
    post=extend_schema(
        request={
            "application/json": None,
        },
        responses={
            (200, "application/json"): OpenApiTypes.STR,
        },
    ),
)
class GenerateAuthTokenView(GenericAPIView[Any]):
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


@extend_schema_view(
    list=extend_schema(
        description="Get the application configuration",
        external_docs={
            "description": "Application Configuration",
            "url": "https://docs.paperless-ngx.com/configuration/",
        },
    ),
)
class ApplicationConfigurationViewSet(ModelViewSet[ApplicationConfiguration]):
    model = ApplicationConfiguration

    queryset = ApplicationConfiguration.objects

    serializer_class = ApplicationConfigurationSerializer
    permission_classes = (IsAuthenticated, DjangoModelPermissions)

    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        return Response(status=405)  # Not Allowed

    def perform_update(self, serializer):
        old_instance = ApplicationConfiguration.objects.all().first()
        old_ai_index_enabled = (
            old_instance.ai_enabled and old_instance.llm_embedding_backend
        )

        new_instance: ApplicationConfiguration = serializer.save()
        new_ai_index_enabled = (
            new_instance.ai_enabled and new_instance.llm_embedding_backend
        )

        if (
            not old_ai_index_enabled
            and new_ai_index_enabled
            and not vector_store_file_exists()
        ):
            # AI index was just enabled and vector store file does not exist
            llmindex_index.apply_async(
                kwargs={"rebuild": True},
                headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
            )


@extend_schema_view(
    post=extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                },
                "required": ["id"],
            },
        },
        responses={
            (200, "application/json"): OpenApiTypes.INT,
            400: OpenApiTypes.STR,
        },
    ),
)
class DisconnectSocialAccountView(GenericAPIView[Any]):
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


@extend_schema_view(
    get=extend_schema(
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class SocialAccountProvidersView(GenericAPIView[Any]):
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
