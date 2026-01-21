# Migration to make tenant_id non-nullable for Workflow, WorkflowTrigger, and WorkflowAction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1096_backfill_workflow_tenant_id'),
    ]

    operations = [
        # Make Workflow.tenant_id non-nullable
        migrations.AlterField(
            model_name='workflow',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                verbose_name='tenant'
            ),
        ),

        # Make WorkflowTrigger.tenant_id non-nullable
        migrations.AlterField(
            model_name='workflowtrigger',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                verbose_name='tenant'
            ),
        ),

        # Make WorkflowAction.tenant_id non-nullable
        migrations.AlterField(
            model_name='workflowaction',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                verbose_name='tenant'
            ),
        ),
    ]
