import os
from unittest import mock

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin
from paperless.settings import _parse_remote_user_settings


class TestRemoteUser(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(
            username="temp_admin",
        )

    def test_remote_user(self):
        """
        GIVEN:
            - Configured user
            - Remote user auth is enabled
        WHEN:
            - API call is made to get documents
        THEN:
            - Call succeeds
        """

        with mock.patch.dict(
            os.environ,
            {
                "PAPERLESS_ENABLE_HTTP_REMOTE_USER": "True",
            },
        ):
            _parse_remote_user_settings()

            response = self.client.get("/api/documents/")

            # 403 testing locally, 401 on ci...
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            )

            response = self.client.get(
                "/api/documents/",
                headers={
                    "Remote-User": self.user.username,
                },
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_remote_user_header_setting(self):
        """
        GIVEN:
            - Remote user header name is set
        WHEN:
            - Settings are parsed
        THEN:
            - Correct header name is returned
        """

        with mock.patch.dict(
            os.environ,
            {
                "PAPERLESS_ENABLE_HTTP_REMOTE_USER": "True",
                "PAPERLESS_HTTP_REMOTE_USER_HEADER_NAME": "HTTP_FOO",
            },
        ):
            header_name = _parse_remote_user_settings()

            self.assertEqual(header_name, "HTTP_FOO")
