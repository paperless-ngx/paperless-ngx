from mcp_server import ModelQueryToolset
from mcp_server import drf_publish_create_mcp_tool
from mcp_server import drf_publish_destroy_mcp_tool
from mcp_server import drf_publish_list_mcp_tool
from mcp_server import drf_publish_update_mcp_tool

from documents.permissions import get_objects_for_user_owner_aware
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.views import MailAccountViewSet
from paperless_mail.views import MailRuleViewSet
from paperless_mail.views import ProcessedMailViewSet

VIEWSET_ACTIONS = {
    "create": {"post": "create"},
    "list": {"get": "list"},
    "update": {"put": "update"},
    "destroy": {"delete": "destroy"},
}

BODY_SCHEMA = {"type": "object", "additionalProperties": True}

VIEWSET_INSTRUCTIONS = {
    MailAccountViewSet: "Manage mail accounts.",
    MailRuleViewSet: "Manage mail rules.",
    ProcessedMailViewSet: "List processed mail.",
}


class MailAccountQueryToolset(ModelQueryToolset):
    model = MailAccount

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return MailAccount.objects.none()
        if user.is_superuser:
            return MailAccount.objects.all()
        return get_objects_for_user_owner_aware(
            user,
            "paperless_mail.view_mailaccount",
            MailAccount,
        )


class MailRuleQueryToolset(ModelQueryToolset):
    model = MailRule

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return MailRule.objects.none()
        if user.is_superuser:
            return MailRule.objects.all()
        return get_objects_for_user_owner_aware(
            user,
            "paperless_mail.view_mailrule",
            MailRule,
        )


class ProcessedMailQueryToolset(ModelQueryToolset):
    model = ProcessedMail

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return ProcessedMail.objects.none()
        if user.is_superuser:
            return ProcessedMail.objects.all()
        return get_objects_for_user_owner_aware(
            user,
            "paperless_mail.view_processedmail",
            ProcessedMail,
        )


drf_publish_create_mcp_tool(
    MailAccountViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[MailAccountViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    MailAccountViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[MailAccountViewSet],
)
drf_publish_update_mcp_tool(
    MailAccountViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[MailAccountViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    MailAccountViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[MailAccountViewSet],
)

drf_publish_create_mcp_tool(
    MailRuleViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[MailRuleViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    MailRuleViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[MailRuleViewSet],
)
drf_publish_update_mcp_tool(
    MailRuleViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[MailRuleViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    MailRuleViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[MailRuleViewSet],
)

drf_publish_list_mcp_tool(
    ProcessedMailViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[ProcessedMailViewSet],
)
