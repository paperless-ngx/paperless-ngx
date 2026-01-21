#!/usr/bin/env python3
"""
Standalone script to migrate shared classifier models to per-tenant locations.

This script should be run after the tenant-aware classifier code is deployed.
It copies the existing shared classifier.pkl file to each tenant's directory.
"""

import logging
import os
import shutil
import sys
from pathlib import Path

# Configure logging for security audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('classifier_migration')

# Add Django project to path - use environment variable for flexibility
django_src_path = os.environ.get('DJANGO_SRC_PATH', '/usr/src/paperless/src')
sys.path.insert(0, django_src_path)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
import django
django.setup()

from django.conf import settings
from paperless.models import Tenant

def migrate_classifier_models():
    """
    Copy the shared classifier model to each tenant's directory.
    """
    logger.info("Starting classifier model migration to per-tenant locations")

    # Get the shared model file path
    shared_model_file = settings.MODEL_FILE

    if not shared_model_file.is_file():
        logger.info("No shared classifier model found. Migration not needed.")
        print("No shared classifier model found. Migration not needed.")
        return 0

    logger.info(f"Found shared classifier model at: {shared_model_file}")
    print(f"Found shared classifier model at: {shared_model_file}")

    # Get all active tenants
    tenants = Tenant.objects.filter(is_active=True)

    if tenants.count() == 0:
        logger.info("No active tenants found. Migration not needed.")
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
                logger.info(f"Migrated classifier model for tenant {tenant.name} (ID: {tenant.id}) to {tenant_model_file}")
                print(f"✓ Copied classifier model to tenant {tenant.name} ({tenant.id})")
                print(f"  Path: {tenant_model_file}")
                success_count += 1
            else:
                logger.info(f"Tenant {tenant.name} (ID: {tenant.id}) already has a classifier model at {tenant_model_file}")
                print(f"✓ Tenant {tenant.name} ({tenant.id}) already has a classifier model.")
                success_count += 1
        except PermissionError as e:
            logger.error(f"Permission denied migrating classifier for tenant {tenant.name} (ID: {tenant.id}): {e}", exc_info=True)
            print(f"✗ Permission denied for tenant {tenant.name} ({tenant.id}): {e}")
            error_count += 1
        except OSError as e:
            logger.error(f"I/O error migrating classifier for tenant {tenant.name} (ID: {tenant.id}): {e}", exc_info=True)
            print(f"✗ I/O error for tenant {tenant.name} ({tenant.id}): {e}")
            error_count += 1
        except Exception as e:
            logger.error(f"Unexpected error migrating classifier for tenant {tenant.name} (ID: {tenant.id}): {e}", exc_info=True)
            print(f"✗ Error migrating classifier for tenant {tenant.name} ({tenant.id}): {e}")
            error_count += 1

    # Optionally rename the shared model file to .backup
    if success_count > 0:
        backup_file = shared_model_file.with_suffix('.pickle.backup')
        if not backup_file.exists():
            try:
                shutil.move(str(shared_model_file), str(backup_file))
                logger.info(f"Backed up shared model to: {backup_file}")
                print(f"\n✓ Backed up shared model to: {backup_file}")
            except PermissionError as e:
                logger.error(f"Permission denied backing up shared model: {e}", exc_info=True)
                print(f"\n✗ Permission denied backing up shared model: {e}")
            except Exception as e:
                logger.error(f"Error backing up shared model: {e}", exc_info=True)
                print(f"\n✗ Error backing up shared model: {e}")

    logger.info(f"Migration complete: {success_count} successful, {error_count} errors")
    print(f"\nMigration complete: {success_count} successful, {error_count} errors")
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(migrate_classifier_models())
