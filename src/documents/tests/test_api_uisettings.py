import json

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin


class TestApiUiSettings(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/ui_settings/"

    def setUp(self):
        super().setUp()
        self.test_user = User.objects.create_superuser(username="test")
        self.test_user.first_name = "Test"
        self.test_user.last_name = "User"
        self.test_user.save()
        self.client.force_authenticate(user=self.test_user)

    def test_api_get_ui_settings(self):
        response = self.client.get(self.ENDPOINT, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data["user"],
            {
                "id": self.test_user.id,
                "username": self.test_user.username,
                "is_staff": True,
                "is_superuser": True,
                "groups": [],
                "first_name": self.test_user.first_name,
                "last_name": self.test_user.last_name,
            },
        )
        self.assertDictEqual(
            response.data["settings"],
            {
                "app_title": None,
                "app_logo": None,
                "auditlog_enabled": True,
                "trash_delay": 30,
                "update_checking": {
                    "backend_setting": "default",
                },
            },
        )

    def test_api_set_ui_settings(self):
        settings = {
            "settings": {
                "dark_mode": {
                    "enabled": True,
                },
            },
        }

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(settings),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ui_settings = self.test_user.ui_settings
        self.assertDictEqual(
            ui_settings.settings,
            settings["settings"],
        )

    def test_api_set_ui_settings_insufficient_global_permissions(self):
        not_superuser = User.objects.create_user(username="test_not_superuser")
        self.client.force_authenticate(user=not_superuser)

        settings = {
            "settings": {
                "dark_mode": {
                    "enabled": True,
                },
            },
        }

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(settings),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_set_ui_settings_sufficient_global_permissions(self):
        not_superuser = User.objects.create_user(username="test_not_superuser")
        not_superuser.user_permissions.add(
            *Permission.objects.filter(codename__contains="uisettings"),
        )
        not_superuser.save()
        self.client.force_authenticate(user=not_superuser)

        settings = {
            "settings": {
                "dark_mode": {
                    "enabled": True,
                },
            },
        }

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(settings),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
