from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
class TestChatStreamingViewUnrestrictedFlag:
    """The document id filter may only be skipped (``unrestricted=True``) for
    a caller who can see every document, i.e. an active superuser.
    """

    @pytest.fixture
    def mocked_stream_chat(self, mocker: MockerFixture) -> mock.MagicMock:
        """AI enabled, with stream_chat_with_documents patched so the view
        never touches the real vector store; returns the patched callable so
        tests can inspect how it was called.
        """
        mocker.patch("documents.views.AIConfig").return_value.ai_enabled = True
        return mocker.patch(
            "documents.views.stream_chat_with_documents",
            return_value=iter(()),
        )

    @pytest.fixture
    def viewer_client(self, user_client: APIClient, regular_user: User) -> APIClient:
        """The conftest regular-user client, additionally granted
        view_document -- able to see every document without being a
        superuser.
        """
        regular_user.user_permissions.add(
            *Permission.objects.filter(codename="view_document"),
        )
        return user_client

    @pytest.mark.parametrize(
        ("client_fixture", "expected_unrestricted"),
        [
            pytest.param("admin_client", True, id="superuser_is_unrestricted"),
            pytest.param("viewer_client", False, id="regular_user_is_restricted"),
        ],
    )
    def test_unrestricted_only_for_superuser(
        self,
        request: pytest.FixtureRequest,
        mocked_stream_chat: mock.MagicMock,
        client_fixture: str,
        *,
        expected_unrestricted: bool,
    ) -> None:
        """
        GIVEN:
            - A superuser, or a regular user holding view_document
        WHEN:
            - They post a chat question with no document_id
        THEN:
            - stream_chat_with_documents is called with unrestricted=True for
              the superuser and unrestricted=False for the regular user, even
              though that user can view every document
        """
        client: APIClient = request.getfixturevalue(client_fixture)

        client.post(
            "/api/documents/chat/",
            data={"q": "What's in these documents?"},
            format="json",
        )

        assert (
            mocked_stream_chat.call_args.kwargs["unrestricted"] is expected_unrestricted
        )
