# Migration to add tenant_id field to Workflow, WorkflowTrigger, and WorkflowAction models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1094_add_rls_policy_for_customfield'),
    ]

    operations = [
        # Add tenant_id field to Workflow (nullable initially for data migration)
        migrations.AddField(
            model_name='workflow',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add owner field to Workflow (nullable, inherits from ModelWithOwner)
        migrations.AddField(
            model_name='workflow',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                default=None,
                on_delete=models.deletion.SET_NULL,
                to='auth.user',
                verbose_name='owner',
            ),
        ),

        # Add tenant_id field to WorkflowTrigger (nullable initially for data migration)
        migrations.AddField(
            model_name='workflowtrigger',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add owner field to WorkflowTrigger (nullable, inherits from ModelWithOwner)
        migrations.AddField(
            model_name='workflowtrigger',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                default=None,
                on_delete=models.deletion.SET_NULL,
                to='auth.user',
                verbose_name='owner',
            ),
        ),

        # Add tenant_id field to WorkflowAction (nullable initially for data migration)
        migrations.AddField(
            model_name='workflowaction',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add owner field to WorkflowAction (nullable, inherits from ModelWithOwner)
        migrations.AddField(
            model_name='workflowaction',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                default=None,
                on_delete=models.deletion.SET_NULL,
                to='auth.user',
                verbose_name='owner',
            ),
        ),

        # Add indexes for Workflow
        migrations.AddIndex(
            model_name='workflow',
            index=models.Index(fields=['tenant_id'], name='documents_wf_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='workflow',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_wf_tenant__owner_idx'),
        ),

        # Add indexes for WorkflowTrigger
        migrations.AddIndex(
            model_name='workflowtrigger',
            index=models.Index(fields=['tenant_id'], name='documents_wft_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='workflowtrigger',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_wft_tenant__owner_idx'),
        ),

        # Add indexes for WorkflowAction
        migrations.AddIndex(
            model_name='workflowaction',
            index=models.Index(fields=['tenant_id'], name='documents_wfa_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='workflowaction',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_wfa_tenant__owner_idx'),
        ),
    ]
