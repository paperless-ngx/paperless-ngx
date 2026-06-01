from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase


class TestChatStreamingViewInputValidation(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def _mock_ai_enabled(self) -> mock.MagicMock:
        """Return a mock AIConfig instance with ai_enabled=True."""
        m = mock.MagicMock()
        m.ai_enabled = True
        return m

    def test_oversized_question_is_rejected(self) -> None:
        with mock.patch(
            "documents.views.AIConfig",
            return_value=self._mock_ai_enabled(),
        ):
            resp = self.client.post(
                "/api/documents/chat/",
                {"q": "x" * 4001},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_question_is_rejected(self) -> None:
        with mock.patch(
            "documents.views.AIConfig",
            return_value=self._mock_ai_enabled(),
        ):
            resp = self.client.post(
                "/api/documents/chat/",
                {},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
