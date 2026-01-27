from mcp_server import drf_publish_create_mcp_tool
from mcp_server import drf_publish_destroy_mcp_tool
from mcp_server import drf_publish_list_mcp_tool
from mcp_server import drf_publish_update_mcp_tool

from paperless.views import ApplicationConfigurationViewSet
from paperless.views import GroupViewSet
from paperless.views import UserViewSet

VIEWSET_ACTIONS = {
    "create": {"post": "create"},
    "list": {"get": "list"},
    "update": {"put": "update"},
    "destroy": {"delete": "destroy"},
}

BODY_SCHEMA = {"type": "object", "additionalProperties": True}

VIEWSET_INSTRUCTIONS = {
    UserViewSet: "Manage Paperless users.",
    GroupViewSet: "Manage Paperless groups.",
    ApplicationConfigurationViewSet: "Manage application configuration.",
}


drf_publish_create_mcp_tool(
    UserViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[UserViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    UserViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[UserViewSet],
)
drf_publish_update_mcp_tool(
    UserViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[UserViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    UserViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[UserViewSet],
)

drf_publish_create_mcp_tool(
    GroupViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[GroupViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    GroupViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[GroupViewSet],
)
drf_publish_update_mcp_tool(
    GroupViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[GroupViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    GroupViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[GroupViewSet],
)

drf_publish_list_mcp_tool(
    ApplicationConfigurationViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[ApplicationConfigurationViewSet],
)
drf_publish_update_mcp_tool(
    ApplicationConfigurationViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[ApplicationConfigurationViewSet],
    body_schema=BODY_SCHEMA,
)
