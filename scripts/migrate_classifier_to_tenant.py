#!/usr/bin/env python3
"""
Standalone script to migrate shared classifier models to per-tenant locations.

This script should be run after the tenant-aware classifier code is deployed.
It copies the existing shared classifier.pkl file to each tenant's directory.
"""

import os
import shutil
import sys
from pathlib import Path

# Add Django project to path
sys.path.insert(0, '/usr/src/paperless/src')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
import django
django.setup()

from django.conf import settings
from documents.models import Tenant

def migrate_classifier_models():
    """
    Copy the shared classifier model to each tenant's directory.
    """
    # Get the shared model file path
    shared_model_file = settings.MODEL_FILE

    if not shared_model_file.is_file():
        print("No shared classifier model found. Migration not needed.")
        return 0

    print(f"Found shared classifier model at: {shared_model_file}")

    # Get all active tenants
    tenants = Tenant.objects.filter(is_active=True)

    if tenants.count() == 0:
        print("No active tenants found. Migration not needed.")
        return 0

    success_count = 0
    error_count = 0

    # Copy to each tenant's directory
    for tenant in tenants:
        try:
            tenant_dir = settings.MEDIA_ROOT / f"tenant_{tenant.id}"
            tenant_dir.mkdir(parents=True, exist_ok=True)

            tenant_model_file = tenant_dir / "classifier.pkl"

            # Only copy if tenant doesn't already have a model
            if not tenant_model_file.exists():
                shutil.copy2(shared_model_file, tenant_model_file)
                print(f"✓ Copied classifier model to tenant {tenant.name} ({tenant.id})")
                print(f"  Path: {tenant_model_file}")
                success_count += 1
            else:
                print(f"✓ Tenant {tenant.name} ({tenant.id}) already has a classifier model.")
                success_count += 1
        except Exception as e:
            print(f"✗ Error migrating classifier for tenant {tenant.name} ({tenant.id}): {e}")
            error_count += 1

    # Optionally rename the shared model file to .backup
    if success_count > 0:
        backup_file = shared_model_file.with_suffix('.pickle.backup')
        if not backup_file.exists():
            try:
                shutil.move(str(shared_model_file), str(backup_file))
                print(f"\n✓ Backed up shared model to: {backup_file}")
            except Exception as e:
                print(f"\n✗ Error backing up shared model: {e}")

    print(f"\nMigration complete: {success_count} successful, {error_count} errors")
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(migrate_classifier_models())
