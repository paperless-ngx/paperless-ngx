import json
from unittest.mock import patch

import pytest

from documents.models import Document
from paperless.ai.ai_classifier import get_ai_document_classification
from paperless.ai.ai_classifier import parse_ai_classification_response


@pytest.fixture
def mock_document():
    return Document(filename="test.pdf", content="This is a test document content.")


@patch("paperless.ai.ai_classifier.run_llm_query")
def test_get_ai_document_classification_success(mock_run_llm_query, mock_document):
    mock_response = json.dumps(
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )
    mock_run_llm_query.return_value = mock_response

    result = get_ai_document_classification(mock_document)

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@patch("paperless.ai.ai_classifier.run_llm_query")
def test_get_ai_document_classification_failure(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = Exception("LLM query failed")

    result = get_ai_document_classification(mock_document)

    assert result == {}


def test_parse_llm_classification_response_valid():
    mock_response = json.dumps(
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    result = parse_ai_classification_response(mock_response)

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


def test_parse_llm_classification_response_invalid_json():
    mock_response = "Invalid JSON"

    result = parse_ai_classification_response(mock_response)

    assert result == {}


def test_parse_llm_classification_response_partial_data():
    mock_response = json.dumps(
        {
            "title": "Partial Data",
            "tags": ["partial"],
            "correspondents": "Jane Doe",
            "document_types": "note",
            "storage_paths": [],
            "dates": [],
        },
    )

    result = parse_ai_classification_response(mock_response)

    assert result["title"] == "Partial Data"
    assert result["tags"] == ["partial"]
    assert result["correspondents"] == ["Jane Doe"]
    assert result["document_types"] == ["note"]
    assert result["storage_paths"] == []
    assert result["dates"] == []
