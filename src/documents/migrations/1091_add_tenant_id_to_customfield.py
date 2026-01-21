# Migration to add tenant_id field to CustomField model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1082_migrate_classifier_to_tenant_specific'),
    ]

    operations = [
        # Add tenant_id field to CustomField (nullable initially for data migration)
        migrations.AddField(
            model_name='customfield',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add owner field to CustomField (nullable, inherits from ModelWithOwner)
        migrations.AddField(
            model_name='customfield',
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
        # Add indexes for CustomField
        migrations.AddIndex(
            model_name='customfield',
            index=models.Index(fields=['tenant_id'], name='documents_cf_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='customfield',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_cf_tenant__owner_idx'),
        ),
    ]
