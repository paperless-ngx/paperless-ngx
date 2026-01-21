# Generated migration for multi-tenant classifier model isolation

import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations


def migrate_classifier_models_to_tenant_specific(apps, schema_editor):
    """
    Migrate existing shared classifier model to per-tenant locations.

    This migration:
    1. Finds the existing shared classifier model file
    2. Copies it to each tenant's directory
    3. Logs the migration for audit purposes
    """
    Tenant = apps.get_model('paperless', 'Tenant')

    # Check if shared model file exists
    shared_model_file = settings.MODEL_FILE

    if not shared_model_file.is_file():
        # No existing model to migrate
        return

    # Get all active tenants
    tenants = Tenant.objects.filter(is_active=True)

    for tenant in tenants:
        # Create tenant-specific directory
        tenant_dir = settings.MEDIA_ROOT / f"tenant_{tenant.id}"
        tenant_dir.mkdir(parents=True, exist_ok=True)

        # Copy shared model to tenant-specific location
        tenant_model_file = tenant_dir / "classifier.pkl"

        if not tenant_model_file.exists():
            shutil.copy2(shared_model_file, tenant_model_file)
            print(f"Migrated classifier model for tenant {tenant.name} ({tenant.id}) to {tenant_model_file}")

    # Rename the shared model file to preserve it as backup
    if shared_model_file.exists():
        backup_file = shared_model_file.with_suffix('.pickle.pre_tenant_migration')
        if not backup_file.exists():
            shutil.move(str(shared_model_file), str(backup_file))
            print(f"Backed up shared classifier model to {backup_file}")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration by restoring the shared model file.

    Note: This will restore the backup but won't delete tenant-specific models,
    as they may have been updated since migration.
    """
    shared_model_file = settings.MODEL_FILE
    backup_file = shared_model_file.with_suffix('.pickle.pre_tenant_migration')

    if backup_file.exists() and not shared_model_file.exists():
        shutil.move(str(backup_file), str(shared_model_file))
        print(f"Restored shared classifier model from backup")


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1081_enable_row_level_security'),
    ]

    operations = [
        migrations.RunPython(
            migrate_classifier_models_to_tenant_specific,
            reverse_code=reverse_migration,
        ),
    ]
