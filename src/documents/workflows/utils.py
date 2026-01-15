import logging

from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Prefetch

from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger

logger = logging.getLogger("paperless.workflows")


def get_workflows_for_trigger(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    workflow_to_run: Workflow | None = None,
):
    """
    Return workflows relevant to a trigger. If a specific workflow is given,
    wrap it in a list; otherwise fetch enabled workflows for the trigger with
    the prefetches used by the runner.
    """
    annotated_actions = (
        WorkflowAction.objects.select_related(
            "assign_correspondent",
            "assign_document_type",
            "assign_storage_path",
            "assign_owner",
            "email",
            "webhook",
        )
        .prefetch_related(
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
        )
        .annotate(
            has_assign_tags=Exists(
                WorkflowAction.assign_tags.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_assign_view_users=Exists(
                WorkflowAction.assign_view_users.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_assign_view_groups=Exists(
                WorkflowAction.assign_view_groups.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_assign_change_users=Exists(
                WorkflowAction.assign_change_users.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_assign_change_groups=Exists(
                WorkflowAction.assign_change_groups.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_assign_custom_fields=Exists(
                WorkflowAction.assign_custom_fields.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_remove_view_users=Exists(
                WorkflowAction.remove_view_users.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_remove_view_groups=Exists(
                WorkflowAction.remove_view_groups.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_remove_change_users=Exists(
                WorkflowAction.remove_change_users.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_remove_change_groups=Exists(
                WorkflowAction.remove_change_groups.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
            has_remove_custom_fields=Exists(
                WorkflowAction.remove_custom_fields.through.objects.filter(
                    workflowaction_id=OuterRef("pk"),
                ),
            ),
        )
    )

    action_prefetch = Prefetch(
        "actions",
        queryset=annotated_actions.order_by("order", "pk"),
    )

    if workflow_to_run is not None:
        return (
            Workflow.objects.filter(pk=workflow_to_run.pk)
            .prefetch_related(
                action_prefetch,
                "triggers",
            )
            .distinct()
        )

    return (
        Workflow.objects.filter(enabled=True, triggers__type=trigger_type)
        .prefetch_related(
            action_prefetch,
            "triggers",
        )
        .order_by("order")
        .distinct()
    )
