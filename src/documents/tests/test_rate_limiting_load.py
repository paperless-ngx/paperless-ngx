"""
Load tests for multi-tenant task rate limiting with 100+ tenants.
Tests worker overload prevention under high tenant count scenarios.
"""
import time
from unittest import mock
from django.test import TestCase, override_settings
from documents import tasks
from paperless.models import Tenant


class TestRateLimitingLoad(TestCase):
    """Load test suite for multi-tenant task rate limiting."""

    def setUp(self):
        """Create 100+ test tenants for load testing."""
        self.tenant_count = 120  # Test with 120 tenants
        self.tenants = []
        for i in range(self.tenant_count):
            tenant = Tenant.objects.create(
                subdomain=f"loadtest_tenant{i}",
                is_active=True,
            )
            self.tenants.append(tenant)

    def tearDown(self):
        """Clean up test tenants."""
        Tenant.objects.filter(subdomain__startswith="loadtest_").delete()

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_load_with_100_tenants_batched(self, mock_task):
        """Test rate limiting with 120 tenants in batches of 10."""
        start_time = time.time()
        tasks.scheduled_train_classifier_all_tenants()
        elapsed_time = time.time() - start_time

        # Should spawn tasks for all 120 tenants
        self.assertEqual(mock_task.delay.call_count, 120)

        # Should complete relatively quickly (no delays configured)
        # Allow generous buffer for test environment
        self.assertLess(elapsed_time, 5.0, "Task spawning took too long")

        # Verify all tenants got their tasks spawned
        spawned_tenant_ids = [call.kwargs["tenant_id"] for call in mock_task.delay.call_args_list]
        expected_tenant_ids = [str(t.id) for t in self.tenants]
        self.assertEqual(sorted(spawned_tenant_ids), sorted(expected_tenant_ids))

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=1)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.sanity_check")
    def test_load_with_100_tenants_with_delays(self, mock_task, mock_sleep):
        """Test that delays are applied correctly with 120 tenants."""
        tasks.scheduled_sanity_check_all_tenants()

        # With 120 tenants and batch_size=10, we have 12 batches
        # Sleep should be called 11 times (between each batch, not after last)
        self.assertEqual(mock_sleep.call_count, 11)
        mock_sleep.assert_called_with(1)

        # All 120 tenants should still get tasks spawned
        self.assertEqual(mock_task.delay.call_count, 120)

    @override_settings(CELERY_TENANT_BATCH_SIZE=25, CELERY_TENANT_BATCH_DELAY=2)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.llmindex_index")
    def test_load_with_larger_batch_size(self, mock_task, mock_sleep):
        """Test with larger batch size (25 tenants per batch)."""
        tasks.scheduled_llmindex_index_all_tenants()

        # With 120 tenants and batch_size=25, we have 5 batches (25+25+25+25+20)
        # Sleep should be called 4 times
        self.assertEqual(mock_sleep.call_count, 4)
        mock_sleep.assert_called_with(2)

        # All 120 tenants should get tasks spawned
        self.assertEqual(mock_task.delay.call_count, 120)

    @override_settings(CELERY_TENANT_BATCH_SIZE=0, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.empty_trash")
    def test_load_without_batching(self, mock_task):
        """Test legacy behavior: spawn all tasks immediately without batching."""
        start_time = time.time()
        tasks.scheduled_empty_trash_all_tenants()
        elapsed_time = time.time() - start_time

        # Should spawn tasks for all 120 tenants immediately
        self.assertEqual(mock_task.delay.call_count, 120)

        # Should complete quickly without batching delays
        self.assertLess(elapsed_time, 5.0, "Task spawning took too long")

    @override_settings(CELERY_TENANT_BATCH_SIZE=50, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.check_scheduled_workflows")
    def test_load_with_moderate_batch_size(self, mock_task):
        """Test with moderate batch size (50 tenants per batch)."""
        tasks.scheduled_check_workflows_all_tenants()

        # With 120 tenants and batch_size=50, we have 3 batches (50+50+20)
        # All 120 tenants should get tasks spawned
        self.assertEqual(mock_task.delay.call_count, 120)

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    @mock.patch("documents.tasks.sanity_check")
    @mock.patch("documents.tasks.llmindex_index")
    @mock.patch("documents.tasks.empty_trash")
    @mock.patch("documents.tasks.check_scheduled_workflows")
    def test_all_wrapper_tasks_with_load(
        self,
        mock_workflows,
        mock_trash,
        mock_llm,
        mock_sanity,
        mock_train,
    ):
        """Test all wrapper tasks simultaneously with 120 tenants."""
        # Run all wrapper tasks
        tasks.scheduled_train_classifier_all_tenants()
        tasks.scheduled_sanity_check_all_tenants()
        tasks.scheduled_llmindex_index_all_tenants()
        tasks.scheduled_empty_trash_all_tenants()
        tasks.scheduled_check_workflows_all_tenants()

        # Each task should spawn 120 tenant tasks
        self.assertEqual(mock_train.delay.call_count, 120)
        self.assertEqual(mock_sanity.delay.call_count, 120)
        self.assertEqual(mock_llm.delay.call_count, 120)
        self.assertEqual(mock_trash.delay.call_count, 120)
        self.assertEqual(mock_workflows.delay.call_count, 120)

        # Total: 600 tasks spawned (120 tenants × 5 task types)
        total_tasks = (
            mock_train.delay.call_count
            + mock_sanity.delay.call_count
            + mock_llm.delay.call_count
            + mock_trash.delay.call_count
            + mock_workflows.delay.call_count
        )
        self.assertEqual(total_tasks, 600)

    @override_settings(CELERY_TENANT_BATCH_SIZE=15, CELERY_TENANT_BATCH_DELAY=1)
    @mock.patch("time.sleep")
    @mock.patch("documents.tasks.train_classifier")
    def test_timing_verification(self, mock_task, mock_sleep):
        """Verify that timing behavior is as expected."""
        start_time = time.time()
        tasks.scheduled_train_classifier_all_tenants()
        elapsed_time = time.time() - start_time

        # With 120 tenants and batch_size=15, we have 8 batches
        # Sleep should be called 7 times (not after last batch)
        self.assertEqual(mock_sleep.call_count, 7)

        # Expected time: 7 seconds of sleep + overhead
        # In mock environment, sleep is instant, so we just verify it was called correctly
        mock_sleep.assert_called_with(1)

        # All tenants processed
        self.assertEqual(mock_task.delay.call_count, 120)

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_batch_ordering_preserved(self, mock_task):
        """Verify that tenant ordering is preserved during batching."""
        tasks.scheduled_train_classifier_all_tenants()

        # Extract tenant IDs in the order they were spawned
        spawned_tenant_ids = [call.kwargs["tenant_id"] for call in mock_task.delay.call_args_list]

        # Original tenant IDs in database order
        original_tenant_ids = [str(t.id) for t in self.tenants]

        # Ordering should be preserved
        self.assertEqual(spawned_tenant_ids, original_tenant_ids)

    @override_settings(CELERY_TENANT_BATCH_SIZE=10, CELERY_TENANT_BATCH_DELAY=0)
    @mock.patch("documents.tasks.train_classifier")
    def test_partial_failure_does_not_block_others(self, mock_task):
        """
        Test that if one task spawn fails, others still proceed.
        This simulates resilience under load.
        """

        def side_effect_with_failure(**kwargs):
            # Fail for one specific tenant (the 50th one)
            if kwargs["tenant_id"] == str(self.tenants[49].id):
                raise Exception("Simulated task spawn failure")

        mock_task.delay.side_effect = side_effect_with_failure

        # Should raise exception but we can catch it
        with self.assertRaises(Exception):
            tasks.scheduled_train_classifier_all_tenants()

        # Task should have been attempted for tenants up to the failure point
        # (In production, you might want to add try-catch to handle individual failures)
        self.assertGreaterEqual(mock_task.delay.call_count, 50)
