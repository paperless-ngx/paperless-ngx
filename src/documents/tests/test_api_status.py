import os
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.classifier import ClassifierModelCorruptError
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.models import Document
from documents.models import Tag
from paperless import version


class TestSystemStatus(APITestCase):
    ENDPOINT = "/api/status/"

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="temp_admin",
        )

    def test_system_status(self):
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

    def test_system_status_insufficient_permissions(self):
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
        normal_user = User.objects.create_user(username="normal_user")
        self.client.force_login(normal_user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_status_container_detection(self):
        """
        GIVEN:
            - The application is running in a containerized environment
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct install type
        """
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

    def test_system_status_redis_no_credentials(self):
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

    def test_system_status_redis_socket(self):
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
    def test_system_status_celery_ping(self, mock_ping):
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

    @override_settings(INDEX_DIR=Path("/tmp/index"))
    @mock.patch("whoosh.index.FileIndex.last_modified")
    def test_system_status_index_ok(self, mock_last_modified):
        """
        GIVEN:
            - The index last modified time is set
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct index status
        """
        mock_last_modified.return_value = 1707839087
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "OK")
        self.assertIsNotNone(response.data["tasks"]["index_last_modified"])

    @override_settings(INDEX_DIR="/tmp/index/")
    @mock.patch("documents.index.open_index", autospec=True)
    def test_system_status_index_error(self, mock_open_index):
        """
        GIVEN:
            - The index is not found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains the correct index status
        """
        mock_open_index.return_value = None
        mock_open_index.side_effect = Exception("Index error")
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        mock_open_index.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["index_status"], "ERROR")
        self.assertIsNotNone(response.data["tasks"]["index_error"])

    @override_settings(DATA_DIR="/tmp/does_not_exist/data/")
    def test_system_status_classifier_ok(self):
        """
        GIVEN:
            - The classifier is found
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an OK classifier status
        """
        load_classifier()
        test_classifier = DocumentClassifier()
        test_classifier.save()
        self.client.force_login(self.user)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"]["classifier_status"], "OK")
        self.assertIsNone(response.data["tasks"]["classifier_error"])

    def test_system_status_classifier_warning(self):
        """
        GIVEN:
            - The classifier does not exist yet
            - > 0 documents and tags with auto matching exist
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an WARNING classifier status
        """
        with override_settings(MODEL_FILE="does_not_exist"):
            Document.objects.create(
                title="Test Document",
            )
            Tag.objects.create(name="Test Tag", matching_algorithm=Tag.MATCH_AUTO)
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["classifier_status"], "WARNING")
            self.assertIsNotNone(response.data["tasks"]["classifier_error"])

    def test_system_status_classifier_error(self):
        """
        GIVEN:
            - The classifier does exist but is corrupt
            - > 0 documents and tags with auto matching exist
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an ERROR classifier status
        """
        with (
            tempfile.NamedTemporaryFile(
                dir="/tmp",
                delete=False,
            ) as does_exist,
            override_settings(MODEL_FILE=does_exist),
        ):
            with mock.patch("documents.classifier.load_classifier") as mock_load:
                mock_load.side_effect = ClassifierModelCorruptError()
                Document.objects.create(
                    title="Test Document",
                )
                Tag.objects.create(
                    name="Test Tag",
                    matching_algorithm=Tag.MATCH_AUTO,
                )
                self.client.force_login(self.user)
                response = self.client.get(self.ENDPOINT)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    response.data["tasks"]["classifier_status"],
                    "ERROR",
                )
                self.assertIsNotNone(response.data["tasks"]["classifier_error"])

    def test_system_status_classifier_ok_no_objects(self):
        """
        GIVEN:
            - The classifier does not exist (and should not)
            - No documents nor objects with auto matching exist
        WHEN:
            - The user requests the system status
        THEN:
            - The response contains an OK classifier status
        """
        with override_settings(MODEL_FILE="does_not_exist"):
            self.client.force_login(self.user)
            response = self.client.get(self.ENDPOINT)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["tasks"]["classifier_status"], "OK")
