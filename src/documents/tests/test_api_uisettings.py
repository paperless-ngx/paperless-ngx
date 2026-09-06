import json

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin
from paperless.version import __full_version_str__


class TestApiUiSettings(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/ui_settings/"

    def setUp(self) -> None:
        super().setUp()
        self.test_user = User.objects.create_superuser(username="test")
        self.test_user.first_name = "Test"
        self.test_user.last_name = "User"
        self.test_user.save()
        self.client.force_authenticate(user=self.test_user)

    @override_settings(
        APP_TITLE=None,
        APP_LOGO=None,
        AUDIT_LOG_ENABLED=True,
        EMPTY_TRASH_DELAY=30,
        ENABLE_UPDATE_CHECK="default",
        EMAIL_ENABLED=False,
        GMAIL_OAUTH_ENABLED=False,
        OUTLOOK_OAUTH_ENABLED=False,
    )
    def test_api_get_ui_settings(self) -> None:
        response = self.client.get(self.ENDPOINT, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.maxDiff = None
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
                "version": __full_version_str__,
                "app_title": None,
                "app_logo": None,
                "auditlog_enabled": True,
                "trash_delay": 30,
                "update_checking": {
                    "backend_setting": "default",
                },
                "email_enabled": False,
                "ai_enabled": False,
                "remote_ocr": {
                    "configured": False,
                    "mode": "always",
                },
            },
        )

    def test_api_set_ui_settings(self) -> None:
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

    def test_api_set_ui_settings_insufficient_global_permissions(self) -> None:
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

    def test_api_set_ui_settings_sufficient_global_permissions(self) -> None:
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

    def test_settings_must_be_dict(self) -> None:
        """
        GIVEN:
            - API request to update ui_settings with settings not being a dict
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "settings": "not a dict",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Expected a dictionary",
            str(response.data["settings"]),
        )

    @override_settings(
        REMOTE_OCR_ENGINE="azureai",
        REMOTE_OCR_API_KEY="somekey",
        REMOTE_OCR_ENDPOINT="https://example.cognitiveservices.azure.com",
        REMOTE_OCR_MODE="workflow_only",
    )
    def test_settings_reports_remote_ocr_when_configured(self) -> None:
        """
        GIVEN:
            - A fully configured remote OCR engine in workflow_only mode
        WHEN:
            - The ui_settings endpoint is called
        THEN:
            - The UI is told remote OCR is available and selective, so it can
              offer it where it would actually change something
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["settings"]["remote_ocr"],
            {"configured": True, "mode": "workflow_only"},
        )

    @override_settings(
        REMOTE_OCR_ENGINE="azureai",
        REMOTE_OCR_API_KEY=None,
        REMOTE_OCR_ENDPOINT=None,
    )
    def test_settings_reports_remote_ocr_incompletely_configured(self) -> None:
        """
        GIVEN:
            - An engine named but missing its endpoint and API key
        WHEN:
            - The ui_settings endpoint is called
        THEN:
            - It is reported as not configured, matching what the parser
              registry will actually do
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["settings"]["remote_ocr"]["configured"])

    @override_settings(
        OAUTH_CALLBACK_BASE_URL="http://localhost:8000",
        GMAIL_OAUTH_CLIENT_ID="abc123",
        GMAIL_OAUTH_CLIENT_SECRET="def456",
        GMAIL_OAUTH_ENABLED=True,
        OUTLOOK_OAUTH_CLIENT_ID="ghi789",
        OUTLOOK_OAUTH_CLIENT_SECRET="jkl012",
        OUTLOOK_OAUTH_ENABLED=True,
    )
    def test_settings_includes_oauth_urls_if_enabled(self) -> None:
        response = self.client.get(self.ENDPOINT, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(
            response.data["settings"]["gmail_oauth_url"],
        )
        self.assertIsNotNone(
            response.data["settings"]["outlook_oauth_url"],
        )
