import datetime
import logging
from datetime import timedelta

from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.utils import timezone
from httpx_oauth.oauth2 import GetAccessTokenError
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.filters import ObjectOwnedOrGrantedPermissionsFilter
from documents.permissions import PaperlessObjectPermissions
from documents.views import PassUserMixin
from paperless.views import StandardPagination
from paperless_mail.mail import MailError
from paperless_mail.mail import get_mailbox
from paperless_mail.mail import mailbox_login
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.oauth import PaperlessMailOAuth2Manager
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer
from paperless_mail.tasks import process_mail_accounts


class MailAccountViewSet(ModelViewSet, PassUserMixin):
    model = MailAccount

    queryset = MailAccount.objects.all().order_by("pk")
    serializer_class = MailAccountSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)

    def get_permissions(self):
        if self.action == "test":
            # Test action does not require object level permissions
            self.permission_classes = (IsAuthenticated,)
        return super().get_permissions()

    @action(methods=["post"], detail=False)
    def test(self, request):
        logger = logging.getLogger("paperless_mail")
        request.data["name"] = datetime.datetime.now().isoformat()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # account exists, use the password from there instead of *** and refresh_token / expiration
        if (
            len(serializer.validated_data.get("password").replace("*", "")) == 0
            and request.data["id"] is not None
        ):
            existing_account = MailAccount.objects.get(pk=request.data["id"])
            serializer.validated_data["password"] = existing_account.password
            serializer.validated_data["account_type"] = existing_account.account_type
            serializer.validated_data["refresh_token"] = existing_account.refresh_token
            serializer.validated_data["expiration"] = existing_account.expiration

        account = MailAccount(**serializer.validated_data)
        with get_mailbox(
            account.imap_server,
            account.imap_port,
            account.imap_security,
        ) as M:
            try:
                if (
                    account.is_token
                    and account.expiration is not None
                    and account.expiration < timezone.now()
                ):
                    oauth_manager = PaperlessMailOAuth2Manager()
                    if oauth_manager.refresh_account_oauth_token(existing_account):
                        # User is not changing password and token needs to be refreshed
                        existing_account.refresh_from_db()
                        account.password = existing_account.password
                    else:
                        raise MailError("Unable to refresh oauth token")

                mailbox_login(M, account)
                return Response({"success": True})
            except MailError as e:
                logger.error(
                    f"Mail account {account} test failed: {e}",
                )
                return HttpResponseBadRequest("Unable to connect to server")

    @action(methods=["post"], detail=True)
    def process(self, request, pk=None):
        account = self.get_object()
        process_mail_accounts.delay([account.pk])

        return Response({"result": "OK"})


class MailRuleViewSet(ModelViewSet, PassUserMixin):
    model = MailRule

    queryset = MailRule.objects.all().order_by("order")
    serializer_class = MailRuleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)


class OauthCallbackView(GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        if not (
            request.user and request.user.has_perms(["paperless_mail.add_mailaccount"])
        ):
            return HttpResponseBadRequest(
                "You do not have permission to add mail accounts",
            )

        logger = logging.getLogger("paperless_mail")
        code = request.query_params.get("code")
        # Gmail passes scope as a query param, Outlook does not
        scope = request.query_params.get("scope")

        if code is None:
            logger.error(
                f"Invalid oauth callback request, code: {code}, scope: {scope}",
            )
            return HttpResponseBadRequest("Invalid request, see logs for more detail")

        oauth_manager = PaperlessMailOAuth2Manager()

        try:
            if scope is not None and "google" in scope:
                # Google
                account_type = MailAccount.MailAccountType.GMAIL_OAUTH
                imap_server = "imap.gmail.com"
                defaults = {
                    "name": f"Gmail OAuth {timezone.now()}",
                    "username": "",
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "imap_port": 993,
                    "account_type": account_type,
                }
                result = oauth_manager.get_gmail_access_token(code)

            elif scope is None:
                # Outlook
                account_type = MailAccount.MailAccountType.OUTLOOK_OAUTH
                imap_server = "outlook.office365.com"
                defaults = {
                    "name": f"Outlook OAuth {timezone.now()}",
                    "username": "",
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "imap_port": 993,
                    "account_type": account_type,
                }

                result = oauth_manager.get_outlook_access_token(code)

            access_token = result["access_token"]
            refresh_token = result["refresh_token"]
            expires_in = result["expires_in"]
            account, _ = MailAccount.objects.update_or_create(
                password=access_token,
                is_token=True,
                imap_server=imap_server,
                refresh_token=refresh_token,
                expiration=timezone.now() + timedelta(seconds=expires_in),
                defaults=defaults,
            )
            return HttpResponseRedirect(
                f"{oauth_manager.oauth_redirect_url}?oauth_success=1&account_id={account.pk}",
            )
        except GetAccessTokenError as e:
            logger.error(f"Error getting access token: {e}")
            return HttpResponseRedirect(
                f"{oauth_manager.oauth_redirect_url}?oauth_success=0",
            )
