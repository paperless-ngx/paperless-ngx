import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from celery import states
from django.test import override_settings
from django.utils import timezone
from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from documents.models import PaperlessTask
from paperless_ai import indexing


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
    fake = FakeEmbedding()
    with (
        patch("paperless_ai.indexing.get_embedding_model") as mock_index,
        patch(
            "paperless_ai.embedding.get_embedding_model",
        ) as mock_embedding,
    ):
        mock_index.return_value = fake
        mock_embedding.return_value = fake
        yield mock_index


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
def test_build_document_node(real_document) -> None:
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    assert nodes[0].metadata["document_id"] == str(real_document.id)


@pytest.mark.django_db
def test_update_llm_index(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

        assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_update_llm_index_removes_meta(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    # Pre-create a meta.json with incorrect data
    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "old", "dim": 1}),
    )

    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

    meta = json.loads((temp_llm_index_dir / "meta.json").read_text())
    from paperless.config import AIConfig

    config = AIConfig()
    expected_model = config.llm_embedding_model or (
        "text-embedding-3-small"
        if config.llm_embedding_backend == "openai"
        else "sentence-transformers/all-MiniLM-L6-v2"
    )
    assert meta == {"embedding_model": expected_model, "dim": 384}


@pytest.mark.django_db
def test_update_llm_index_partial_update(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    doc2 = Document.objects.create(
        title="Test Document 2",
        content="This is some test content 2.",
        added=timezone.now(),
        checksum="1234567890abcdef",
    )
    # Initial index
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document, doc2])
        mock_all.return_value = mock_queryset

        indexing.update_llm_index(rebuild=True)

    # modify document
    updated_document = real_document
    updated_document.modified = timezone.now()  # simulate modification

    # new doc
    doc3 = Document.objects.create(
        title="Test Document 3",
        content="This is some test content 3.",
        added=timezone.now(),
        checksum="abcdef1234567890",
    )

    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([updated_document, doc2, doc3])
        mock_all.return_value = mock_queryset

        # assert logs "Updating LLM index with %d new nodes and removing %d old nodes."
        with patch("paperless_ai.indexing.logger") as mock_logger:
            indexing.update_llm_index(rebuild=False)
            mock_logger.info.assert_called_once_with(
                "Updating %d nodes in LLM index.",
                2,
            )
        indexing.update_llm_index(rebuild=False)

    assert any(temp_llm_index_dir.glob("*.json"))


def test_get_or_create_storage_context_raises_exception(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    with pytest.raises(Exception):
        indexing.get_or_create_storage_context(rebuild=False)


@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
)
def test_load_or_build_index_builds_when_nodes_given(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.load_index_from_storage",
            side_effect=ValueError("Index not found"),
        ),
        patch(
            "paperless_ai.indexing.VectorStoreIndex",
            return_value=MagicMock(),
        ) as mock_index_cls,
        patch(
            "paperless_ai.indexing.get_or_create_storage_context",
            return_value=MagicMock(),
        ) as mock_storage,
    ):
        mock_storage.return_value.persist_dir = temp_llm_index_dir
        indexing.load_or_build_index(
            nodes=[indexing.build_document_node(real_document)],
        )
        mock_index_cls.assert_called_once()


def test_load_or_build_index_raises_exception_when_no_nodes(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.load_index_from_storage",
            side_effect=ValueError("Index not found"),
        ),
        patch(
            "paperless_ai.indexing.get_or_create_storage_context",
            return_value=MagicMock(),
        ),
    ):
        with pytest.raises(Exception):
            indexing.load_or_build_index()


@pytest.mark.django_db
def test_load_or_build_index_succeeds_when_nodes_given(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.load_index_from_storage",
            side_effect=ValueError("Index not found"),
        ),
        patch(
            "paperless_ai.indexing.VectorStoreIndex",
            return_value=MagicMock(),
        ) as mock_index_cls,
        patch(
            "paperless_ai.indexing.get_or_create_storage_context",
            return_value=MagicMock(),
        ) as mock_storage,
    ):
        mock_storage.return_value.persist_dir = temp_llm_index_dir
        indexing.load_or_build_index(
            nodes=[MagicMock()],
        )
        mock_index_cls.assert_called_once()


@pytest.mark.django_db
def test_add_or_update_document_updates_existing_entry(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    indexing.update_llm_index(rebuild=True)
    indexing.llm_index_add_or_update_document(real_document)

    assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_remove_document_deletes_node_from_docstore(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    indexing.update_llm_index(rebuild=True)
    index = indexing.load_or_build_index()
    assert len(index.docstore.docs) == 1

    indexing.llm_index_remove_document(real_document)
    index = indexing.load_or_build_index()
    assert len(index.docstore.docs) == 0


@pytest.mark.django_db
def test_update_llm_index_no_documents(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_queryset.__iter__.return_value = iter([])
        mock_all.return_value = mock_queryset

        # check log message
        with patch("paperless_ai.indexing.logger") as mock_logger:
            indexing.update_llm_index(rebuild=True)
            mock_logger.warning.assert_called_once_with(
                "No documents found to index.",
            )


@pytest.mark.django_db
def test_queue_llm_index_update_if_needed_enqueues_when_idle_or_skips_recent() -> None:
    # No existing tasks
    with patch("documents.tasks.llmindex_index") as mock_task:
        result = indexing.queue_llm_index_update_if_needed(
            rebuild=True,
            reason="test enqueue",
        )

    assert result is True
    mock_task.delay.assert_called_once_with(rebuild=True, scheduled=False, auto=True)

    PaperlessTask.objects.create(
        task_id="task-1",
        task_name=PaperlessTask.TaskName.LLMINDEX_UPDATE,
        status=states.STARTED,
        date_created=timezone.now(),
    )

    # Existing running task
    with patch("documents.tasks.llmindex_index") as mock_task:
        result = indexing.queue_llm_index_update_if_needed(
            rebuild=False,
            reason="should skip",
        )

    assert result is False
    mock_task.delay.assert_not_called()


@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_BACKEND="ollama",
)
def test_query_similar_documents(
    temp_llm_index_dir,
    real_document,
) -> None:
    with (
        patch("paperless_ai.indexing.get_or_create_storage_context") as mock_storage,
        patch("paperless_ai.indexing.load_or_build_index") as mock_load_or_build_index,
        patch(
            "paperless_ai.indexing.vector_store_file_exists",
        ) as mock_vector_store_exists,
        patch("paperless_ai.indexing.VectorIndexRetriever") as mock_retriever_cls,
        patch("paperless_ai.indexing.Document.objects.filter") as mock_filter,
    ):
        mock_storage.return_value = MagicMock()
        mock_storage.return_value.persist_dir = temp_llm_index_dir
        mock_vector_store_exists.return_value = True

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
        mock_retriever_cls.assert_called_once()
        mock_retriever.retrieve.assert_called_once_with(
            "Test Document\nThis is some test content.",
        )
        mock_filter.assert_called_once_with(pk__in=[1, 2])

        assert result == mock_filtered_docs


@pytest.mark.django_db
def test_query_similar_documents_triggers_update_when_index_missing(
    temp_llm_index_dir,
    real_document,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.vector_store_file_exists",
            return_value=False,
        ),
        patch(
            "paperless_ai.indexing.queue_llm_index_update_if_needed",
        ) as mock_queue,
        patch("paperless_ai.indexing.load_or_build_index") as mock_load,
    ):
        result = indexing.query_similar_documents(
            real_document,
            top_k=2,
        )

    mock_queue.assert_called_once_with(
        rebuild=False,
        reason="LLM index not found for similarity query.",
    )
    mock_load.assert_not_called()
    assert result == []
