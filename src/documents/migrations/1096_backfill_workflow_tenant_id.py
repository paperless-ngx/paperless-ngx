# Data migration to populate tenant_id for Workflow, WorkflowTrigger, and WorkflowAction

from django.db import migrations


def backfill_workflow_tenant_id(apps, schema_editor):
    """
    Populate tenant_id for Workflow, WorkflowTrigger, and WorkflowAction.

    Strategy:
    1. For Workflows: Get tenant_id from first related document through WorkflowRun
    2. For WorkflowTriggers: Get tenant_id from related Workflows (M2M relationship)
    3. For WorkflowActions: Get tenant_id from related Workflows (M2M relationship)

    If no related objects exist, use a default tenant_id from any existing document.
    """
    import uuid
    Workflow = apps.get_model('documents', 'Workflow')
    WorkflowTrigger = apps.get_model('documents', 'WorkflowTrigger')
    WorkflowAction = apps.get_model('documents', 'WorkflowAction')
    WorkflowRun = apps.get_model('documents', 'WorkflowRun')
    Document = apps.get_model('documents', 'Document')

    # Get a default tenant_id from any existing document
    first_doc = Document.objects.first()
    if not first_doc or not hasattr(first_doc, 'tenant_id') or not first_doc.tenant_id:
        # If no documents exist or they don't have tenant_id, use a placeholder
        default_tenant_id = uuid.uuid4()
    else:
        default_tenant_id = first_doc.tenant_id

    # Step 1: Backfill Workflow tenant_id
    workflows = Workflow.objects.filter(tenant_id__isnull=True)
    for workflow in workflows:
        # Try to get tenant_id from first related WorkflowRun's document
        first_run = WorkflowRun.objects.filter(workflow=workflow).select_related('document').first()

        if first_run and first_run.document and hasattr(first_run.document, 'tenant_id') and first_run.document.tenant_id:
            workflow.tenant_id = first_run.document.tenant_id
        else:
            # No runs yet or document doesn't have tenant_id, use default
            workflow.tenant_id = default_tenant_id

        workflow.save(update_fields=['tenant_id'])

    # Step 2: Backfill WorkflowTrigger tenant_id from related Workflows
    triggers = WorkflowTrigger.objects.filter(tenant_id__isnull=True)
    for trigger in triggers:
        # Get tenant_id from first related Workflow
        first_workflow = trigger.workflows.first()

        if first_workflow and hasattr(first_workflow, 'tenant_id') and first_workflow.tenant_id:
            trigger.tenant_id = first_workflow.tenant_id
        else:
            # No related workflow, use default
            trigger.tenant_id = default_tenant_id

        trigger.save(update_fields=['tenant_id'])

    # Step 3: Backfill WorkflowAction tenant_id from related Workflows
    actions = WorkflowAction.objects.filter(tenant_id__isnull=True)
    for action in actions:
        # Get tenant_id from first related Workflow
        first_workflow = action.workflows.first()

        if first_workflow and hasattr(first_workflow, 'tenant_id') and first_workflow.tenant_id:
            action.tenant_id = first_workflow.tenant_id
        else:
            # No related workflow, use default
            action.tenant_id = default_tenant_id

        action.save(update_fields=['tenant_id'])


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all tenant_id fields back to NULL.
    """
    Workflow = apps.get_model('documents', 'Workflow')
    WorkflowTrigger = apps.get_model('documents', 'WorkflowTrigger')
    WorkflowAction = apps.get_model('documents', 'WorkflowAction')

    Workflow.objects.all().update(tenant_id=None)
    WorkflowTrigger.objects.all().update(tenant_id=None)
    WorkflowAction.objects.all().update(tenant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1095_add_tenant_id_to_workflow_models'),
    ]

    operations = [
        migrations.RunPython(
            backfill_workflow_tenant_id,
            reverse_backfill,
        ),
    ]
