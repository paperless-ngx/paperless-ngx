from __future__ import annotations

from django.db.models import Q
from django.http import QueryDict
from mcp_server import MCPToolset
from mcp_server import ModelQueryToolset
from mcp_server import drf_publish_create_mcp_tool
from mcp_server import drf_publish_destroy_mcp_tool
from mcp_server import drf_publish_list_mcp_tool
from mcp_server import drf_publish_update_mcp_tool
from rest_framework.response import Response

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import SavedView
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.permissions import get_objects_for_user_owner_aware
from documents.views import CorrespondentViewSet
from documents.views import CustomFieldViewSet
from documents.views import DocumentTypeViewSet
from documents.views import SavedViewViewSet
from documents.views import ShareLinkViewSet
from documents.views import StoragePathViewSet
from documents.views import TagViewSet
from documents.views import TasksViewSet
from documents.views import UnifiedSearchViewSet
from documents.views import WorkflowActionViewSet
from documents.views import WorkflowTriggerViewSet
from documents.views import WorkflowViewSet

VIEWSET_ACTIONS = {
    "create": {"post": "create"},
    "list": {"get": "list"},
    "update": {"put": "update"},
    "destroy": {"delete": "destroy"},
}

BODY_SCHEMA = {"type": "object", "additionalProperties": True}

VIEWSET_INSTRUCTIONS = {
    CorrespondentViewSet: "Manage correspondents.",
    TagViewSet: "Manage tags.",
    UnifiedSearchViewSet: "Search and manage documents.",
    DocumentTypeViewSet: "Manage document types.",
    StoragePathViewSet: "Manage storage paths.",
    SavedViewViewSet: "Manage saved views.",
    ShareLinkViewSet: "Manage share links.",
    WorkflowTriggerViewSet: "Manage workflow triggers.",
    WorkflowActionViewSet: "Manage workflow actions.",
    WorkflowViewSet: "Manage workflows.",
    CustomFieldViewSet: "Manage custom fields.",
    TasksViewSet: "List background tasks.",
}


class OwnerAwareQueryToolsetMixin:
    permission: str

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return self.model.objects.none()
        if user.is_superuser:
            return self.model._default_manager.all()
        return get_objects_for_user_owner_aware(user, self.permission, self.model)


class DocumentQueryToolset(ModelQueryToolset):
    model = Document
    search_fields = ["title", "content"]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return Document.objects.none()
        if user.is_superuser:
            return Document.objects.all()
        return get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        )


class CorrespondentQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = Correspondent
    permission = "documents.view_correspondent"


class TagQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = Tag
    permission = "documents.view_tag"


class DocumentTypeQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = DocumentType
    permission = "documents.view_documenttype"


class StoragePathQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = StoragePath
    permission = "documents.view_storagepath"


class SavedViewQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = SavedView
    permission = "documents.view_savedview"


class ShareLinkQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = ShareLink
    permission = "documents.view_sharelink"


class WorkflowTriggerQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = WorkflowTrigger
    permission = "documents.view_workflowtrigger"


class WorkflowActionQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = WorkflowAction
    permission = "documents.view_workflowaction"


class WorkflowQueryToolset(OwnerAwareQueryToolsetMixin, ModelQueryToolset):
    model = Workflow
    permission = "documents.view_workflow"


class NoteQueryToolset(ModelQueryToolset):
    model = Note

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return Note.objects.none()
        if user.is_superuser:
            return Note.objects.all()
        return Note.objects.filter(
            document__in=get_objects_for_user_owner_aware(
                user,
                "documents.view_document",
                Document,
            ),
        )


class CustomFieldQueryToolset(ModelQueryToolset):
    model = CustomField

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        base = CustomField.objects.all()
        if not user or not user.is_authenticated:
            return base.none()
        if user.is_superuser:
            return base
        return base.filter(
            Q(
                fields__document__id__in=get_objects_for_user_owner_aware(
                    user,
                    "documents.view_document",
                    Document,
                ),
            )
            | Q(fields__document__isnull=True),
        ).distinct()


class DocumentSearchTools(MCPToolset):
    def search_documents(
        self,
        query: str | None = None,
        more_like_id: int | None = None,
        fields: list[str] | None = None,
        page: int | None = None,
        page_size: int | None = None,
        *,
        full_perms: bool | None = None,
    ) -> dict:
        """Search documents using the full-text index."""
        if not query and not more_like_id:
            raise ValueError("Provide either query or more_like_id.")

        request = self.request
        if request is None:
            raise ValueError("Request context is required.")

        viewset = UnifiedSearchViewSet()
        viewset.request = request
        viewset.args = ()
        viewset.kwargs = {}
        viewset.action = "list"
        viewset.format_kwarg = None
        viewset.check_permissions(request)

        query_params = QueryDict(mutable=True)
        if query:
            query_params["query"] = query
        if more_like_id:
            query_params["more_like_id"] = str(more_like_id)
        if full_perms is not None:
            query_params["full_perms"] = str(full_perms).lower()
        if page:
            query_params["page"] = str(page)
        if page_size:
            query_params["page_size"] = str(page_size)
        if fields:
            query_params.setlist("fields", fields)

        request._request.GET = query_params
        response = viewset.list(request)
        if isinstance(response, Response):
            return response.data
        if hasattr(response, "data"):
            return response.data
        return {
            "detail": getattr(response, "content", b"").decode() or "Search failed.",
        }


drf_publish_create_mcp_tool(
    CorrespondentViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[CorrespondentViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    CorrespondentViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[CorrespondentViewSet],
)
drf_publish_update_mcp_tool(
    CorrespondentViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[CorrespondentViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    CorrespondentViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[CorrespondentViewSet],
)

drf_publish_create_mcp_tool(
    TagViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[TagViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    TagViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[TagViewSet],
)
drf_publish_update_mcp_tool(
    TagViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[TagViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    TagViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[TagViewSet],
)

drf_publish_list_mcp_tool(
    UnifiedSearchViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[UnifiedSearchViewSet],
)
drf_publish_update_mcp_tool(
    UnifiedSearchViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[UnifiedSearchViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    UnifiedSearchViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[UnifiedSearchViewSet],
)

drf_publish_create_mcp_tool(
    DocumentTypeViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[DocumentTypeViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    DocumentTypeViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[DocumentTypeViewSet],
)
drf_publish_update_mcp_tool(
    DocumentTypeViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[DocumentTypeViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    DocumentTypeViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[DocumentTypeViewSet],
)

drf_publish_create_mcp_tool(
    StoragePathViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[StoragePathViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    StoragePathViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[StoragePathViewSet],
)
drf_publish_update_mcp_tool(
    StoragePathViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[StoragePathViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    StoragePathViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[StoragePathViewSet],
)

drf_publish_create_mcp_tool(
    SavedViewViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[SavedViewViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    SavedViewViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[SavedViewViewSet],
)
drf_publish_update_mcp_tool(
    SavedViewViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[SavedViewViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    SavedViewViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[SavedViewViewSet],
)

drf_publish_create_mcp_tool(
    ShareLinkViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[ShareLinkViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    ShareLinkViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[ShareLinkViewSet],
)
drf_publish_update_mcp_tool(
    ShareLinkViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[ShareLinkViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    ShareLinkViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[ShareLinkViewSet],
)

drf_publish_create_mcp_tool(
    WorkflowTriggerViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowTriggerViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    WorkflowTriggerViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowTriggerViewSet],
)
drf_publish_update_mcp_tool(
    WorkflowTriggerViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowTriggerViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    WorkflowTriggerViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowTriggerViewSet],
)

drf_publish_create_mcp_tool(
    WorkflowActionViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowActionViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    WorkflowActionViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowActionViewSet],
)
drf_publish_update_mcp_tool(
    WorkflowActionViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowActionViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    WorkflowActionViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowActionViewSet],
)

drf_publish_create_mcp_tool(
    WorkflowViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    WorkflowViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowViewSet],
)
drf_publish_update_mcp_tool(
    WorkflowViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    WorkflowViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[WorkflowViewSet],
)

drf_publish_create_mcp_tool(
    CustomFieldViewSet,
    actions=VIEWSET_ACTIONS["create"],
    instructions=VIEWSET_INSTRUCTIONS[CustomFieldViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_list_mcp_tool(
    CustomFieldViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[CustomFieldViewSet],
)
drf_publish_update_mcp_tool(
    CustomFieldViewSet,
    actions=VIEWSET_ACTIONS["update"],
    instructions=VIEWSET_INSTRUCTIONS[CustomFieldViewSet],
    body_schema=BODY_SCHEMA,
)
drf_publish_destroy_mcp_tool(
    CustomFieldViewSet,
    actions=VIEWSET_ACTIONS["destroy"],
    instructions=VIEWSET_INSTRUCTIONS[CustomFieldViewSet],
)

drf_publish_list_mcp_tool(
    TasksViewSet,
    actions=VIEWSET_ACTIONS["list"],
    instructions=VIEWSET_INSTRUCTIONS[TasksViewSet],
)
