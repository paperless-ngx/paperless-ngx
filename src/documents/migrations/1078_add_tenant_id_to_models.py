# Generated migration to add tenant_id to all ModelWithOwner models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1077_create_tenant_model'),
    ]

    operations = [
        # Add tenant_id field to Correspondent
        migrations.AddField(
            model_name='correspondent',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to Tag
        migrations.AddField(
            model_name='tag',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to DocumentType
        migrations.AddField(
            model_name='documenttype',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to StoragePath
        migrations.AddField(
            model_name='storagepath',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to Document
        migrations.AddField(
            model_name='document',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to SavedView
        migrations.AddField(
            model_name='savedview',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add tenant_id field to PaperlessTask
        migrations.AddField(
            model_name='paperlesstask',
            name='tenant_id',
            field=models.UUIDField(db_index=True, null=True, verbose_name='tenant'),
        ),
        # Add indexes for Correspondent
        migrations.AddIndex(
            model_name='correspondent',
            index=models.Index(fields=['tenant_id'], name='documents_c_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='correspondent',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_c_tenant__owner_idx'),
        ),
        # Add indexes for Tag
        migrations.AddIndex(
            model_name='tag',
            index=models.Index(fields=['tenant_id'], name='documents_t_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='tag',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_t_tenant__owner_idx'),
        ),
        # Add indexes for DocumentType
        migrations.AddIndex(
            model_name='documenttype',
            index=models.Index(fields=['tenant_id'], name='documents_d_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='documenttype',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_d_tenant__owner_idx'),
        ),
        # Add indexes for StoragePath
        migrations.AddIndex(
            model_name='storagepath',
            index=models.Index(fields=['tenant_id'], name='documents_s_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='storagepath',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_s_tenant__owner_idx'),
        ),
        # Add indexes for Document
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['tenant_id'], name='documents_d_tenant__2_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_d_tenant__owner_2_idx'),
        ),
        # Add indexes for SavedView
        migrations.AddIndex(
            model_name='savedview',
            index=models.Index(fields=['tenant_id'], name='documents_s_tenant__2_idx'),
        ),
        migrations.AddIndex(
            model_name='savedview',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_s_tenant__owner_2_idx'),
        ),
        # Add indexes for PaperlessTask
        migrations.AddIndex(
            model_name='paperlesstask',
            index=models.Index(fields=['tenant_id'], name='documents_p_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='paperlesstask',
            index=models.Index(fields=['tenant_id', 'owner'], name='documents_p_tenant__owner_idx'),
        ),
    ]
