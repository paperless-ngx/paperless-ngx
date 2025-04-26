from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from paperless.ai.embedding import build_llm_index_text
from paperless.ai.embedding import get_embedding_dim
from paperless.ai.embedding import get_embedding_model
from paperless.ai.indexing import load_index
from paperless.ai.indexing import query_similar_documents
from paperless.ai.rag import get_context_for_document
from paperless.models import LLMEmbeddingBackend


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


@patch("paperless.ai.rag.query_similar_documents")
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
    with patch("paperless.ai.rag.query_similar_documents", return_value=[]):
        result = get_context_for_document(mock_document)
        assert result == ""


# Embedding


@pytest.fixture
def mock_ai_config():
    with patch("paperless.ai.embedding.AIConfig") as MockAIConfig:
        yield MockAIConfig


def test_get_embedding_model_openai(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = LLMEmbeddingBackend.OPENAI
    mock_ai_config.return_value.llm_embedding_model = "text-embedding-3-small"
    mock_ai_config.return_value.llm_api_key = "test_api_key"

    with patch("paperless.ai.embedding.OpenAIEmbedding") as MockOpenAIEmbedding:
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
        "paperless.ai.embedding.HuggingFaceEmbedding",
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


def test_get_embedding_dim_openai(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "openai"
    mock_ai_config.return_value.llm_embedding_model = None

    assert get_embedding_dim() == 1536


def test_get_embedding_dim_huggingface(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "huggingface"
    mock_ai_config.return_value.llm_embedding_model = None

    assert get_embedding_dim() == 384


def test_get_embedding_dim_unknown_model(mock_ai_config):
    mock_ai_config.return_value.llm_embedding_backend = "openai"
    mock_ai_config.return_value.llm_embedding_model = "unknown-model"

    with pytest.raises(ValueError, match="Unknown embedding model: unknown-model"):
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


# Indexing


@pytest.fixture
def mock_settings(settings):
    settings.LLM_INDEX_DIR = "/fake/path"
    return settings


class FakeEmbedding(BaseEmbedding):
    # TODO: gotta be a better way to do this
    def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def test_load_index(mock_settings):
    with (
        patch("paperless.ai.indexing.FaissVectorStore.from_persist_dir") as mock_faiss,
        patch("paperless.ai.indexing.get_embedding_model") as mock_get_embed_model,
        patch(
            "paperless.ai.indexing.StorageContext.from_defaults",
        ) as mock_storage_context,
        patch("paperless.ai.indexing.load_index_from_storage") as mock_load_index,
    ):
        # Setup mocks
        mock_vector_store = MagicMock()
        mock_storage = MagicMock()
        mock_index = MagicMock()

        mock_faiss.return_value = mock_vector_store
        mock_storage_context.return_value = mock_storage
        mock_load_index.return_value = mock_index
        mock_get_embed_model.return_value = FakeEmbedding()

        # Act
        result = load_index()

        # Assert
        mock_faiss.assert_called_once_with("/fake/path")
        mock_get_embed_model.assert_called_once()
        mock_storage_context.assert_called_once_with(
            vector_store=mock_vector_store,
            persist_dir="/fake/path",
        )
        mock_load_index.assert_called_once_with(mock_storage)
        assert result == mock_index


def test_query_similar_documents(mock_document):
    with (
        patch("paperless.ai.indexing.load_index") as mock_load_index_func,
        patch("paperless.ai.indexing.VectorIndexRetriever") as mock_retriever_cls,
        patch("paperless.ai.indexing.Document.objects.filter") as mock_filter,
    ):
        # Setup mocks
        mock_index = MagicMock()
        mock_load_index_func.return_value = mock_index

        mock_retriever = MagicMock()
        mock_retriever_cls.return_value = mock_retriever

        mock_node1 = MagicMock()
        mock_node1.metadata = {"document_id": 1}

        mock_node2 = MagicMock()
        mock_node2.metadata = {"document_id": 2}

        mock_retriever.retrieve.return_value = [mock_node1, mock_node2]

        mock_filtered_docs = [MagicMock(pk=1), MagicMock(pk=2)]
        mock_filter.return_value = mock_filtered_docs

        result = query_similar_documents(mock_document, top_k=3)

        mock_load_index_func.assert_called_once()
        mock_retriever_cls.assert_called_once_with(index=mock_index, similarity_top_k=3)
        mock_retriever.retrieve.assert_called_once_with(
            "Test Title\nThis is the document content.",
        )
        mock_filter.assert_called_once_with(pk__in=[1, 2])

        assert result == mock_filtered_docs
