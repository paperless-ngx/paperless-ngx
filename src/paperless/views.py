from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlencode

from allauth.mfa import signals
from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.base.internal.flows import delete_and_cleanup
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.flows import auto_generate_recovery_codes
from allauth.mfa.totp.internal import auth as totp_auth
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models.functions import Lower
from django.http import FileResponse
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import View
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.index import DelayedQuery
from documents.permissions import PaperlessObjectPermissions
from documents.tasks import llmindex_index
from paperless.external_auth import build_external_auth_callback_url
from paperless.external_auth import consume_external_auth_code
from paperless.external_auth import does_pkce_match
from paperless.external_auth import external_auth_is_enabled
from paperless.external_auth import get_external_auth_flow
from paperless.external_auth import is_allowed_redirect_uri
from paperless.external_auth import issue_external_auth_code
from paperless.external_auth import pop_external_auth_flow
from paperless.external_auth import save_external_auth_flow
from paperless.external_auth import validate_code_challenge
from paperless.filters import GroupFilterSet
from paperless.filters import UserFilterSet
from paperless.models import ApplicationConfiguration
from paperless.serialisers import ApplicationConfigurationSerializer
from paperless.serialisers import ExternalAuthCodeExchangeSerializer
from paperless.serialisers import ExternalAuthConsentSerializer
from paperless.serialisers import GroupSerializer
from paperless.serialisers import PaperlessAuthTokenSerializer
from paperless.serialisers import ProfileSerializer
from paperless.serialisers import UserSerializer
from paperless_ai.indexing import vector_store_file_exists


class PaperlessObtainAuthTokenView(ObtainAuthToken):
    serializer_class = PaperlessAuthTokenSerializer


def _external_auth_error_response(
    request,
    *,
    status_code: int,
    title: str,
    message: str,
):
    return render(
        request,
        "paperless-ngx/external_auth_error.html",
        {
            "title": title,
            "message": message,
        },
        status=status_code,
    )


class ExternalLoginStartView(View):
    def get(self, request, *args, **kwargs):
        if not external_auth_is_enabled():
            return _external_auth_error_response(
                request,
                status_code=403,
                title=_("External app login unavailable"),
                message=_(
                    "External app login is not configured on this server.",
                ),
            )

        redirect_uri = request.GET.get("redirect_uri")
        if not redirect_uri:
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Missing redirect URI."),
            )
        if not is_allowed_redirect_uri(redirect_uri):
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Redirect URI is not allowed."),
            )

        code_challenge = request.GET.get("code_challenge")
        if not code_challenge:
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Missing PKCE code challenge."),
            )

        code_challenge_method = request.GET.get("code_challenge_method")
        if not code_challenge_method:
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Missing PKCE code challenge method."),
            )
        code_challenge_validation_error = validate_code_challenge(
            code_challenge,
            code_challenge_method,
        )
        if code_challenge_validation_error == "unsupported_method":
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Unsupported PKCE code challenge method."),
            )
        if code_challenge_validation_error == "invalid_code_challenge":
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Invalid login request"),
                message=_("Invalid PKCE code challenge."),
            )

        save_external_auth_flow(
            request,
            redirect_uri=redirect_uri,
            state=request.GET.get("state"),
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )

        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse("external_auth_complete"))

        return HttpResponseRedirect(
            f"{reverse('account_login')}?{urlencode({'next': reverse('external_auth_complete')})}",
        )


class ExternalLoginCompleteView(View):
    def get(self, request, *args, **kwargs):
        flow = get_external_auth_flow(request)
        if flow is None:
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Login request expired"),
                message=_(
                    "This external login request is invalid or has expired. "
                    "Please restart login from your app.",
                ),
            )

        if not request.user.is_authenticated:
            return HttpResponseRedirect(
                f"{reverse('account_login')}?{urlencode({'next': reverse('external_auth_complete')})}",
            )

        return render(
            request,
            "paperless-ngx/external_auth_success.html",
            {
                "callback_uri": flow["redirect_uri"],
            },
        )

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(
                f"{reverse('account_login')}?{urlencode({'next': reverse('external_auth_complete')})}",
            )

        serializer = ExternalAuthConsentSerializer(data=request.POST)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        flow = pop_external_auth_flow(request)
        if flow is None:
            return _external_auth_error_response(
                request,
                status_code=400,
                title=_("Login request expired"),
                message=_(
                    "This external login request is invalid or has expired. "
                    "Please restart login from your app.",
                ),
            )

        if action == "deny":
            callback_url = build_external_auth_callback_url(
                flow["redirect_uri"],
                error="access_denied",
                state=flow["state"],
            )
            return HttpResponse(status=302, headers={"Location": callback_url})

        code = issue_external_auth_code(
            user_id=request.user.pk,
            redirect_uri=flow["redirect_uri"],
            code_challenge=flow["code_challenge"],
            code_challenge_method=flow["code_challenge_method"],
        )
        callback_url = build_external_auth_callback_url(
            flow["redirect_uri"],
            code=code,
            state=flow["state"],
        )
        return HttpResponse(status=302, headers={"Location": callback_url})


@extend_schema_view(
    post=extend_schema(
        request=ExternalAuthCodeExchangeSerializer,
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
            400: OpenApiTypes.STR,
        },
    ),
)
class ExternalLoginExchangeView(GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = ExternalAuthCodeExchangeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = consume_external_auth_code(serializer.validated_data["code"])
        if payload is None:
            return HttpResponseBadRequest("Invalid or expired code")

        if serializer.validated_data["redirect_uri"] != payload["redirect_uri"]:
            return HttpResponseBadRequest("Invalid or expired code")

        if not does_pkce_match(
            code_verifier=serializer.validated_data["code_verifier"],
            code_challenge=payload["code_challenge"],
            code_challenge_method=payload["code_challenge_method"],
        ):
            return HttpResponseBadRequest("Invalid or expired code")

        user = User.objects.filter(pk=payload["user_id"], is_active=True).first()
        if user is None:
            return HttpResponseBadRequest("Invalid or expired code")

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


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
        query = self.page.paginator.object_list
        if isinstance(query, DelayedQuery):
            try:
                ids = [
                    query.searcher.ixreader.stored_fields(
                        doc_num,
                    )["id"]
                    for doc_num in query.saved_results.get(0).results.docs()
                ]
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
            "items": {"type": "integer"},
        }
        return response_schema


class FaviconView(View):
    def get(self, request, *args, **kwargs):
        try:
            path = Path(staticfiles_storage.path("paperless/img/favicon.ico"))
            return FileResponse(path.open("rb"), content_type="image/x-icon")
        except FileNotFoundError:
            return HttpResponseNotFound("favicon.ico not found")


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

    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.data.get("is_superuser") is True:
            return HttpResponseForbidden(
                "Superuser status can only be granted by a superuser",
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user_to_update: User = self.get_object()
        if not request.user.is_superuser and user_to_update.is_superuser:
            return HttpResponseForbidden(
                "Superusers can only be modified by other superusers",
            )
        if (
            not request.user.is_superuser
            and request.data.get("is_superuser") is not None
            and request.data.get("is_superuser") != user_to_update.is_superuser
        ):
            return HttpResponseForbidden(
                "Superuser status can only be changed by a superuser",
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
class TOTPView(GenericAPIView):
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


@extend_schema_view(
    list=extend_schema(
        description="Get the application configuration",
        external_docs={
            "description": "Application Configuration",
            "url": "https://docs.paperless-ngx.com/configuration/",
        },
    ),
)
class ApplicationConfigurationViewSet(ModelViewSet):
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
            llmindex_index.delay(
                progress_bar_disable=True,
                rebuild=True,
                scheduled=False,
                auto=True,
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


@extend_schema_view(
    get=extend_schema(
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class SocialAccountProvidersView(GenericAPIView):
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
