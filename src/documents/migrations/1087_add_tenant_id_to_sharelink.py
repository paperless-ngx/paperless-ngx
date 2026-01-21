# Migration to add tenant_id field to ShareLink model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1082_migrate_classifier_to_tenant_specific'),
    ]

    operations = [
        # Add tenant_id field to ShareLink (nullable initially for data migration)
        migrations.AddField(
            model_name='sharelink',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add indexes for ShareLink
        migrations.AddIndex(
            model_name='sharelink',
            index=models.Index(fields=['tenant_id'], name='documents_sl_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='sharelink',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_sl_tenant__owner_idx'),
        ),
    ]
