import datetime
import logging

from django.http import HttpResponseBadRequest
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
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer


class MailAccountViewSet(ModelViewSet, PassUserMixin):
    model = MailAccount

    queryset = MailAccount.objects.all().order_by("pk")
    serializer_class = MailAccountSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (ObjectOwnedOrGrantedPermissionsFilter,)


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
