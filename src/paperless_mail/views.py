import datetime
import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.utils import timezone
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
from paperless_mail.mail import refresh_oauth_token
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer


class MailAccountViewSet(ModelViewSet, PassUserMixin):
    model = MailAccount

    queryset = MailAccount.objects.all().order_by("pk")
    serializer_class = MailAccountSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)

    @action(methods=["post"], detail=True)
    def refresh_oauth_token(self, request, pk=None):
        return (
            Response({"success": True})
            if refresh_oauth_token(MailAccount.objects.get(id=pk))
            else HttpResponseBadRequest("Unable to refresh token")
        )


class MailRuleViewSet(ModelViewSet, PassUserMixin):
    model = MailRule

    queryset = MailRule.objects.all().order_by("order")
    serializer_class = MailRuleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)


class MailAccountTestView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MailAccountSerializer

    def post(self, request, *args, **kwargs):
        logger = logging.getLogger("paperless_mail")
        request.data["name"] = datetime.datetime.now().isoformat()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # account exists, use the password from there instead of ***
        if (
            len(serializer.validated_data.get("password").replace("*", "")) == 0
            and request.data["id"] is not None
        ):
            serializer.validated_data["password"] = MailAccount.objects.get(
                pk=request.data["id"],
            ).password

        account = MailAccount(**serializer.validated_data)

        with get_mailbox(
            account.imap_server,
            account.imap_port,
            account.imap_security,
        ) as M:
            try:
                mailbox_login(M, account)
                return Response({"success": True})
            except MailError:
                logger.error(
                    f"Mail account {account} test failed",
                )
                return HttpResponseBadRequest("Unable to connect to server")


class OauthCallbackView(GenericAPIView):
    def get(self, request, format=None):
        logger = logging.getLogger("paperless_mail")
        code = request.query_params.get("code")
        # Gmail passes scope as a query param, Outlook does not
        scope = request.query_params.get("scope")

        if code is None:
            logger.error(
                f"Invalid oauth callback request, code: {code}, scope: {scope}",
            )
            return HttpResponseBadRequest("Invalid request, see logs for more detail")

        if scope is not None and "google" in scope:
            # Google
            # Gmail setup guide: https://postmansmtp.com/how-to-configure-post-smtp-with-gmailgsuite-using-oauth/
            account_type = MailAccount.AccountType.GMAIL
            imap_server = "imap.gmail.com"
            defaults = {
                "name": f"Gmail OAuth {datetime.now()}",
                "username": "",
                "imap_security": MailAccount.ImapSecurity.SSL,
                "imap_port": 993,
                "account_type": account_type,
            }

            token_request_uri = "https://accounts.google.com/o/oauth2/token"
            client_id = settings.GMAIL_OAUTH_CLIENT_ID
            client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
            scope = "https://mail.google.com/"
        elif scope is None:
            # Outlook
            # Outlok setup guide: https://medium.com/@manojkumardhakad/python-read-and-send-outlook-mail-using-oauth2-token-and-graph-api-53de606ecfa1
            account_type = MailAccount.AccountType.OUTLOOK
            imap_server = "outlook.office365.com"
            defaults = {
                "name": f"Outlook OAuth {datetime.now()}",
                "username": "",
                "imap_security": MailAccount.ImapSecurity.SSL,
                "imap_port": 993,
                "account_type": account_type,
            }

            token_request_uri = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            )
            client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
            client_secret = settings.OUTLOOK_OAUTH_CLIENT_SECRET
            scope = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"

        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
            "redirect_uri": "http://localhost:8000/api/oauth/callback/",
            "grant_type": "authorization_code",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = httpx.post(token_request_uri, data=data, headers=headers)
        data = response.json()

        if "error" in data:
            logger.error(f"Error {response.status_code} getting access token: {data}")
            return HttpResponseRedirect(
                "http://localhost:4200/mail?oauth_success=0",
            )
        elif "access_token" in data:
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            expires_in = data["expires_in"]
            account, _ = MailAccount.objects.update_or_create(
                password=access_token,
                is_token=True,
                imap_server=imap_server,
                refresh_token=refresh_token,
                expiration=timezone.now() + timedelta(seconds=expires_in),
                defaults=defaults,
            )
            return HttpResponseRedirect(
                f"http://localhost:4200/mail?oauth_success=1&account_id={account.pk}",
            )
