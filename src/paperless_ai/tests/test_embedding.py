import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import TagFactory
from paperless.config import AIConfig
from paperless.models import LLMEmbeddingBackend
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_embedding_dim
from paperless_ai.embedding import get_embedding_model


@pytest.fixture
def mock_ai_config(mocker: MockerFixture) -> MagicMock:
    mock = mocker.patch("paperless_ai.embedding.AIConfig", spec=AIConfig)
    mock.return_value.llm_allow_internal_endpoints = True
    return mock


@pytest.fixture
def full_document(db) -> Document:
    tag1 = TagFactory(name="Tag1")
    tag2 = TagFactory(name="Tag2")
    doc = DocumentFactory(
        title="Test Title",
        filename="test_file.pdf",
        created=datetime.date(2023, 1, 1),
        correspondent=CorrespondentFactory(name="Test Correspondent"),
        document_type=DocumentTypeFactory(name="Invoice"),
        archive_serial_number=12345,
        content="This is the document content.",
    )
    doc.tags.add(tag1, tag2)
    cf1 = CustomField.objects.create(
        name="Field1",
        data_type=CustomField.FieldDataType.STRING,
    )
    cf2 = CustomField.objects.create(
        name="Field2",
        data_type=CustomField.FieldDataType.STRING,
    )
    CustomFieldInstance.objects.create(document=doc, field=cf1, value_text="Value1")
    CustomFieldInstance.objects.create(document=doc, field=cf2, value_text="Value2")
    Note.objects.create(document=doc, note="Note1")
    Note.objects.create(document=doc, note="Note2")
    return doc


def test_get_embedding_model_openai(
    mock_ai_config: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"
    mock_ai_config.return_value.llm_endpoint = "http://test-url"
    mock_cls = mocker.patch("llama_index.embeddings.openai_like.OpenAILikeEmbedding")
    model = get_embedding_model()
    mock_cls.assert_called_once_with(
        model_name="text-embedding-3-small",
        api_key="test_api_key",
        api_base="http://test-url",
    )
    assert model == mock_cls.return_value


def test_get_embedding_model_openai_blocks_internal_endpoint_when_disallowed(
    mock_ai_config: MagicMock,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"
    mock_ai_config.return_value.llm_endpoint = "http://127.0.0.1:11434"
    mock_ai_config.return_value.llm_allow_internal_endpoints = False
    with pytest.raises(ValueError, match="non-public address"):
        get_embedding_model()


def test_get_embedding_model_huggingface(
    mock_ai_config: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.HUGGINGFACE
    mock_ai_config.return_value.llm_embedding_model = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    mock_cls = mocker.patch("llama_index.embeddings.huggingface.HuggingFaceEmbedding")
    model = get_embedding_model()
    mock_cls.assert_called_once_with(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )
    assert model == mock_cls.return_value


def test_get_embedding_model_invalid_backend(mock_ai_config: MagicMock) -> None:
    mock_ai_config.return_value.llm_embedding_backend = "INVALID_BACKEND"
    with pytest.raises(
        ValueError,
        match="Unsupported embedding backend: INVALID_BACKEND",
    ):
        get_embedding_model()


def test_get_embedding_dim_infers_and_saves(
    temp_llm_index_dir: Path,
    mock_ai_config: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = "openai-like"
    mock_ai_config.return_value.llm_embedding_model = None

    class DummyEmbedding:
        def get_text_embedding(self, text: str) -> list[float]:
            return [0.0] * 7

    mock_get = mocker.patch(
        "paperless_ai.embedding.get_embedding_model",
        return_value=DummyEmbedding(),
    )
    dim = get_embedding_dim()
    mock_get.assert_called_once()
    assert dim == 7
    meta = json.loads((temp_llm_index_dir / "meta.json").read_text())
    assert meta == {"embedding_model": "text-embedding-3-small", "dim": 7}


def test_get_embedding_dim_reads_existing_meta(
    temp_llm_index_dir: Path,
    mock_ai_config: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = "openai-like"
    mock_ai_config.return_value.llm_embedding_model = None
    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "text-embedding-3-small", "dim": 11}),
    )
    mock_get = mocker.patch("paperless_ai.embedding.get_embedding_model")
    assert get_embedding_dim() == 11
    mock_get.assert_not_called()


def test_get_embedding_dim_raises_on_model_change(
    temp_llm_index_dir: Path,
    mock_ai_config: MagicMock,
) -> None:
    mock_ai_config.return_value.llm_embedding_backend = "openai-like"
    mock_ai_config.return_value.llm_embedding_model = None
    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "old", "dim": 11}),
    )
    with pytest.raises(
        RuntimeError,
        match="Embedding model changed from old to text-embedding-3-small",
    ):
        get_embedding_dim()


@pytest.mark.django_db
def test_build_llm_index_text(full_document: Document) -> None:
    result = build_llm_index_text(full_document)
    assert "Title: Test Title" in result
    assert "Filename: test_file.pdf" in result
    assert "Created: 2023-01-01" in result
    assert "Tags: Tag1, Tag2" in result
    assert "Document Type: Invoice" in result
    assert "Correspondent: Test Correspondent" in result
    assert "Notes: Note1,Note2" in result
    assert "Content:\n\nThis is the document content." in result
    assert "Custom Field - Field1: Value1\nCustom Field - Field2: Value2" in result
