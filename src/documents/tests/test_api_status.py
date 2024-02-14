import os
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from paperless import version


class TestSystemStatus(APITestCase):
    ENDPOINT = "/api/status/"

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="temp_admin",
        )

    def test_system_status(self):
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

    def test_system_status_insufficient_permissions(self):
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        normal_user = User.objects.create_user(username="normal_user")
        self.client.force_login(normal_user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_status_container_detection(self):
        self.client.force_login(self.user)
        os.environ["PNGX_CONTAINERIZED"] = "1"
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["install_type"], "docker")
        os.environ["KUBERNETES_SERVICE_HOST"] = "http://localhost"
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.data["install_type"], "kubernetes")

    @mock.patch("redis.Redis.execute_command")
    def test_system_status_redis_ping(self, mock_ping):
        mock_ping.return_value = True
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["redis_status"], "OK")

    @mock.patch("celery.app.control.Inspect.ping")
    def test_system_status_celery_ping(self, mock_ping):
        mock_ping.return_value = {"hostname": {"ok": "pong"}}
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["celery_status"], "OK")

    @override_settings(INDEX_DIR="/tmp/index")
    @mock.patch("whoosh.index.FileIndex.last_modified")
    def test_system_status_index_ok(self, mock_last_modified):
        mock_last_modified.return_value = 1707839087
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "OK")
        self.assertIsNotNone(response.data["tasks"]["index_last_modified"])

    @override_settings(INDEX_DIR="/tmp/index/")
    @mock.patch("documents.index.open_index", autospec=True)
    def test_system_status_index_error(self, mock_open_index):
        mock_open_index.return_value = None
        mock_open_index.side_effect = Exception("Index error")
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        mock_open_index.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "ERROR")
        self.assertIsNotNone(response.data["tasks"]["index_error"])

    @override_settings(MODEL_FILE="/tmp/does_not_exist")
    def test_system_status_classifier_ok(self):
        with open(settings.MODEL_FILE, "w") as f:
            f.write("test")
            f.close()
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["classifier_status"], "OK")
            self.assertIsNone(response.data["tasks"]["classifier_error"])

    @override_settings(MODEL_FILE="/tmp/does_not_exist")
    @mock.patch("documents.classifier.load_classifier")
    def test_system_status_classifier_error(self, mock_load_classifier):
        mock_load_classifier.side_effect = Exception("Classifier error")
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["classifier_status"], "ERROR")
        self.assertIsNotNone(response.data["tasks"]["classifier_error"])
