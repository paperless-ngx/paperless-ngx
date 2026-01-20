# Data migration to create default tenant and backfill all existing records

import uuid
from django.db import migrations


def create_default_tenant_and_backfill(apps, schema_editor):
    """
    Create a default tenant and assign all existing records to it.
    """
    # Get the Tenant model
    Tenant = apps.get_model('documents', 'Tenant')

    # Create default tenant if it doesn't exist
    default_tenant, created = Tenant.objects.get_or_create(
        subdomain='default',
        defaults={
            'name': 'Default Tenant',
            'region': 'us',
            'max_storage_gb': 10,
            'max_documents': 10000,
            'max_users': 10,
            'theme_color': '#17541f',
            'app_title': 'Paperless-ngx',
            'is_active': True,
        }
    )

    default_tenant_id = default_tenant.id

    # Get all models that inherit from ModelWithOwner
    Correspondent = apps.get_model('documents', 'Correspondent')
    Tag = apps.get_model('documents', 'Tag')
    DocumentType = apps.get_model('documents', 'DocumentType')
    StoragePath = apps.get_model('documents', 'StoragePath')
    Document = apps.get_model('documents', 'Document')
    SavedView = apps.get_model('documents', 'SavedView')
    PaperlessTask = apps.get_model('documents', 'PaperlessTask')

    # Backfill all existing records with the default tenant ID
    Correspondent.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    Tag.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    DocumentType.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    StoragePath.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    Document.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    SavedView.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)
    PaperlessTask.objects.filter(tenant_id__isnull=True).update(tenant_id=default_tenant_id)


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all tenant_id fields back to NULL.
    """
    Correspondent = apps.get_model('documents', 'Correspondent')
    Tag = apps.get_model('documents', 'Tag')
    DocumentType = apps.get_model('documents', 'DocumentType')
    StoragePath = apps.get_model('documents', 'StoragePath')
    Document = apps.get_model('documents', 'Document')
    SavedView = apps.get_model('documents', 'SavedView')
    PaperlessTask = apps.get_model('documents', 'PaperlessTask')

    # Set all tenant_id fields back to NULL
    Correspondent.objects.all().update(tenant_id=None)
    Tag.objects.all().update(tenant_id=None)
    DocumentType.objects.all().update(tenant_id=None)
    StoragePath.objects.all().update(tenant_id=None)
    Document.objects.all().update(tenant_id=None)
    SavedView.objects.all().update(tenant_id=None)
    PaperlessTask.objects.all().update(tenant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1078_add_tenant_id_to_models'),
    ]

    operations = [
        migrations.RunPython(
            create_default_tenant_and_backfill,
            reverse_backfill,
        ),
    ]
