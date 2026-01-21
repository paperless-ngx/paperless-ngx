# Migration to add tenant_id field to Note model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1083_create_tenant_group'),
    ]

    operations = [
        # Add tenant_id field to Note (nullable initially for data migration)
        migrations.AddField(
            model_name='note',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Add owner field to Note if not already present (from ModelWithOwner)
        # Note: This may already exist if user field serves this purpose
        # But ModelWithOwner expects an 'owner' field specifically
    ]
