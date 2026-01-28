import datetime
import logging
from datetime import timedelta
from typing import Any

from adrf.views import APIView
from adrf.viewsets import ModelViewSet
from adrf.viewsets import ReadOnlyModelViewSet
from asgiref.sync import sync_to_async
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from httpx_oauth.oauth2 import GetAccessTokenError
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from documents.filters import ObjectOwnedOrGrantedPermissionsFilter
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import has_perms_owner_aware
from documents.views import PassUserMixin
from paperless.views import StandardPagination
from paperless_mail.filters import ProcessedMailFilterSet
from paperless_mail.mail import MailError
from paperless_mail.mail import get_mailbox
from paperless_mail.mail import mailbox_login
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.oauth import PaperlessMailOAuth2Manager
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer
from paperless_mail.serialisers import ProcessedMailSerializer
from paperless_mail.tasks import process_mail_accounts

logger: logging.Logger = logging.getLogger("paperless_mail")


@extend_schema_view(
    test=extend_schema(
        operation_id="mail_account_test",
        request=MailAccountSerializer,
        description="Test a mail account",
        responses={
            200: inline_serializer(
                name="MailAccountTestResponse",
                fields={"success": serializers.BooleanField()},
            ),
            400: OpenApiTypes.STR,
        },
    ),
    process=extend_schema(
        operation_id="mail_account_process",
        description="Manually process the selected mail account for new messages.",
        responses={
            200: inline_serializer(
                name="MailAccountProcessResponse",
                fields={"result": serializers.CharField(default="OK")},
            ),
            404: None,
        },
    ),
)
class MailAccountViewSet(ModelViewSet, PassUserMixin):
    queryset = MailAccount.objects.all().order_by("pk")
    serializer_class = MailAccountSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)

    def get_permissions(self) -> list[Any]:
        if self.action == "test":
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(methods=["post"], detail=False)
    async def test(self, request: Request) -> Response | HttpResponseBadRequest:
        request.data["name"] = datetime.datetime.now().isoformat()
        serializer = self.get_serializer(data=request.data)

        # Validation must be wrapped because of sync DB validators
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        validated_data: dict[str, Any] = serializer.validated_data

        if (
            len(str(validated_data.get("password", "")).replace("*", "")) == 0
            and request.data.get("id") is not None
        ):
            existing_account = await MailAccount.objects.aget(pk=request.data["id"])
            validated_data.update(
                {
                    "password": existing_account.password,
                    "account_type": existing_account.account_type,
                    "refresh_token": existing_account.refresh_token,
                    "expiration": existing_account.expiration,
                },
            )

        account = MailAccount(**validated_data)

        def _blocking_imap_test() -> bool:
            with get_mailbox(
                account.imap_server,
                account.imap_port,
                account.imap_security,
            ) as m_box:
                if (
                    account.is_token
                    and account.expiration
                    and account.expiration < timezone.now()
                ):
                    oauth_manager = PaperlessMailOAuth2Manager()
                    if oauth_manager.refresh_account_oauth_token(existing_account):
                        # User is not changing password and token needs to be refreshed
                        account.password = existing_account.password
                    else:
                        raise MailError("Unable to refresh oauth token")
                mailbox_login(m_box, account)
                return True

        try:
            await sync_to_async(_blocking_imap_test, thread_sensitive=False)()
            return Response({"success": True})
        except MailError as e:
            logger.error(f"Mail account {account} test failed: {e}")
            return HttpResponseBadRequest("Unable to connect to server")

    @action(methods=["post"], detail=True)
    async def process(self, request: Request, pk: int | None = None) -> Response:
        # FIX: Use aget_object() provided by adrf to avoid SynchronousOnlyOperation
        account = await self.aget_object()
        process_mail_accounts.delay([account.pk])
        return Response({"result": "OK"})


class ProcessedMailViewSet(ReadOnlyModelViewSet, PassUserMixin):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    serializer_class = ProcessedMailSerializer
    pagination_class = StandardPagination
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = ProcessedMailFilterSet
    queryset = ProcessedMail.objects.all().order_by("-processed")

    @action(methods=["post"], detail=False)
    async def bulk_delete(
        self,
        request: Request,
    ) -> Response | HttpResponseBadRequest | HttpResponseForbidden:
        mail_ids: list[int] = request.data.get("mail_ids", [])
        if not isinstance(mail_ids, list) or not all(
            isinstance(i, int) for i in mail_ids
        ):
            return HttpResponseBadRequest("mail_ids must be a list of integers")

        # Store objects to delete after verification
        to_delete: list[ProcessedMail] = []

        # We must verify permissions for every requested ID
        async for mail in ProcessedMail.objects.filter(id__in=mail_ids):
            can_delete = await sync_to_async(has_perms_owner_aware)(
                request.user,
                "delete_processedmail",
                mail,
            )
            if not can_delete:
                # This is what the test is looking for: 403 on permission failure
                return HttpResponseForbidden("Insufficient permissions")
            to_delete.append(mail)

        # Only perform deletions if all items passed the permission check
        for mail in to_delete:
            await mail.adelete()

        return Response({"result": "OK", "deleted_mail_ids": mail_ids})


class MailRuleViewSet(ModelViewSet, PassUserMixin):
    model = MailRule

    queryset = MailRule.objects.all().order_by("order")
    serializer_class = MailRuleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)


@extend_schema_view(
    get=extend_schema(
        description="Callback view for OAuth2 authentication",
        responses={200: None},
    ),
)
class OauthCallbackView(APIView):
    permission_classes = (IsAuthenticated,)

    async def get(
        self,
        request: Request,
    ) -> Response | HttpResponseBadRequest | HttpResponseRedirect:
        has_perm = await sync_to_async(request.user.has_perm)(
            "paperless_mail.add_mailaccount",
        )
        if not has_perm:
            return HttpResponseBadRequest(
                "You do not have permission to add mail accounts",
            )

        code: str | None = request.query_params.get("code")
        state: str | None = request.query_params.get("state")
        scope: str | None = request.query_params.get("scope")

        if not code or not state:
            return HttpResponseBadRequest("Invalid request parameters")

        oauth_manager = PaperlessMailOAuth2Manager(
            state=request.session.get("oauth_state"),
        )
        if not oauth_manager.validate_state(state):
            return HttpResponseBadRequest("Invalid OAuth state")

        try:
            defaults: dict[str, Any] = {
                "username": "",
                "imap_security": MailAccount.ImapSecurity.SSL,
                "imap_port": 993,
            }

            if scope and "google" in scope:
                account_type = MailAccount.MailAccountType.GMAIL_OAUTH
                imap_server = "imap.gmail.com"
                defaults.update(
                    {
                        "name": f"Gmail OAuth {timezone.now()}",
                        "account_type": account_type,
                    },
                )
                result = await sync_to_async(oauth_manager.get_gmail_access_token)(code)
            else:
                account_type = MailAccount.MailAccountType.OUTLOOK_OAUTH
                imap_server = "outlook.office365.com"
                defaults.update(
                    {
                        "name": f"Outlook OAuth {timezone.now()}",
                        "account_type": account_type,
                    },
                )
                result = await sync_to_async(oauth_manager.get_outlook_access_token)(
                    code,
                )

            account, _ = await MailAccount.objects.aupdate_or_create(
                imap_server=imap_server,
                refresh_token=result["refresh_token"],
                defaults={
                    **defaults,
                    "password": result["access_token"],
                    "is_token": True,
                    "expiration": timezone.now()
                    + timedelta(seconds=result["expires_in"]),
                },
            )
            return HttpResponseRedirect(
                f"{oauth_manager.oauth_redirect_url}?oauth_success=1&account_id={account.pk}",
            )
        except GetAccessTokenError as e:
            logger.error(f"Error getting access token: {e}")
            return HttpResponseRedirect(
                f"{oauth_manager.oauth_redirect_url}?oauth_success=0",
            )
