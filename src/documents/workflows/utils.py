from documents.models import Workflow
from documents.models import WorkflowTrigger


def get_workflows_for_trigger(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    workflow_to_run: Workflow | None = None,
):
    """
    Return workflows relevant to a trigger. If a specific workflow is given,
    wrap it in a list; otherwise fetch enabled workflows for the trigger with
    the prefetches used by the runner.
    """
    if workflow_to_run is not None:
        return [workflow_to_run]

    return (
        Workflow.objects.filter(enabled=True, triggers__type=trigger_type)
        .prefetch_related(
            "actions",
            "actions__assign_view_users",
            "actions__assign_view_groups",
            "actions__assign_change_users",
            "actions__assign_change_groups",
            "actions__assign_custom_fields",
            "actions__remove_tags",
            "actions__remove_correspondents",
            "actions__remove_document_types",
            "actions__remove_storage_paths",
            "actions__remove_custom_fields",
            "actions__remove_owners",
            "triggers",
        )
        .order_by("order")
        .distinct()
    )
