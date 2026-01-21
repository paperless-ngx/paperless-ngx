# Migration to make tenant_id non-nullable after backfilling data

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1079_create_default_tenant_and_backfill'),
    ]

    operations = [
        # Make tenant_id non-nullable for Correspondent
        migrations.AlterField(
            model_name='correspondent',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for Tag
        migrations.AlterField(
            model_name='tag',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for DocumentType
        migrations.AlterField(
            model_name='documenttype',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for StoragePath
        migrations.AlterField(
            model_name='storagepath',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for Document
        migrations.AlterField(
            model_name='document',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for SavedView
        migrations.AlterField(
            model_name='savedview',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
        # Make tenant_id non-nullable for PaperlessTask
        migrations.AlterField(
            model_name='paperlesstask',
            name='tenant_id',
            field=models.UUIDField(db_index=True, verbose_name='tenant'),
        ),
    ]
