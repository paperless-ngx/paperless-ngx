from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.conf import settings

from documents.models import Document
from paperless.models import LLMEmbeddingBackend
from paperless_ai.embedding import _normalize_llm_index_text
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_configured_model_name
from paperless_ai.embedding import get_embedding_model


@pytest.fixture
def mock_ai_config():
    with patch("paperless_ai.embedding.AIConfig") as MockAIConfig:
        MockAIConfig.return_value.llm_embedding_endpoint = None
        MockAIConfig.return_value.llm_allow_internal_endpoints = True
        MockAIConfig.return_value.llm_context_size = 8192
        yield MockAIConfig


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


def test_get_embedding_model_openai(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"
    mock_ai_config.return_value.llm_endpoint = "http://test-url"

    with patch(
        "llama_index.embeddings.openai_like.OpenAILikeEmbedding",
    ) as MockOpenAIEmbedding:
        model = get_embedding_model(mock_ai_config.return_value)
        MockOpenAIEmbedding.assert_called_once_with(
            model_name="text-embedding-3-small",
            api_key="test_api_key",
            api_base="http://test-url",
            http_client=ANY,
            async_http_client=ANY,
        )
        assert model == MockOpenAIEmbedding.return_value


def test_get_embedding_model_openai_prefers_embedding_endpoint(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"
    mock_ai_config.return_value.llm_embedding_endpoint = "http://embedding-url"
    mock_ai_config.return_value.llm_endpoint = "http://test-url"

    with patch(
        "llama_index.embeddings.openai_like.OpenAILikeEmbedding",
    ) as MockOpenAIEmbedding:
        model = get_embedding_model(mock_ai_config.return_value)
        MockOpenAIEmbedding.assert_called_once_with(
            model_name="text-embedding-3-small",
            api_key="test_api_key",
            api_base="http://embedding-url",
            http_client=ANY,
            async_http_client=ANY,
        )
        assert model == MockOpenAIEmbedding.return_value


def test_get_embedding_model_openai_blocks_internal_endpoint_when_disallowed(
    mock_ai_config,
):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"
    mock_ai_config.return_value.llm_endpoint = "http://127.0.0.1:11434"
    mock_ai_config.return_value.llm_allow_internal_endpoints = False

    with pytest.raises(ValueError, match="non-public address"):
        get_embedding_model(mock_ai_config.return_value)


def test_get_embedding_model_huggingface(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.HUGGINGFACE
    mock_ai_config.return_value.llm_embedding_model = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    with patch(
        "llama_index.embeddings.huggingface.HuggingFaceEmbedding",
    ) as MockHuggingFaceEmbedding:
        model = get_embedding_model(mock_ai_config.return_value)
        MockHuggingFaceEmbedding.assert_called_once_with(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_folder=str(settings.DATA_DIR / "hf_cache"),
        )
        assert model == MockHuggingFaceEmbedding.return_value


def test_get_embedding_model_ollama(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OLLAMA
    mock_ai_config.return_value.llm_embedding_model = "embeddinggemma"
    mock_ai_config.return_value.llm_endpoint = "http://test-url"

    with patch(
        "llama_index.embeddings.ollama.OllamaEmbedding",
    ) as MockOllamaEmbedding:
        model = get_embedding_model(mock_ai_config.return_value)
        MockOllamaEmbedding.assert_called_once_with(
            model_name="embeddinggemma",
            base_url="http://test-url",
            ollama_additional_kwargs={"num_ctx": 8192},
        )
        assert model == MockOllamaEmbedding.return_value


def test_get_embedding_model_ollama_prefers_embedding_endpoint(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OLLAMA
    mock_ai_config.return_value.llm_embedding_model = "embeddinggemma"
    mock_ai_config.return_value.llm_embedding_endpoint = "http://embedding-url"
    mock_ai_config.return_value.llm_endpoint = "http://test-url"

    with patch(
        "llama_index.embeddings.ollama.OllamaEmbedding",
    ) as MockOllamaEmbedding:
        model = get_embedding_model(mock_ai_config.return_value)
        MockOllamaEmbedding.assert_called_once_with(
            model_name="embeddinggemma",
            base_url="http://embedding-url",
            ollama_additional_kwargs={"num_ctx": 8192},
        )
        assert model == MockOllamaEmbedding.return_value


def test_get_embedding_model_ollama_blocks_internal_endpoint_when_disallowed(
    mock_ai_config,
):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OLLAMA
    mock_ai_config.return_value.llm_embedding_model = "embeddinggemma"
    mock_ai_config.return_value.llm_endpoint = "http://127.0.0.1:11434"
    mock_ai_config.return_value.llm_allow_internal_endpoints = False

    with pytest.raises(ValueError, match="non-public address"):
        get_embedding_model(mock_ai_config.return_value)


def test_get_embedding_model_invalid_backend(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "INVALID_BACKEND"

    with pytest.raises(
        ValueError,
        match="Unsupported embedding backend: INVALID_BACKEND",
    ):
        get_embedding_model(mock_ai_config.return_value)


@pytest.mark.parametrize(
    ("backend", "expected_default"),
    [
        (LLMEmbeddingBackend.OPENAI_LIKE, "text-embedding-3-small"),
        (LLMEmbeddingBackend.HUGGINGFACE, "sentence-transformers/all-MiniLM-L6-v2"),
        (LLMEmbeddingBackend.OLLAMA, "embeddinggemma"),
    ],
)
def test_get_configured_model_name_falls_back_to_backend_default(
    mock_ai_config,
    backend,
    expected_default,
):
    """When no model is explicitly configured, each backend has a distinct default."""
    config = mock_ai_config.return_value
    config.llm_embedding_backend = backend
    config.llm_embedding_model = None
    assert get_configured_model_name(config) == expected_default


def test_get_configured_model_name_explicit_overrides_default(mock_ai_config):
    """An explicit model name overrides the backend default for all backends."""
    config = mock_ai_config.return_value
    config.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    config.llm_embedding_model = "my-custom-model"
    # The backend default for OPENAI_LIKE is "text-embedding-3-small", so if
    # the explicit name was ignored we'd get the wrong result.
    assert get_configured_model_name(config) == "my-custom-model"


def test_build_llm_index_text(mock_document):
    with patch("documents.models.Note.objects.filter") as mock_notes_filter:
        mock_notes_filter.return_value = [
            MagicMock(note="Note1"),
            MagicMock(note="Note2"),
        ]

        result = build_llm_index_text(mock_document)

        # Structured fields live in node.metadata for LLM context — not body text
        assert "Title: Test Title" not in result
        assert "Created: 2023-01-01" not in result
        assert "Tags: Tag1, Tag2" not in result
        assert "Document Type: Invoice" not in result
        assert "Correspondent: Test Correspondent" not in result

        # Fields without a metadata equivalent stay in body text
        assert "Filename: test_file.pdf" in result
        assert "Notes: Note1,Note2" in result
        assert "Content:\n\nThis is the document content." in result
        assert "Custom Field - Field1: Value1\nCustom Field - Field2: Value2" in result


def test_build_llm_index_text_normalizes_ocr_punctuation_runs(mock_document):
    mock_document.content = (
        "Introduction ................................................ 7\n"
        "Hardware Limitation ________________________________________ 9\n"
        "Keep short punctuation like INV-100 and ellipses..."
    )

    with patch("documents.models.Note.objects.filter", return_value=[]):
        result = build_llm_index_text(mock_document)

    assert "Introduction 7" in result
    assert "Hardware Limitation 9" in result
    assert "INV-100" in result
    assert "ellipses..." in result


def test_normalize_llm_index_text_collapses_ocr_leaders_without_joining_lines():
    assert _normalize_llm_index_text("A........B\nC____D----E") == "A B\nC D E"


def test_normalize_llm_index_text_collapses_non_breaking_spaces():
    assert _normalize_llm_index_text("A\u00a0........\u00a0B") == "A B"
