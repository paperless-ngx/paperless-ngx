"""
Tests for multi-tenant task rate limiting functionality.
"""
from unittest import mock
from django.test import TestCase, override_settings
from documents import tasks
from paperless.models import Tenant


class TestRateLimiting(TestCase):
    """Test suite for multi-tenant task rate limiting."""

    def setUp(self):
        """Create test tenants."""
        self.tenants = []
        for i in range(15):  # Create 15 tenants for testing batching
            tenant = Tenant.objects.create(
                subdomain=f"tenant{i}",
                is_active=True,
            )
            self.tenants.append(tenant)

    def tearDown(self):
        """Clean up test tenants."""
        Tenant.objects.all().delete()

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_scheduled_train_classifier_all_tenants_with_batching(self, mock_task):
        """Test that train_classifier tasks are spawned in batches."""
        tasks.scheduled_train_classifier_all_tenants()

        # Should call delay for all 15 tenants
        self.assertEqual(mock_task.delay.call_count, 15)

        # Verify tenant_id and scheduled are passed correctly
        for call in mock_task.delay.call_args_list:
            self.assertIn("tenant_id", call.kwargs)
            self.assertEqual(call.kwargs["scheduled"], True)

    @override_settings(CELERY_TENANT_BATCH_SIZE=0, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_scheduled_train_classifier_no_batching(self, mock_task):
        """Test that tasks spawn immediately when batch_size is 0."""
        tasks.scheduled_train_classifier_all_tenants()

        # Should still call delay for all 15 tenants (no batching)
        self.assertEqual(mock_task.delay.call_count, 15)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.sanity_check")
    def test_scheduled_sanity_check_all_tenants_with_batching(self, mock_task):
        """Test that sanity_check tasks are spawned in batches."""
        tasks.scheduled_sanity_check_all_tenants()

        # Should call delay for all 15 tenants
        self.assertEqual(mock_task.delay.call_count, 15)

        # Verify tenant_id, scheduled, and raise_on_error are passed correctly
        for call in mock_task.delay.call_args_list:
            self.assertIn("tenant_id", call.kwargs)
            self.assertEqual(call.kwargs["scheduled"], True)
            self.assertEqual(call.kwargs["raise_on_error"], True)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.llmindex_index")
    def test_scheduled_llmindex_index_all_tenants_with_batching(self, mock_task):
        """Test that llmindex_index tasks are spawned in batches."""
        tasks.scheduled_llmindex_index_all_tenants()

        # Should call delay for all 15 tenants
        self.assertEqual(mock_task.delay.call_count, 15)

        # Verify tenant_id and scheduled are passed correctly
        for call in mock_task.delay.call_args_list:
            self.assertIn("tenant_id", call.kwargs)
            self.assertEqual(call.kwargs["scheduled"], True)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.empty_trash")
    def test_scheduled_empty_trash_all_tenants_with_batching(self, mock_task):
        """Test that empty_trash tasks are spawned in batches."""
        tasks.scheduled_empty_trash_all_tenants()

        # Should call delay for all 15 tenants
        self.assertEqual(mock_task.delay.call_count, 15)

        # Verify tenant_id is passed correctly
        for call in mock_task.delay.call_args_list:
            self.assertIn("tenant_id", call.kwargs)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.check_scheduled_workflows")
    def test_scheduled_check_workflows_all_tenants_with_batching(self, mock_task):
        """Test that check_scheduled_workflows tasks are spawned in batches."""
        tasks.scheduled_check_workflows_all_tenants()

        # Should call delay for all 15 tenants
        self.assertEqual(mock_task.delay.call_count, 15)

        # Verify tenant_id is passed correctly
        for call in mock_task.delay.call_args_list:
            self.assertIn("tenant_id", call.kwargs)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=1)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.train_classifier")
    def test_rate_limiting_with_delay(self, mock_task, mock_sleep):
        """Test that batches are delayed as expected."""
        tasks.scheduled_train_classifier_all_tenants()

        # With 15 tenants and batch_size=5, we should have 3 batches
        # Sleep should be called 2 times (between batch 1-2 and 2-3, but not after batch 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(1)

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=2)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.train_classifier")
    def test_rate_limiting_with_larger_batches(self, mock_task, mock_sleep):
        """Test rate limiting with larger batch size."""
        tasks.scheduled_train_classifier_all_tenants()

        # With 15 tenants and batch_size=10, we should have 2 batches (10 + 5)
        # Sleep should be called 1 time (between batch 1 and 2)
        self.assertEqual(mock_sleep.call_count, 1)
        mock_sleep.assert_called_with(2)

    @override_settings(CELERY_TENANT_BATCH_SIZE=20, CELERY_TENANT_BATCH_DELAY=1)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.train_classifier")
    def test_no_delay_when_single_batch(self, mock_task, mock_sleep):
        """Test that no delay occurs when all tenants fit in one batch."""
        tasks.scheduled_train_classifier_all_tenants()

        # With 15 tenants and batch_size=20, we have 1 batch
        # Sleep should never be called
        mock_sleep.assert_not_called()

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_only_active_tenants_processed(self, mock_task):
        """Test that only active tenants are processed."""
        # Mark some tenants as inactive
        for i in range(5):
            self.tenants[i].is_active = False
            self.tenants[i].save()

        tasks.scheduled_train_classifier_all_tenants()

        # Should only call delay for 10 active tenants
        self.assertEqual(mock_task.delay.call_count, 10)

    @override_settings(CELERY_TENANT_BATCH_SIZE=5, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_no_tenants_no_tasks_spawned(self, mock_task):
        """Test that no tasks are spawned when there are no active tenants."""
        # Mark all tenants as inactive
        Tenant.objects.all().update(is_active=False)

        tasks.scheduled_train_classifier_all_tenants()

        # Should not call delay at all
        mock_task.delay.assert_not_called()
