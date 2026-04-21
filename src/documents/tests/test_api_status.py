import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import PaperlessTask
from documents.permissions import has_system_status_permission
from documents.tests.factories import PaperlessTaskFactory
from paperless import version


class TestSystemStatus(APITestCase):
    ENDPOINT = "/api/status/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(
            username="temp_admin",
        )
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.override = override_settings(MEDIA_ROOT=self.tmp_dir)
        self.override.enable()

        # Mock slow network calls so tests don't block on real Redis/Celery timeouts.
        # Individual tests that care about specific behaviour override these with
        # their own @mock.patch decorators (which take precedence).
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

        self.override.disable()
        shutil.rmtree(self.tmp_dir)

    def test_system_status(self) -> None:
        """
        GIVEN:
            - A user is logged in
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains relevant system status information
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pngx_version"], version.__full_version_str__)
        self.assertIsNotNone(response.data["server_os"])
        self.assertEqual(response.data["install_type"], "bare-metal")
        self.assertIsNotNone(response.data["storage"]["total"])
        self.assertIsNotNone(response.data["storage"]["available"])
        self.assertEqual(response.data["database"]["type"], "sqlite")
        self.assertIsNotNone(response.data["database"]["url"])
        self.assertEqual(response.data["database"]["status"], "OK")
        self.assertIsNone(response.data["database"]["error"])
        self.assertIsNotNone(response.data["database"]["migration_status"])
        self.assertEqual(response.data["tasks"]["redis_url"], "redis://localhost:6379")
        self.assertEqual(response.data["tasks"]["redis_status"], "ERROR")
        self.assertIsNotNone(response.data["tasks"]["redis_error"])

    def test_system_status_insufficient_permissions(self) -> None:
        """
        GIVEN:
            - A user is not logged in or does not have permissions
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains a 401 status code or a 403 status code
        """
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Token")
        normal_user = User.objects.create_user(username="normal_user")
        self.client.force_login(normal_user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # test the permission helper function directly for good measure
        self.assertFalse(has_system_status_permission(None))

    def test_system_status_with_system_status_permission(self) -> None:
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        user = User.objects.create_user(username="status_user")
        user.user_permissions.add(
            Permission.objects.get(codename="view_system_status"),
        )

        self.client.force_login(user)
        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_system_status_with_bad_basic_auth_challenges(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION="Basic invalid")
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], 'Basic realm="api"')

    def test_system_status_container_detection(self) -> None:
        """
        GIVEN:
            - The application is running in a containerized environment
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct install type
        """
        self.client.force_login(self.user)
        with mock.patch.dict(os.environ, {"PNGX_CONTAINERIZED": "1"}, clear=False):
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["install_type"], "docker")
        with mock.patch.dict(
            os.environ,
            {"PNGX_CONTAINERIZED": "1", "KUBERNETES_SERVICE_HOST": "http://localhost"},
            clear=False,
        ):
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.data["install_type"], "kubernetes")

    @mock.patch("redis.Redis.execute_command")
    def test_system_status_redis_ping(self, mock_ping) -> None:
        """
        GIVEN:
            - Redies ping returns True
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct redis status
        """
        mock_ping.return_value = True
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["redis_status"], "OK")

    def test_system_status_redis_no_credentials(self) -> None:
        """
        GIVEN:
            - Redis URL with credentials
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the redis URL but no credentials
        """
        with override_settings(
            _CHANNELS_REDIS_URL="redis://username:password@localhost:6379",
        ):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.data["tasks"]["redis_url"],
                "redis://localhost:6379",
            )

    def test_system_status_redis_socket(self) -> None:
        """
        GIVEN:
            - Redis URL is socket
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the redis URL
        """

        with override_settings(_CHANNELS_REDIS_URL="unix:///path/to/redis.sock"):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.data["tasks"]["redis_url"],
                "unix:///path/to/redis.sock",
            )

    @mock.patch("celery.app.control.Inspect.ping")
    def test_system_status_celery_ping(self, mock_ping) -> None:
        """
        GIVEN:
            - Celery ping returns pong
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct celery status
        """
        mock_ping.return_value = {"hostname": {"ok": "pong"}}
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["celery_status"], "OK")

    @mock.patch("documents.search.get_backend")
    def test_system_status_index_ok(self, mock_get_backend) -> None:
        """
        GIVEN:
            - The index is accessible
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct index status
        """
        mock_get_backend.return_value = mock.MagicMock()
        # Use the temp dir created in setUp (self.tmp_dir) as a real INDEX_DIR
        # with a real file so the mtime lookup works
        sentinel = self.tmp_dir / "sentinel.txt"
        sentinel.write_text("ok")
        with self.settings(INDEX_DIR=self.tmp_dir):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "OK")
        self.assertIsNotNone(response.data["tasks"]["index_last_modified"])

    @mock.patch("documents.search.get_backend")
    def test_system_status_index_error(self, mock_get_backend) -> None:
        """
        GIVEN:
            - The index cannot be opened
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct index status
        """
        mock_get_backend.side_effect = Exception("Index error")
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        mock_get_backend.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "ERROR")
        self.assertIsNotNone(response.data["tasks"]["index_error"])

    def test_system_status_classifier_ok(self) -> None:
        """
        GIVEN:
            - The classifier is found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an OK classifier status
        """
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=PaperlessTask.Status.SUCCESS,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["classifier_status"], "OK")
        self.assertIsNone(response.data["tasks"]["classifier_error"])

    def test_system_status_classifier_warning(self) -> None:
        """
        GIVEN:
            - No classifier task is found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains a WARNING classifier status
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["tasks"]["classifier_status"],
            "WARNING",
        )

    def test_system_status_classifier_error(self) -> None:
        """
        GIVEN:
            - An error occurred while loading the classifier
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an ERROR classifier status
        """
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=PaperlessTask.Status.FAILURE,
            result_data={"error_message": "Classifier training failed"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["tasks"]["classifier_status"],
            "ERROR",
        )
        self.assertIsNotNone(response.data["tasks"]["classifier_error"])

    def test_system_status_sanity_check_ok(self) -> None:
        """
        GIVEN:
            - The sanity check is successful
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an OK sanity check status
        """
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.SANITY_CHECK,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=PaperlessTask.Status.SUCCESS,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["sanity_check_status"], "OK")
        self.assertIsNone(response.data["tasks"]["sanity_check_error"])

    def test_system_status_sanity_check_warning(self) -> None:
        """
        GIVEN:
            - No sanity check task is found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains a WARNING sanity check status
        """
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["tasks"]["sanity_check_status"],
            "WARNING",
        )

    def test_system_status_sanity_check_error(self) -> None:
        """
        GIVEN:
            - The sanity check failed
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an ERROR sanity check status
        """
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.SANITY_CHECK,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=PaperlessTask.Status.FAILURE,
            result_data={"error_message": "5 issues found."},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["tasks"]["sanity_check_status"],
            "ERROR",
        )
        self.assertIsNotNone(response.data["tasks"]["sanity_check_error"])

    def test_system_status_ai_disabled(self) -> None:
        """
        GIVEN:
            - The AI feature is disabled
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct AI status
        """
        with override_settings(AI_ENABLED=False):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["llmindex_status"], "DISABLED")
            self.assertIsNone(response.data["tasks"]["llmindex_error"])

    def test_system_status_ai_enabled(self) -> None:
        """
        GIVEN:
            - The AI index feature is enabled, but no tasks are found
            - The AI index feature is enabled and a task is found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct AI status
        """
        with override_settings(AI_ENABLED=True, LLM_EMBEDDING_BACKEND="openai"):
            self.client.force_login(self.user)

            # No tasks found
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["llmindex_status"], "WARNING")

            PaperlessTaskFactory(
                task_type=PaperlessTask.TaskType.LLM_INDEX,
                trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
                status=PaperlessTask.Status.SUCCESS,
            )
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["llmindex_status"], "OK")
            self.assertIsNone(response.data["tasks"]["llmindex_error"])

    def test_system_status_ai_error(self) -> None:
        """
        GIVEN:
            - The AI index feature is enabled and a task is found with an error
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct AI status
        """
        with override_settings(AI_ENABLED=True, LLM_EMBEDDING_BACKEND="openai"):
            PaperlessTaskFactory(
                task_type=PaperlessTask.TaskType.LLM_INDEX,
                trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
                status=PaperlessTask.Status.FAILURE,
                result_data={"error_message": "AI index update failed"},
            )
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["llmindex_status"], "ERROR")
            self.assertIsNotNone(response.data["tasks"]["llmindex_error"])
