import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.conf import settings

from documents.models import Document
from paperless.models import LLMEmbeddingBackend
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_embedding_dim
from paperless_ai.embedding import get_embedding_model


@pytest.fixture
def mock_ai_config():
    with patch("paperless_ai.embedding.AIConfig") as MockAIConfig:
        yield MockAIConfig


@pytest.fixture
def temp_llm_index_dir(tmp_path):
    original_dir = settings.LLM_INDEX_DIR
    settings.LLM_INDEX_DIR = tmp_path
    yield tmp_path
    settings.LLM_INDEX_DIR = original_dir


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
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"

    with patch("paperless_ai.embedding.OpenAIEmbedding") as MockOpenAIEmbedding:
        model = get_embedding_model()
        MockOpenAIEmbedding.assert_called_once_with(
            model="text-embedding-3-small",
            api_key="test_api_key",
        )
        assert model == MockOpenAIEmbedding.return_value


def test_get_embedding_model_huggingface(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.HUGGINGFACE
    mock_ai_config.return_value.llm_embedding_model = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    with patch(
        "paperless_ai.embedding.HuggingFaceEmbedding",
    ) as MockHuggingFaceEmbedding:
        model = get_embedding_model()
        MockHuggingFaceEmbedding.assert_called_once_with(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
        assert model == MockHuggingFaceEmbedding.return_value


def test_get_embedding_model_invalid_backend(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "INVALID_BACKEND"

    with pytest.raises(
        ValueError,
        match="Unsupported embedding backend: INVALID_BACKEND",
    ):
        get_embedding_model()


def test_get_embedding_dim_infers_and_saves(temp_llm_index_dir, mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "openai"
    mock_ai_config.return_value.llm_embedding_model = None

    class DummyEmbedding:
        def get_text_embedding(self, text):
            return [0.0] * 7

    with patch(
        "paperless_ai.embedding.get_embedding_model",
        return_value=DummyEmbedding(),
    ) as mock_get:
        dim = get_embedding_dim()
        mock_get.assert_called_once()

    assert dim == 7
    meta = json.loads((temp_llm_index_dir / "meta.json").read_text())
    assert meta == {"embedding_model": "text-embedding-3-small", "dim": 7}


def test_get_embedding_dim_reads_existing_meta(temp_llm_index_dir, mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "openai"
    mock_ai_config.return_value.llm_embedding_model = None

    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "text-embedding-3-small", "dim": 11}),
    )

    with patch("paperless_ai.embedding.get_embedding_model") as mock_get:
        assert get_embedding_dim() == 11
        mock_get.assert_not_called()


def test_get_embedding_dim_raises_on_model_change(temp_llm_index_dir, mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "openai"
    mock_ai_config.return_value.llm_embedding_model = None

    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "old", "dim": 11}),
    )

    with pytest.raises(
        RuntimeError,
        match="Embedding model changed from old to text-embedding-3-small",
    ):
        get_embedding_dim()


def test_build_llm_index_text(mock_document):
    with patch("documents.models.Note.objects.filter") as mock_notes_filter:
        mock_notes_filter.return_value = [
            MagicMock(note="Note1"),
            MagicMock(note="Note2"),
        ]

        result = build_llm_index_text(mock_document)

        assert "Title: Test Title" in result
        assert "Filename: test_file.pdf" in result
        assert "Created: 2023-01-01" in result
        assert "Tags: Tag1, Tag2" in result
        assert "Document Type: Invoice" in result
        assert "Correspondent: Test Correspondent" in result
        assert "Notes: Note1,Note2" in result
        assert "Content:\n\nThis is the document content." in result
        assert "Custom Field - Field1: Value1\nCustom Field - Field2: Value2" in result
