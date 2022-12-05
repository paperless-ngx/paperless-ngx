from paperless.views import StandardPagination
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet


class MailAccountViewSet(ModelViewSet):
    model = MailAccount

    queryset = MailAccount.objects.all().order_by("pk")
    serializer_class = MailAccountSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)

    # TODO: user-scoped
    # def get_queryset(self):
    #     user = self.request.user
    #     return MailAccount.objects.filter(user=user)

    # def perform_create(self, serializer):
    #     serializer.save(user=self.request.user)


class MailRuleViewSet(ModelViewSet):
    model = MailRule

    queryset = MailRule.objects.all().order_by("pk")
    serializer_class = MailRuleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)

    # TODO: user-scoped
    # def get_queryset(self):
    #     user = self.request.user
    #     return MailRule.objects.filter(user=user)

    # def perform_create(self, serializer):
    #     serializer.save(user=self.request.user)
