import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_mock
from django.contrib.auth.models import User
from django.test import override_settings

from documents.models import Document
from paperless.config import AIConfig
from paperless_ai.ai_classifier import build_localization_prompt
from paperless_ai.ai_classifier import build_prompt_with_rag
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_context_for_document
from paperless_ai.ai_classifier import get_language_name


@pytest.fixture
def mock_document():
    doc = MagicMock(spec=Document)
    doc.title = "Test Title"
    doc.filename = "test_file.pdf"
    doc.created = "2023-01-01"
    doc.added = "2023-01-02"
    doc.modified = "2023-01-03"

    tag1 = MagicMock()
    tag1.name = "Tag1"
    tag2 = MagicMock()
    tag2.name = "Tag2"
    doc.tags.all = MagicMock(return_value=[tag1, tag2])

    doc.document_type = MagicMock()
    doc.document_type.name = "Invoice"
    doc.correspondent = MagicMock()
    doc.correspondent.name = "Test Correspondent"
    doc.archive_serial_number = "12345"
    doc.content = "This is the document content."

    cf1 = MagicMock(__str__=lambda x: "Value1")
    cf1.field = MagicMock()
    cf1.field.name = "Field1"
    cf1.value = "Value1"
    cf2 = MagicMock(__str__=lambda x: "Value2")
    cf2.field = MagicMock()
    cf2.field.name = "Field2"
    cf2.value = "Value2"
    doc.custom_fields.all = MagicMock(return_value=[cf1, cf2])

    return doc


@pytest.fixture
def mock_similar_documents():
    doc1 = MagicMock()
    doc1.content = "Content of document 1"
    doc1.title = "Title 1"
    doc1.filename = "file1.txt"

    doc2 = MagicMock()
    doc2.content = "Content of document 2"
    doc2.title = None
    doc2.filename = "file2.txt"

    doc3 = MagicMock()
    doc3.content = None
    doc3.title = None
    doc3.filename = None

    return [doc1, doc2, doc3]


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_success(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = [
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
        {
            "title": "Testtitel",
            "tags": ["Test", "Document"],
            "correspondents": ["Jane Doe"],
            "document_types": ["Bericht"],
            "storage_paths": ["Berichte"],
            "dates": ["2024-01-01"],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Testtitel"
    assert result["tags"] == ["Test", "Document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["Bericht"]
    assert result["storage_paths"] == ["Berichte"]
    assert result["dates"] == ["2023-01-01"]
    classification_prompt = mock_run_llm_query.call_args_list[0].args[0]
    localization_prompt = mock_run_llm_query.call_args_list[1].args[0]
    assert "Write suggested titles" not in classification_prompt
    assert "Rewrite only these generated fields in German" in localization_prompt
    assert "Do not translate correspondents or dates" in localization_prompt


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_keeps_originals_when_localization_empty(
    mock_run_llm_query,
    mock_document,
):
    mock_run_llm_query.side_effect = [
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
        {
            "title": "",
            "tags": [],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
            "dates": [],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
def test_get_ai_document_classification_failure(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = Exception("LLM query failed")

    # assert raises an exception
    with pytest.raises(Exception):
        get_ai_document_classification(mock_document)


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_with_rag")
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_EMBEDDING_MODEL="some_model",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_use_rag_if_configured(
    mock_build_prompt_with_rag,
    mock_run_llm_query,
    mock_document,
):
    mock_build_prompt_with_rag.return_value = "Prompt with RAG"
    mock_run_llm_query.return_value.text = json.dumps({})
    get_ai_document_classification(mock_document)
    mock_build_prompt_with_rag.assert_called_once()


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_without_rag")
@patch("paperless.config.AIConfig")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_use_without_rag_if_not_configured(
    mock_ai_config,
    mock_build_prompt_without_rag,
    mock_run_llm_query,
    mock_document,
):
    mock_ai_config.llm_embedding_backend = None
    mock_build_prompt_without_rag.return_value = "Prompt without RAG"
    mock_run_llm_query.return_value.text = json.dumps({})
    get_ai_document_classification(mock_document)
    mock_build_prompt_without_rag.assert_called_once()


@pytest.mark.django_db
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_prompt_with_without_rag(mock_document):
    with patch(
        "paperless_ai.ai_classifier.get_context_for_document",
        return_value="Context from similar documents",
    ):
        config = AIConfig()
        prompt = build_prompt_without_rag(mock_document, config)
        assert "Additional context from similar documents" not in prompt
        assert "for generated" not in prompt

        prompt = build_prompt_with_rag(mock_document, config)
        assert "Additional context from similar documents" in prompt

        prompt = build_localization_prompt(
            {
                "title": "Test Title",
                "tags": ["test", "document"],
                "correspondents": ["John Doe"],
                "document_types": ["report"],
                "storage_paths": ["Reports"],
                "dates": ["2023-01-01"],
            },
            output_language="de-de",
        )
        assert "Rewrite only these generated fields in German" in prompt
        assert "Do not translate correspondents or dates" in prompt


def test_get_language_name_falls_back_to_language_code():
    assert get_language_name("zz-zz") == "zz-zz"


def test_build_localization_prompt_preserves_unicode_characters():
    prompt = build_localization_prompt(
        {
            "title": "Gebührenbescheid",
            "tags": [],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
            "dates": [],
        },
        output_language="de-de",
    )

    assert "Gebührenbescheid" in prompt
    assert "\\u00fc" not in prompt


@patch("paperless_ai.ai_classifier.query_similar_documents")
def test_get_context_for_document(
    mock_query_similar_documents,
    mock_document,
    mock_similar_documents,
):
    mock_query_similar_documents.return_value = mock_similar_documents

    result = get_context_for_document(mock_document, max_docs=2)

    expected_result = (
        "TITLE: Title 1\nContent of document 1\n\n"
        "TITLE: file2.txt\nContent of document 2"
    )
    assert result == expected_result
    mock_query_similar_documents.assert_called_once()


def test_get_context_for_document_no_similar_docs(mock_document):
    with patch("paperless_ai.ai_classifier.query_similar_documents", return_value=[]):
        result = get_context_for_document(mock_document)
        assert result == ""


class TestGetContextForDocumentVisibility:
    """get_context_for_document must not materialize every visible document
    id for a user who can already see the whole library: a superuser (like
    no user at all) gets document_ids=None (no restriction) straight
    through to query_similar_documents(), instead of a full-library IN
    filter that is wasteful at best and, past ~32,763 documents, a hard
    sqlite3.OperationalError at worst (SQLite's bound-parameter limit).
    """

    def test_skips_permission_lookup_for_superuser(
        self,
        mock_document: MagicMock,
        mock_similar_documents: list[MagicMock],
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A superuser
        WHEN:
            - get_context_for_document() is called
        THEN:
            - get_objects_for_user_owner_aware() is never called, and
              query_similar_documents() is called with document_ids=None
        """
        mock_query = mocker.patch(
            "paperless_ai.ai_classifier.query_similar_documents",
            return_value=mock_similar_documents,
        )
        mock_get_objects = mocker.patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        )
        user = mocker.MagicMock(spec=User)
        user.is_superuser = True

        get_context_for_document(mock_document, user, max_docs=2)

        mock_get_objects.assert_not_called()
        assert mock_query.call_args.kwargs["document_ids"] is None

    def test_skips_permission_lookup_when_no_user(
        self,
        mock_document: MagicMock,
        mock_similar_documents: list[MagicMock],
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - No user (user=None)
        WHEN:
            - get_context_for_document() is called
        THEN:
            - get_objects_for_user_owner_aware() is never called, and
              query_similar_documents() is called with document_ids=None
        """
        mock_query = mocker.patch(
            "paperless_ai.ai_classifier.query_similar_documents",
            return_value=mock_similar_documents,
        )
        mock_get_objects = mocker.patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        )

        get_context_for_document(mock_document, None, max_docs=2)

        mock_get_objects.assert_not_called()
        assert mock_query.call_args.kwargs["document_ids"] is None

    def test_restricts_to_visible_documents_for_non_superuser(
        self,
        mock_document: MagicMock,
        mock_similar_documents: list[MagicMock],
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A non-superuser with a specific set of visible documents
        WHEN:
            - get_context_for_document() is called
        THEN:
            - query_similar_documents() is called with exactly that user's
              visible document ids, unchanged from before this optimization
        """
        mock_query = mocker.patch(
            "paperless_ai.ai_classifier.query_similar_documents",
            return_value=mock_similar_documents,
        )
        mock_queryset = mocker.MagicMock()
        mock_queryset.values_list.return_value = [1, 2, 3]
        mock_get_objects = mocker.patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
            return_value=mock_queryset,
        )
        user = mocker.MagicMock(spec=User)
        user.is_superuser = False

        get_context_for_document(mock_document, user, max_docs=2)

        mock_get_objects.assert_called_once_with(user, "view_document", Document)
        assert mock_query.call_args.kwargs["document_ids"] == [1, 2, 3]
