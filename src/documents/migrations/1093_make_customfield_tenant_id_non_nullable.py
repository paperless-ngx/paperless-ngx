# Migration to make CustomField.tenant_id non-nullable

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1092_backfill_customfield_tenant_id'),
    ]

    operations = [
        # Make tenant_id field non-nullable
        migrations.AlterField(
            model_name='customfield',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                verbose_name='tenant'
            ),
        ),
    ]
