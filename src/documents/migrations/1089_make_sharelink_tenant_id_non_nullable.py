# Migration to make tenant_id non-nullable after backfilling data

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1088_backfill_sharelink_tenant_id'),
    ]

    operations = [
        # Make tenant_id non-nullable for ShareLink
        migrations.AlterField(
            model_name='sharelink',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
    ]
