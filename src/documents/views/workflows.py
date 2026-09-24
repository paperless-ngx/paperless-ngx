from django.db.models import Prefetch
from django.http import HttpResponseBadRequest
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.permissions import PaperlessObjectPermissions
from documents.serialisers.workflows import WorkflowActionSerializer
from documents.serialisers.workflows import WorkflowSerializer
from documents.serialisers.workflows import WorkflowTriggerSerializer
from paperless.views import StandardPagination


class WorkflowTriggerViewSet(ModelViewSet[WorkflowTrigger]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowTriggerSerializer
    pagination_class = StandardPagination

    model = WorkflowTrigger

    queryset = WorkflowTrigger.objects.all()

    def partial_update(self, request, *args, **kwargs):
        if "id" in request.data and str(request.data["id"]) != str(kwargs["pk"]):
            return HttpResponseBadRequest(
                "ID in body does not match URL",
            )
        return super().partial_update(request, *args, **kwargs)


class WorkflowActionViewSet(ModelViewSet[WorkflowAction]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowActionSerializer
    pagination_class = StandardPagination

    model = WorkflowAction

    queryset = WorkflowAction.objects.all().prefetch_related(
        "assign_tags",
        "assign_view_users",
        "assign_view_groups",
        "assign_change_users",
        "assign_change_groups",
        "assign_custom_fields",
    )

    def partial_update(self, request, *args, **kwargs):
        if "id" in request.data and str(request.data["id"]) != str(kwargs["pk"]):
            return HttpResponseBadRequest(
                "ID in body does not match URL",
            )
        return super().partial_update(request, *args, **kwargs)


class WorkflowViewSet(ModelViewSet[Workflow]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowSerializer
    pagination_class = StandardPagination

    model = Workflow

    queryset = (
        Workflow.objects.all()
        .order_by("order")
        .prefetch_related(
            Prefetch(
                "triggers",
                queryset=WorkflowTrigger.objects.prefetch_related(
                    "filter_has_tags",
                    "filter_has_all_tags",
                    "filter_has_not_tags",
                    "filter_has_any_correspondents",
                    "filter_has_not_correspondents",
                    "filter_has_any_document_types",
                    "filter_has_not_document_types",
                    "filter_has_any_storage_paths",
                    "filter_has_not_storage_paths",
                ),
            ),
            Prefetch(
                "actions",
                queryset=WorkflowAction.objects.order_by(
                    "order",
                    "pk",
                ).prefetch_related(
                    "assign_tags",
                    "assign_view_users",
                    "assign_view_groups",
                    "assign_change_users",
                    "assign_change_groups",
                    "assign_custom_fields",
                    "remove_tags",
                    "remove_correspondents",
                    "remove_document_types",
                    "remove_storage_paths",
                    "remove_custom_fields",
                    "remove_owners",
                    "remove_view_users",
                    "remove_view_groups",
                    "remove_change_users",
                    "remove_change_groups",
                ),
            ),
        )
    )
