from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.utils import timezone
from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from paperless.ai import indexing


@pytest.fixture
def temp_llm_index_dir(tmp_path):
    original_dir = indexing.settings.LLM_INDEX_DIR
    indexing.settings.LLM_INDEX_DIR = tmp_path
    yield tmp_path
    indexing.settings.LLM_INDEX_DIR = original_dir


@pytest.fixture
def real_document(db):
    return Document.objects.create(
        title="Test Document",
        content="This is some test content.",
        added=timezone.now(),
    )


@pytest.fixture
def mock_embed_model():
    """Mocks the embedding model."""
    with patch("paperless.ai.indexing.get_embedding_model") as mock:
        mock.return_value = FakeEmbedding()
        yield mock


class FakeEmbedding(BaseEmbedding):
    # TODO: maybe a better way to do this?
    def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def get_query_embedding_dim(self) -> int:
        return 384  # Match your real FAISS config


@pytest.mark.django_db
def test_build_document_node(real_document):
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    assert nodes[0].metadata["document_id"] == str(real_document.id)


@pytest.mark.django_db
def test_rebuild_llm_index(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
):
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

        assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_add_or_update_document_updates_existing_entry(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
):
    indexing.update_llm_index(rebuild=True)
    indexing.llm_index_add_or_update_document(real_document)

    assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_remove_document_deletes_node_from_docstore(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
):
    indexing.update_llm_index(rebuild=True)
    indexing.llm_index_add_or_update_document(real_document)
    indexing.llm_index_remove_document(real_document)

    assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_rebuild_llm_index_no_documents(
    temp_llm_index_dir,
    mock_embed_model,
):
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_queryset.__iter__.return_value = iter([])
        mock_all.return_value = mock_queryset

        # check log message
        with patch("paperless.ai.indexing.logger") as mock_logger:
            indexing.update_llm_index(rebuild=True)
            mock_logger.warning.assert_called_once_with(
                "No documents found to index.",
            )


def test_query_similar_documents(
    temp_llm_index_dir,
    real_document,
):
    with (
        patch("paperless.ai.indexing.load_or_build_index") as mock_load_or_build_index,
        patch("paperless.ai.indexing.VectorIndexRetriever") as mock_retriever_cls,
        patch("paperless.ai.indexing.Document.objects.filter") as mock_filter,
    ):
        mock_index = MagicMock()
        mock_load_or_build_index.return_value = mock_index

        mock_retriever = MagicMock()
        mock_retriever_cls.return_value = mock_retriever

        mock_node1 = MagicMock()
        mock_node1.metadata = {"document_id": 1}

        mock_node2 = MagicMock()
        mock_node2.metadata = {"document_id": 2}

        mock_retriever.retrieve.return_value = [mock_node1, mock_node2]

        mock_filtered_docs = [MagicMock(pk=1), MagicMock(pk=2)]
        mock_filter.return_value = mock_filtered_docs

        result = indexing.query_similar_documents(real_document, top_k=3)

        mock_load_or_build_index.assert_called_once()
        mock_retriever_cls.assert_called_once_with(index=mock_index, similarity_top_k=3)
        mock_retriever.retrieve.assert_called_once_with(
            "Test Document\nThis is some test content.",
        )
        mock_filter.assert_called_once_with(pk__in=[1, 2])

        assert result == mock_filtered_docs
