from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from paperless import version


class TestSystemStatusView(APITestCase):
    ENDPOINT = "/api/status/"

    def test_system_status_insufficient_permissions(self):
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_system_status(self):
        user = User.objects.create_superuser(
            username="temp_admin",
        )
        self.client.force_login(user)
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
        self.assertEqual(response.data["redis"]["url"], "redis://localhost:6379")
        self.assertEqual(response.data["redis"]["status"], "ERROR")
        self.assertIsNotNone(response.data["redis"]["error"])
