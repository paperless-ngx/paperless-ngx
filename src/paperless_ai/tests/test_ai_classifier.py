import pytest
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from documents.models import Document
from paperless_ai.ai_classifier import build_prompt_with_rag
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_context_for_document


@pytest.mark.django_db
def test_get_ai_document_classification_success(
    settings: SettingsWrapper,
    mocker: MockerFixture,
    document: Document,
) -> None:
    settings.LLM_BACKEND = "ollama"
    settings.LLM_MODEL = "some_model"
    mock_run = mocker.patch("paperless_ai.client.AIClient.run_llm_query")
    mock_run.return_value = {
        "title": "Test Title",
        "tags": ["test", "document"],
        "correspondents": ["John Doe"],
        "document_types": ["report"],
        "storage_paths": ["Reports"],
        "dates": ["2023-01-01"],
    }

    result = get_ai_document_classification(document)

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@pytest.mark.django_db
def test_get_ai_document_classification_failure(
    mocker: MockerFixture,
    document: Document,
) -> None:
    mocker.patch(
        "paperless_ai.client.AIClient.run_llm_query",
        side_effect=Exception("LLM query failed"),
    )
    with pytest.raises(Exception):
        get_ai_document_classification(document)


@pytest.mark.django_db
def test_use_rag_if_configured(
    settings: SettingsWrapper,
    mocker: MockerFixture,
    document: Document,
) -> None:
    settings.LLM_EMBEDDING_BACKEND = "huggingface"
    settings.LLM_EMBEDDING_MODEL = "some_model"
    settings.LLM_BACKEND = "ollama"
    settings.LLM_MODEL = "some_model"
    mock_build = mocker.patch("paperless_ai.ai_classifier.build_prompt_with_rag")
    mock_build.return_value = "Prompt with RAG"
    mocker.patch("paperless_ai.client.AIClient.run_llm_query", return_value={})
    get_ai_document_classification(document)
    mock_build.assert_called_once()


@pytest.mark.django_db
def test_use_without_rag_if_not_configured(
    settings: SettingsWrapper,
    mocker: MockerFixture,
    document: Document,
) -> None:
    settings.LLM_BACKEND = "ollama"
    settings.LLM_MODEL = "some_model"
    mock_ai_config = mocker.patch("paperless.config.AIConfig")
    mock_build = mocker.patch("paperless_ai.ai_classifier.build_prompt_without_rag")
    mocker.patch("paperless_ai.client.AIClient.run_llm_query", return_value={})
    mock_ai_config.llm_embedding_backend = None
    mock_build.return_value = "Prompt without RAG"
    get_ai_document_classification(document)
    mock_build.assert_called_once()


def test_prompt_with_without_rag(mocker: MockerFixture, document: Document) -> None:
    mocker.patch(
        "paperless_ai.ai_classifier.get_context_for_document",
        return_value="Context from similar documents",
    )
    prompt = build_prompt_without_rag(document)
    assert "Additional context from similar documents:" not in prompt

    prompt = build_prompt_with_rag(document)
    assert "Additional context from similar documents:" in prompt


def test_get_context_for_document(
    mocker: MockerFixture,
    document: Document,
    similar_documents: list[Document],
) -> None:
    mocker.patch(
        "paperless_ai.ai_classifier.query_similar_documents",
        return_value=similar_documents,
    )
    result = get_context_for_document(document, max_docs=2)
    assert result == (
        "TITLE: Title 1\nContent of document 1\n\n"
        "TITLE: file2.txt\nContent of document 2"
    )


def test_get_context_for_document_no_similar_docs(
    mocker: MockerFixture,
    document: Document,
) -> None:
    mocker.patch(
        "paperless_ai.ai_classifier.query_similar_documents",
        return_value=[],
    )
    assert get_context_for_document(document) == ""
