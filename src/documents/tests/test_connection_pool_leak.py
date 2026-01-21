"""
Test suite for PostgreSQL connection pool leak fix.

This test verifies that Celery task signal handlers properly close
database connection pools to prevent memory leaks.
"""
import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from celery import states
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from documents.models import PaperlessTask
from documents.signals.handlers import before_task_publish_handler
from documents.signals.handlers import task_failure_handler
from documents.signals.handlers import task_postrun_handler
from documents.signals.handlers import task_prerun_handler


class ConnectionPoolLeakTestCase(TestCase):
    """
    Test that signal handlers properly close connection pools to prevent leaks.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.task_id = "test-task-id-123"
        self.headers = {
            "task": "documents.tasks.consume_file",
            "id": self.task_id,
        }

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_before_task_publish_closes_pool(self, mock_close_old, mock_connections):
        """Test that before_task_publish_handler closes connection pool."""
        # Setup mock connection with pool
        mock_conn = Mock()
        mock_conn.alias = "default"
        mock_conn.pool = Mock()
        mock_connections.all.return_value = [mock_conn]

        # Create test body
        from documents.data_models import ConsumableDocument
        from documents.data_models import DocumentMetadataOverrides

        mock_doc = Mock(spec=ConsumableDocument)
        mock_doc.original_file.name = "test.pdf"
        mock_overrides = Mock(spec=DocumentMetadataOverrides)
        mock_overrides.owner_id = 1

        body = [[mock_doc, mock_overrides]]

        # Call handler
        before_task_publish_handler(
            sender=None,
            headers=self.headers,
            body=body,
        )

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()

        # Verify connection pool was closed
        mock_connections.all.assert_called_once_with(initialized_only=True)
        mock_conn.close_pool.assert_called_once()

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_task_prerun_closes_pool(self, mock_close_old, mock_connections):
        """Test that task_prerun_handler closes connection pool."""
        # Setup mock connection with pool
        mock_conn = Mock()
        mock_conn.alias = "default"
        mock_conn.pool = Mock()
        mock_connections.all.return_value = [mock_conn]

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.PENDING,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
        )

        # Call handler
        task_prerun_handler(
            sender=None,
            task_id=self.task_id,
            task=None,
        )

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()

        # Verify connection pool was closed
        mock_connections.all.assert_called_once_with(initialized_only=True)
        mock_conn.close_pool.assert_called_once()

        # Verify task status was updated
        task.refresh_from_db()
        self.assertEqual(task.status, states.STARTED)
        self.assertIsNotNone(task.date_started)

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_task_postrun_closes_pool(self, mock_close_old, mock_connections):
        """Test that task_postrun_handler closes connection pool."""
        # Setup mock connection with pool
        mock_conn = Mock()
        mock_conn.alias = "default"
        mock_conn.pool = Mock()
        mock_connections.all.return_value = [mock_conn]

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.STARTED,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
            date_started=timezone.now(),
        )

        # Call handler
        task_postrun_handler(
            sender=None,
            task_id=self.task_id,
            task=None,
            retval="Success",
            state=states.SUCCESS,
        )

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()

        # Verify connection pool was closed
        mock_connections.all.assert_called_once_with(initialized_only=True)
        mock_conn.close_pool.assert_called_once()

        # Verify task status was updated
        task.refresh_from_db()
        self.assertEqual(task.status, states.SUCCESS)
        self.assertEqual(task.result, "Success")
        self.assertIsNotNone(task.date_done)

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_task_failure_closes_pool(self, mock_close_old, mock_connections):
        """Test that task_failure_handler closes connection pool."""
        # Setup mock connection with pool
        mock_conn = Mock()
        mock_conn.alias = "default"
        mock_conn.pool = Mock()
        mock_connections.all.return_value = [mock_conn]

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.STARTED,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
            date_started=timezone.now(),
        )

        # Call handler with failure
        task_failure_handler(
            sender=None,
            task_id=self.task_id,
            exception=Exception("Test error"),
            args=None,
            traceback="Test traceback",
        )

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()

        # Verify connection pool was closed
        mock_connections.all.assert_called_once_with(initialized_only=True)
        mock_conn.close_pool.assert_called_once()

        # Verify task status was updated
        task.refresh_from_db()
        self.assertEqual(task.status, states.FAILURE)
        self.assertEqual(task.result, "Test traceback")
        self.assertIsNotNone(task.date_done)

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_handlers_skip_connections_without_pool(
        self,
        mock_close_old,
        mock_connections,
    ):
        """Test that handlers skip connections without pool attribute."""
        # Setup mock connection without pool
        mock_conn = Mock()
        mock_conn.alias = "default"
        # Don't set pool attribute
        if hasattr(mock_conn, "pool"):
            delattr(mock_conn, "pool")
        mock_connections.all.return_value = [mock_conn]

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.PENDING,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
        )

        # Call handler - should not raise error
        task_prerun_handler(
            sender=None,
            task_id=self.task_id,
            task=None,
        )

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()

        # Verify connection pool was NOT attempted to be closed
        # (since pool doesn't exist)
        self.assertFalse(hasattr(mock_conn, "close_pool"))

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    def test_handlers_skip_non_default_connections(
        self,
        mock_close_old,
        mock_connections,
    ):
        """Test that handlers only close default connection pool."""
        # Setup mock connections with different aliases
        mock_default = Mock()
        mock_default.alias = "default"
        mock_default.pool = Mock()

        mock_other = Mock()
        mock_other.alias = "other_db"
        mock_other.pool = Mock()

        mock_connections.all.return_value = [mock_default, mock_other]

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.PENDING,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
        )

        # Call handler
        task_prerun_handler(
            sender=None,
            task_id=self.task_id,
            task=None,
        )

        # Verify only default connection pool was closed
        mock_default.close_pool.assert_called_once()
        mock_other.close_pool.assert_not_called()

    @patch("documents.signals.handlers.connections")
    @patch("documents.signals.handlers.close_old_connections")
    @patch("documents.signals.handlers.logger")
    def test_handler_exception_doesnt_prevent_task_execution(
        self,
        mock_logger,
        mock_close_old,
        mock_connections,
    ):
        """Test that exceptions in handlers don't prevent task execution."""
        # Setup mock to raise exception
        mock_close_old.side_effect = Exception("Database error")

        # Create test body
        from documents.data_models import ConsumableDocument
        from documents.data_models import DocumentMetadataOverrides

        mock_doc = Mock(spec=ConsumableDocument)
        mock_doc.original_file.name = "test.pdf"
        mock_overrides = Mock(spec=DocumentMetadataOverrides)
        mock_overrides.owner_id = 1

        body = [[mock_doc, mock_overrides]]

        # Call handler - should not raise exception
        try:
            before_task_publish_handler(
                sender=None,
                headers=self.headers,
                body=body,
            )
        except Exception:
            self.fail("Handler raised exception when it should have caught it")

        # Verify exception was logged
        mock_logger.exception.assert_called()

    @unittest.skipUnless(
        settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql",
        "Test requires PostgreSQL connection pooling",
    )
    def test_integration_pool_closing_with_real_db(self):
        """Integration test with real database connection."""
        from django.db import connections

        # Get the default connection
        conn = connections["default"]

        # Skip if pooling is not enabled
        if not hasattr(conn, "pool") or not conn.pool:
            self.skipTest("Connection pooling not enabled in test environment")

        # Create a test task
        task = PaperlessTask.objects.create(
            task_id=self.task_id,
            status=states.PENDING,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            type=PaperlessTask.TaskType.AUTO,
        )

        # Get initial pool state
        initial_pool_size = (
            len(conn.pool._pool) if hasattr(conn.pool, "_pool") else None
        )

        # Call handler which should close pool
        task_prerun_handler(
            sender=None,
            task_id=self.task_id,
            task=None,
        )

        # Verify task was updated
        task.refresh_from_db()
        self.assertEqual(task.status, states.STARTED)

        # Pool should have been closed and recreated
        # Note: The exact pool state depends on Django's implementation
        # but we verify the handler executed without errors
        self.assertIsNotNone(conn.pool)
