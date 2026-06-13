from types import SimpleNamespace

import pytest
import pytest_mock
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from documents.models import Document


@pytest.mark.django_db
class TestSuggestionsHintWiring:
    @pytest.fixture
    def user(self) -> User:
        return User.objects.create_superuser(username="admin", password="pw")

    @pytest.fixture
    def document(self, user: User) -> Document:
        return Document.objects.create(
            title="Doc",
            content="content",
            checksum="abc123",
            mime_type="application/pdf",
        )

    @pytest.fixture
    def api_client(self, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_hints_passed_to_classifier_and_matchers(
        self,
        api_client: APIClient,
        document: Document,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        hints = {
            "tags": ["Bloodwork"],
            "document_types": [],
            "correspondents": [],
            "storage_paths": [],
        }
        mocker.patch(
            "documents.views.get_taxonomy_hints_for_document",
            return_value=hints,
        )
        mocker.patch(
            "documents.views.AIConfig",
            return_value=SimpleNamespace(
                ai_enabled=True,
                llm_backend="ollama",
                llm_output_language=None,
            ),
        )
        # No cached suggestion -> the view reaches the classifier path.
        mocker.patch(
            "documents.views.get_llm_suggestion_cache",
            return_value=None,
        )
        mocker.patch("documents.views.set_llm_suggestions_cache")
        classify = mocker.patch(
            "documents.views.get_ai_document_classification",
            return_value={
                "title": "Doc",
                "tags": ["Bloodwork"],
                "correspondents": [],
                "document_types": [],
                "storage_paths": [],
                "dates": [],
            },
        )
        match_tags = mocker.patch(
            "documents.views.match_tags_by_name",
            return_value=[],
        )
        mocker.patch("documents.views.match_correspondents_by_name", return_value=[])
        mocker.patch("documents.views.match_document_types_by_name", return_value=[])
        mocker.patch("documents.views.match_storage_paths_by_name", return_value=[])

        response = api_client.get(f"/api/documents/{document.pk}/ai_suggestions/")

        assert response.status_code == 200
        assert classify.call_args.kwargs["hints"] == hints
        assert match_tags.call_args.kwargs["hinted_names"] == {"Bloodwork"}
