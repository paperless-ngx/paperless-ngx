"""
Tests for tenant context restoration in Celery tasks.
"""
import uuid
from unittest import mock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from documents import tasks
from documents.models import (
    Correspondent,
    Document,
    DocumentType,
    Tag,
    get_current_tenant_id,
    set_current_tenant_id,
)
from paperless.models import Tenant


class TenantContextRestorationTestCase(TransactionTestCase):
    """Test tenant context restoration for Celery tasks."""

    def setUp(self):
        """Set up test data."""
        # Create test tenants
        self.tenant1 = Tenant.objects.create(
            subdomain='tenant1',
            name='Tenant 1',
            region='us',
        )
        self.tenant2 = Tenant.objects.create(
            subdomain='tenant2',
            name='Tenant 2',
            region='us',
        )

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_restore_tenant_context(self):
        """Test restore_tenant_context helper function."""
        # Initially should be None
        self.assertIsNone(get_current_tenant_id())

        # Restore tenant1 context
        tasks.restore_tenant_context(str(self.tenant1.id))
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

        # Restore tenant2 context
        tasks.restore_tenant_context(str(self.tenant2.id))
        self.assertEqual(get_current_tenant_id(), self.tenant2.id)

        # Clear context
        set_current_tenant_id(None)
        self.assertIsNone(get_current_tenant_id())

    def test_restore_tenant_context_with_uuid(self):
        """Test restore_tenant_context with UUID object."""
        tasks.restore_tenant_context(self.tenant1.id)
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

    def test_restore_tenant_context_with_none(self):
        """Test restore_tenant_context with None."""
        set_current_tenant_id(self.tenant1.id)
        tasks.restore_tenant_context(None)
        # Should log warning but not crash
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

    @mock.patch('documents.tasks.Document.objects.filter')
    def test_bulk_update_documents_restores_context(self, mock_filter):
        """Test bulk_update_documents restores tenant context."""
        mock_filter.return_value = Document.objects.none()

        # Clear any existing context
        set_current_tenant_id(None)

        # Call task with tenant_id
        tasks.bulk_update_documents([1, 2, 3], tenant_id=str(self.tenant1.id))

        # Verify context was restored
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

    def test_empty_trash_restores_context(self):
        """Test empty_trash restores tenant context."""
        # Set tenant1 context
        set_current_tenant_id(self.tenant1.id)

        # Create a deleted document
        doc = Document.objects.create(
            title="test",
            content="test content",
            checksum="test123",
            added=timezone.now(),
            created=timezone.now(),
            modified=timezone.now(),
            tenant_id=self.tenant1.id,
        )
        doc.delete()

        # Clear context
        set_current_tenant_id(None)

        # Call task with tenant_id
        tasks.empty_trash(doc_ids=[doc.id], tenant_id=str(self.tenant1.id))

        # Verify context was restored
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

    def test_check_scheduled_workflows_restores_context(self):
        """Test check_scheduled_workflows restores tenant context."""
        # Clear any existing context
        set_current_tenant_id(None)

        # Call task with tenant_id
        tasks.check_scheduled_workflows(tenant_id=str(self.tenant1.id))

        # Verify context was restored
        self.assertEqual(get_current_tenant_id(), self.tenant1.id)

    def test_update_document_content_restores_context(self):
        """Test update_document_content_maybe_archive_file restores tenant context."""
        # Set tenant1 context
        set_current_tenant_id(self.tenant1.id)

        # Create a document
        doc = Document.objects.create(
            title="test",
            content="test content",
            checksum="test123",
            added=timezone.now(),
            created=timezone.now(),
            modified=timezone.now(),
            mime_type="application/pdf",
            tenant_id=self.tenant1.id,
        )

        # Clear context
        set_current_tenant_id(None)

        # Mock the parser to avoid file operations
        with mock.patch('documents.tasks.get_parser_class_for_mime_type') as mock_parser:
            mock_parser.return_value = None

            # Call task with tenant_id (will fail at parser but that's ok)
            try:
                tasks.update_document_content_maybe_archive_file(
                    doc.id,
                    tenant_id=str(self.tenant1.id)
                )
            except Exception:
                pass  # Expected to fail due to missing parser

            # Verify context was restored before the failure
            self.assertEqual(get_current_tenant_id(), self.tenant1.id)


class ScheduledWrapperTasksTestCase(TestCase):
    """Test scheduled wrapper tasks for all tenants."""

    def setUp(self):
        """Set up test data."""
        # Create test tenants
        self.tenant1 = Tenant.objects.create(
            subdomain='tenant1',
            name='Tenant 1',
            region='us',
            is_active=True,
        )
        self.tenant2 = Tenant.objects.create(
            subdomain='tenant2',
            name='Tenant 2',
            region='us',
            is_active=True,
        )
        self.inactive_tenant = Tenant.objects.create(
            subdomain='inactive',
            name='Inactive Tenant',
            region='us',
            is_active=False,
        )

    @mock.patch('documents.tasks.empty_trash.delay')
    def test_scheduled_empty_trash_all_tenants(self, mock_task):
        """Test scheduled_empty_trash_all_tenants calls task for each active tenant."""
        tasks.scheduled_empty_trash_all_tenants()

        # Should be called twice (only for active tenants)
        self.assertEqual(mock_task.call_count, 2)

        # Verify called with correct tenant IDs
        call_args_list = [call[1]['tenant_id'] for call in mock_task.call_args_list]
        self.assertIn(str(self.tenant1.id), call_args_list)
        self.assertIn(str(self.tenant2.id), call_args_list)
        self.assertNotIn(str(self.inactive_tenant.id), call_args_list)

    @mock.patch('documents.tasks.check_scheduled_workflows.delay')
    def test_scheduled_check_workflows_all_tenants(self, mock_task):
        """Test scheduled_check_workflows_all_tenants calls task for each active tenant."""
        tasks.scheduled_check_workflows_all_tenants()

        # Should be called twice (only for active tenants)
        self.assertEqual(mock_task.call_count, 2)

        # Verify called with correct tenant IDs
        call_args_list = [call[1]['tenant_id'] for call in mock_task.call_args_list]
        self.assertIn(str(self.tenant1.id), call_args_list)
        self.assertIn(str(self.tenant2.id), call_args_list)
        self.assertNotIn(str(self.inactive_tenant.id), call_args_list)
