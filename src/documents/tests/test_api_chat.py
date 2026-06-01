from __future__ import annotations

from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from documents.tests.factories import DocumentFactory
from documents.tests.factories import UserFactory


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


@pytest.mark.django_db
class TestChatStreamingViewDocumentExistenceOracle:
    def _mock_ai_enabled(self) -> mock.MagicMock:
        m = mock.MagicMock()
        m.ai_enabled = True
        return m

    def test_nonexistent_document_returns_404(self) -> None:
        user: User = UserFactory.create(superuser=True)
        client = APIClient()
        client.force_authenticate(user=user)

        with mock.patch(
            "documents.views.AIConfig",
            return_value=self._mock_ai_enabled(),
        ):
            resp = client.post(
                "/api/documents/chat/",
                {"q": "hello", "document_id": 99999999},
                format="json",
            )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthorized_document_returns_404(self) -> None:
        owner: User = UserFactory.create()
        requester: User = UserFactory.create()
        requester.user_permissions.add(
            *Permission.objects.filter(codename="view_document"),
        )
        doc = DocumentFactory.create(owner=owner)
        client = APIClient()
        client.force_authenticate(user=requester)

        with mock.patch(
            "documents.views.AIConfig",
            return_value=self._mock_ai_enabled(),
        ):
            resp = client.post(
                "/api/documents/chat/",
                {"q": "hello", "document_id": doc.pk},
                format="json",
            )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
