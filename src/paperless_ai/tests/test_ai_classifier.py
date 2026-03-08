import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import override_settings

from documents.models import Document
from paperless_ai.ai_classifier import build_prompt_with_rag
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_context_for_document


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
    mock_run_llm_query.return_value = {
        "title": "Test Title",
        "tags": ["test", "document"],
        "correspondents": ["John Doe"],
        "document_types": ["report"],
        "storage_paths": ["Reports"],
        "dates": ["2023-01-01"],
    }

    result = get_ai_document_classification(mock_document)

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
        prompt = build_prompt_without_rag(mock_document)
        assert "Additional context from similar documents:" not in prompt

        prompt = build_prompt_with_rag(mock_document)
        assert "Additional context from similar documents:" in prompt


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
