import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import override_settings

from documents.models import Document
from paperless.ai.ai_classifier import get_ai_document_classification
from paperless.ai.ai_classifier import parse_ai_response


@pytest.fixture
def mock_document():
    return Document(filename="test.pdf", content="This is a test document content.")


@pytest.mark.django_db
@patch("paperless.ai.client.AIClient.run_llm_query")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_success(mock_run_llm_query, mock_document):
    mock_run_llm_query.return_value.text = json.dumps(
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    result = get_ai_document_classification(mock_document)

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@pytest.mark.django_db
@patch("paperless.ai.client.AIClient.run_llm_query")
def test_get_ai_document_classification_failure(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = Exception("LLM query failed")

    # assert raises an exception
    with pytest.raises(Exception):
        get_ai_document_classification(mock_document)


def test_parse_llm_classification_response_invalid_json():
    mock_response = MagicMock()
    mock_response.text = "Invalid JSON response"

    result = parse_ai_response(mock_response)

    assert result == {}


@pytest.mark.django_db
@patch("paperless.ai.client.AIClient.run_llm_query")
@patch("paperless.ai.ai_classifier.build_prompt_with_rag")
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
@patch("paperless.ai.client.AIClient.run_llm_query")
@patch("paperless.ai.ai_classifier.build_prompt_without_rag")
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
