import shutil
import tempfile
from pathlib import Path
from unittest import mock

from celery import states
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import PaperlessTask


@override_settings(PROMETHEUS_METRICS_ENABLED=True)
class TestPrometheusMetrics(APITestCase):
    ENDPOINT = "/metrics/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(
            username="temp_admin",
        )
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.media_override = override_settings(MEDIA_ROOT=self.tmp_dir)
        self.media_override.enable()

        # Mock slow network calls so tests don't block on real Redis/Celery timeouts.
        redis_patcher = mock.patch(
            "redis.Redis.execute_command",
            side_effect=Exception("Redis not available"),
        )
        self.mock_redis = redis_patcher.start()
        self.addCleanup(redis_patcher.stop)

        celery_patcher = mock.patch(
            "celery.app.control.Inspect.ping",
            side_effect=Exception("Celery not available"),
        )
        self.mock_celery_ping = celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

    def tearDown(self) -> None:
        super().tearDown()
        self.media_override.disable()
        shutil.rmtree(self.tmp_dir)

    def test_metrics_disabled(self) -> None:
        """
        GIVEN:
            - PROMETHEUS_METRICS_ENABLED is False
        WHEN:
            - A user requests /metrics/
        THEN:
            - The response is 404
        """
        with override_settings(PROMETHEUS_METRICS_ENABLED=False):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_metrics_requires_auth(self) -> None:
        """
        GIVEN:
            - No user is logged in
        WHEN:
            - An unauthenticated request is made to /metrics/
        THEN:
            - The response is 401
        """
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_metrics_requires_staff(self) -> None:
        """
        GIVEN:
            - A non-staff user is logged in
        WHEN:
            - The user requests /metrics/
        THEN:
            - The response is 403
        """
        normal_user = User.objects.create_user(username="normal_user")
        self.client.force_login(normal_user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_metrics_ok_for_staff(self) -> None:
        """
        GIVEN:
            - A staff user is logged in and metrics are enabled
        WHEN:
            - The user requests /metrics/
        THEN:
            - The response is 200 with Prometheus content type
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/plain", response["Content-Type"])

    def test_database_status_metric(self) -> None:
        """
        GIVEN:
            - Database is accessible
        WHEN:
            - Metrics are scraped
        THEN:
            - Database status gauge is 1.0
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"paperless_status_database_status 1.0", response.content)

    def test_database_unapplied_migrations(self) -> None:
        """
        GIVEN:
            - All migrations are applied
        WHEN:
            - Metrics are scraped
        THEN:
            - Unapplied migrations gauge is 0.0
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(
            b"paperless_status_database_unapplied_migrations 0.0",
            response.content,
        )

    def test_storage_metrics(self) -> None:
        """
        GIVEN:
            - Storage is accessible
        WHEN:
            - Metrics are scraped
        THEN:
            - Storage total and available bytes metrics are present
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_storage_total_bytes", response.content)
        self.assertIn(b"paperless_status_storage_available_bytes", response.content)

    @mock.patch("redis.Redis.execute_command")
    def test_redis_ok(self, mock_ping) -> None:
        """
        GIVEN:
            - Redis ping returns True
        WHEN:
            - Metrics are scraped
        THEN:
            - Redis status gauge is 1.0
        """
        mock_ping.return_value = True
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_redis_status 1.0", response.content)

    def test_redis_error(self) -> None:
        """
        GIVEN:
            - Redis is not available
        WHEN:
            - Metrics are scraped
        THEN:
            - Redis status gauge is 0.0
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_redis_status 0.0", response.content)

    @mock.patch("celery.app.control.Inspect.ping")
    def test_celery_ok(self, mock_ping) -> None:
        """
        GIVEN:
            - Celery ping returns pong
        WHEN:
            - Metrics are scraped
        THEN:
            - Celery status gauge is 1.0
        """
        mock_ping.return_value = {"hostname": {"ok": "pong"}}
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_celery_status 1.0", response.content)

    def test_celery_error(self) -> None:
        """
        GIVEN:
            - Celery is not available
        WHEN:
            - Metrics are scraped
        THEN:
            - Celery status gauge is 0.0
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_celery_status 0.0", response.content)

    @override_settings(INDEX_DIR=Path("/tmp/index"))
    @mock.patch("whoosh.index.FileIndex.last_modified")
    def test_index_ok_with_timestamp(self, mock_last_modified) -> None:
        """
        GIVEN:
            - The index is accessible with a known modification time
        WHEN:
            - Metrics are scraped
        THEN:
            - Index status gauge is 1.0 and timestamp metric is present
        """
        mock_last_modified.return_value = 1707839087
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_index_status 1.0", response.content)
        self.assertIn(
            b"paperless_status_index_last_modified_timestamp_seconds",
            response.content,
        )

    @override_settings(INDEX_DIR=Path("/tmp/index/"))
    @mock.patch("documents.index.open_index", autospec=True)
    def test_index_error(self, mock_open_index) -> None:
        """
        GIVEN:
            - The index cannot be opened
        WHEN:
            - Metrics are scraped
        THEN:
            - Index status gauge is 0.0 and no timestamp metric
        """
        mock_open_index.side_effect = Exception("Index error")
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_index_status 0.0", response.content)
        self.assertNotIn(
            b"paperless_status_index_last_modified_timestamp_seconds",
            response.content,
        )

    def test_classifier_ok(self) -> None:
        """
        GIVEN:
            - A successful classifier training task exists
        WHEN:
            - Metrics are scraped
        THEN:
            - Classifier status gauge is 1.0 and timestamp is present
        """
        PaperlessTask.objects.create(
            type=PaperlessTask.TaskType.SCHEDULED_TASK,
            status=states.SUCCESS,
            task_name=PaperlessTask.TaskName.TRAIN_CLASSIFIER,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_classifier_status 1.0", response.content)
        self.assertIn(
            b"paperless_status_classifier_last_trained_timestamp_seconds",
            response.content,
        )

    def test_classifier_warning(self) -> None:
        """
        GIVEN:
            - No classifier training tasks exist
        WHEN:
            - Metrics are scraped
        THEN:
            - Classifier status gauge is 0.0 (WARNING maps to 0)
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_classifier_status 0.0", response.content)

    def test_classifier_error(self) -> None:
        """
        GIVEN:
            - A failed classifier training task exists
        WHEN:
            - Metrics are scraped
        THEN:
            - Classifier status gauge is 0.0
        """
        PaperlessTask.objects.create(
            type=PaperlessTask.TaskType.SCHEDULED_TASK,
            status=states.FAILURE,
            task_name=PaperlessTask.TaskName.TRAIN_CLASSIFIER,
            result="Classifier training failed",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"paperless_status_classifier_status 0.0", response.content)

    def test_sanity_check_ok(self) -> None:
        """
        GIVEN:
            - A successful sanity check task exists
        WHEN:
            - Metrics are scraped
        THEN:
            - Sanity check status gauge is 1.0 and timestamp is present
        """
        PaperlessTask.objects.create(
            type=PaperlessTask.TaskType.SCHEDULED_TASK,
            status=states.SUCCESS,
            task_name=PaperlessTask.TaskName.CHECK_SANITY,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(
            b"paperless_status_sanity_check_status 1.0",
            response.content,
        )
        self.assertIn(
            b"paperless_status_sanity_check_last_run_timestamp_seconds",
            response.content,
        )

    def test_sanity_check_error(self) -> None:
        """
        GIVEN:
            - A failed sanity check task exists
        WHEN:
            - Metrics are scraped
        THEN:
            - Sanity check status gauge is 0.0
        """
        PaperlessTask.objects.create(
            type=PaperlessTask.TaskType.SCHEDULED_TASK,
            status=states.FAILURE,
            task_name=PaperlessTask.TaskName.CHECK_SANITY,
            result="5 issues found.",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(
            b"paperless_status_sanity_check_status 0.0",
            response.content,
        )

    def test_timestamp_absent_when_no_task(self) -> None:
        """
        GIVEN:
            - No classifier or sanity check tasks exist
        WHEN:
            - Metrics are scraped
        THEN:
            - Timestamp metrics are absent from the output
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertNotIn(
            b"paperless_status_classifier_last_trained_timestamp_seconds",
            response.content,
        )
        self.assertNotIn(
            b"paperless_status_sanity_check_last_run_timestamp_seconds",
            response.content,
        )

    def test_metrics_help_and_type_annotations(self) -> None:
        """
        GIVEN:
            - Metrics endpoint is enabled
        WHEN:
            - Metrics are scraped
        THEN:
            - Output contains HELP and TYPE annotations for metrics
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertIn(b"# HELP paperless_status_database_status", response.content)
        self.assertIn(
            b"# TYPE paperless_status_database_status gauge",
            response.content,
        )
        self.assertIn(b"# HELP paperless_status_redis_status", response.content)
        self.assertIn(b"# HELP paperless_status_celery_status", response.content)
        self.assertIn(b"# HELP paperless_status_storage_total_bytes", response.content)
