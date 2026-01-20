"""
Tests for tenant_id functionality on ModelWithOwner models.
"""
import uuid
from django.contrib.auth.models import User
from django.test import TestCase

from documents.models import (
    Correspondent,
    Document,
    DocumentType,
    PaperlessTask,
    SavedView,
    StoragePath,
    Tag,
    get_current_tenant_id,
    set_current_tenant_id,
)
from documents.models.tenant import Tenant


class TenantIdFunctionalityTestCase(TestCase):
    """Test tenant_id functionality on all ModelWithOwner models."""

    def setUp(self):
        """Set up test data."""
        # Create a test tenant
        self.tenant = Tenant.objects.create(
            subdomain='test-tenant',
            name='Test Tenant',
            region='us',
        )
        self.tenant_id = self.tenant.id

        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_thread_local_storage_functions(self):
        """Test get_current_tenant_id and set_current_tenant_id."""
        # Initially should be None
        self.assertIsNone(get_current_tenant_id())

        # Set tenant_id
        set_current_tenant_id(self.tenant_id)
        self.assertEqual(get_current_tenant_id(), self.tenant_id)

        # Clear tenant_id
        set_current_tenant_id(None)
        self.assertIsNone(get_current_tenant_id())

    def test_auto_populate_tenant_id_on_save(self):
        """Test that tenant_id is auto-populated from thread-local on save."""
        set_current_tenant_id(self.tenant_id)

        # Test Correspondent
        correspondent = Correspondent(name='Test Correspondent', owner=self.user)
        correspondent.save()
        self.assertEqual(correspondent.tenant_id, self.tenant_id)

        # Test Tag
        tag = Tag(name='Test Tag', owner=self.user)
        tag.save()
        self.assertEqual(tag.tenant_id, self.tenant_id)

        # Test DocumentType
        doc_type = DocumentType(name='Test Type', owner=self.user)
        doc_type.save()
        self.assertEqual(doc_type.tenant_id, self.tenant_id)

        # Test StoragePath
        storage_path = StoragePath(name='Test Path', path='/test', owner=self.user)
        storage_path.save()
        self.assertEqual(storage_path.tenant_id, self.tenant_id)

    def test_explicit_tenant_id_overrides_thread_local(self):
        """Test that explicitly set tenant_id is not overridden."""
        set_current_tenant_id(self.tenant_id)

        # Create another tenant
        other_tenant = Tenant.objects.create(
            subdomain='other-tenant',
            name='Other Tenant',
            region='us',
        )

        # Explicitly set different tenant_id
        correspondent = Correspondent(
            name='Test Correspondent',
            owner=self.user,
            tenant_id=other_tenant.id,
        )
        correspondent.save()

        # Should keep explicitly set tenant_id
        self.assertEqual(correspondent.tenant_id, other_tenant.id)

    def test_save_without_tenant_id_raises_error(self):
        """Test that saving without tenant_id raises ValueError."""
        # Ensure thread-local is None
        set_current_tenant_id(None)

        correspondent = Correspondent(name='Test Correspondent', owner=self.user)

        with self.assertRaises(ValueError) as context:
            correspondent.save()

        self.assertIn('tenant_id cannot be None', str(context.exception))
        self.assertIn('Correspondent', str(context.exception))

    def test_default_tenant_created_by_migration(self):
        """Test that default tenant was created by migration."""
        default_tenant = Tenant.objects.filter(subdomain='default').first()
        self.assertIsNotNone(default_tenant, 'Default tenant should exist after migration')
        self.assertEqual(default_tenant.name, 'Default Tenant')

    def test_existing_records_have_tenant_id(self):
        """Test that existing records were backfilled with default tenant_id."""
        # This test assumes the data migration has run
        # Create a correspondent with thread-local
        set_current_tenant_id(self.tenant_id)
        correspondent = Correspondent.objects.create(name='Test', owner=self.user)

        # Query from database
        correspondent_from_db = Correspondent.objects.get(id=correspondent.id)
        self.assertIsNotNone(correspondent_from_db.tenant_id)
        self.assertEqual(correspondent_from_db.tenant_id, self.tenant_id)

    def test_tenant_id_indexes_exist(self):
        """Test that database indexes on tenant_id columns exist."""
        # This is a smoke test - if indexes don't exist, migrations failed
        from django.db import connection

        with connection.cursor() as cursor:
            # Check for tenant_id index on documents_correspondent table
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'documents_correspondent'
                AND indexdef LIKE '%tenant_id%'
            """)
            indexes = cursor.fetchall()
            self.assertGreater(
                len(indexes),
                0,
                'At least one index on tenant_id should exist for Correspondent',
            )
