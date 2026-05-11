import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from documents.models import Document
from documents.models import PaperlessTask
from documents.tests.factories import PaperlessTaskFactory
from paperless_ai import indexing


@pytest.fixture
def real_document(db) -> Document:
    return Document.objects.create(
        title="Test Document",
        content="This is some test content.",
        added=timezone.now(),
    )


@pytest.fixture
def mock_embed_model(mocker: MockerFixture) -> MagicMock:
    fake = MockEmbedding(embed_dim=384)
    mock = mocker.patch("paperless_ai.indexing.get_embedding_model", return_value=fake)
    mocker.patch("paperless_ai.embedding.get_embedding_model", return_value=fake)
    return mock


@pytest.mark.django_db
def test_build_document_node(real_document: Document) -> None:
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    assert nodes[0].metadata["document_id"] == str(real_document.id)


@pytest.mark.django_db
def test_update_llm_index(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_queryset = MagicMock()
    mock_queryset.exists.return_value = True
    mock_queryset.__iter__.return_value = iter([real_document])
    mocker.patch("documents.models.Document.objects.all", return_value=mock_queryset)

    indexing.update_llm_index(rebuild=True)

    assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_update_llm_index_removes_meta(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    (temp_llm_index_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "old", "dim": 1}),
    )

    mock_queryset = MagicMock()
    mock_queryset.exists.return_value = True
    mock_queryset.__iter__.return_value = iter([real_document])
    mocker.patch("documents.models.Document.objects.all", return_value=mock_queryset)

    indexing.update_llm_index(rebuild=True)

    meta = json.loads((temp_llm_index_dir / "meta.json").read_text())
    from paperless.config import AIConfig

    config = AIConfig()
    expected_model = config.llm_embedding_model or (
        "text-embedding-3-small"
        if config.llm_embedding_backend == "openai-like"
        else "sentence-transformers/all-MiniLM-L6-v2"
    )
    assert meta == {"embedding_model": expected_model, "dim": 384}


@pytest.mark.django_db
def test_update_llm_index_partial_update(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    doc2 = Document.objects.create(
        title="Test Document 2",
        content="This is some test content 2.",
        added=timezone.now(),
        checksum="1234567890abcdef",
    )

    mock_queryset = MagicMock()
    mock_queryset.exists.return_value = True
    mock_queryset.__iter__.return_value = iter([real_document, doc2])
    mocker.patch("documents.models.Document.objects.all", return_value=mock_queryset)
    indexing.update_llm_index(rebuild=True)

    updated_document = real_document
    updated_document.modified = timezone.now()

    doc3 = Document.objects.create(
        title="Test Document 3",
        content="This is some test content 3.",
        added=timezone.now(),
        checksum="abcdef1234567890",
    )

    mock_queryset2 = MagicMock()
    mock_queryset2.exists.return_value = True
    mock_queryset2.__iter__.return_value = iter([updated_document, doc2, doc3])
    mocker.patch("documents.models.Document.objects.all", return_value=mock_queryset2)

    mock_logger = mocker.patch("paperless_ai.indexing.logger")
    indexing.update_llm_index(rebuild=False)
    mock_logger.info.assert_called_once_with("Updating %d nodes in LLM index.", 2)

    indexing.update_llm_index(rebuild=False)

    assert any(temp_llm_index_dir.glob("*.json"))


def test_get_or_create_storage_context_raises_exception(
    temp_llm_index_dir: Path,
    mock_embed_model: MagicMock,
) -> None:
    with pytest.raises(Exception):
        indexing.get_or_create_storage_context(rebuild=False)


@pytest.mark.django_db
def test_load_or_build_index_builds_when_nodes_given(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "llama_index.core.load_index_from_storage",
        side_effect=ValueError("Index not found"),
    )
    mock_index_cls = mocker.patch(
        "llama_index.core.VectorStoreIndex",
        return_value=MagicMock(),
    )
    mock_storage = mocker.patch(
        "paperless_ai.indexing.get_or_create_storage_context",
        return_value=MagicMock(),
    )
    mock_storage.return_value.persist_dir = temp_llm_index_dir

    indexing.load_or_build_index(nodes=[indexing.build_document_node(real_document)])

    mock_index_cls.assert_called_once()


def test_load_or_build_index_raises_exception_when_no_nodes(
    temp_llm_index_dir: Path,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "llama_index.core.load_index_from_storage",
        side_effect=ValueError("Index not found"),
    )
    mocker.patch(
        "paperless_ai.indexing.get_or_create_storage_context",
        return_value=MagicMock(),
    )
    with pytest.raises(Exception):
        indexing.load_or_build_index()


@pytest.mark.django_db
def test_load_or_build_index_succeeds_when_nodes_given(
    temp_llm_index_dir: Path,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "llama_index.core.load_index_from_storage",
        side_effect=ValueError("Index not found"),
    )
    mock_index_cls = mocker.patch(
        "llama_index.core.VectorStoreIndex",
        return_value=MagicMock(),
    )
    mock_storage = mocker.patch(
        "paperless_ai.indexing.get_or_create_storage_context",
        return_value=MagicMock(),
    )
    mock_storage.return_value.persist_dir = temp_llm_index_dir

    indexing.load_or_build_index(nodes=[MagicMock()])

    mock_index_cls.assert_called_once()


@pytest.mark.django_db
def test_add_or_update_document_updates_existing_entry(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
) -> None:
    indexing.update_llm_index(rebuild=True)
    indexing.llm_index_add_or_update_document(real_document)

    assert any(temp_llm_index_dir.glob("*.json"))


@pytest.mark.django_db
def test_remove_document_deletes_node_from_docstore(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: MagicMock,
) -> None:
    indexing.update_llm_index(rebuild=True)
    index = indexing.load_or_build_index()
    assert len(index.docstore.docs) == 1

    indexing.llm_index_remove_document(real_document)
    index = indexing.load_or_build_index()
    assert len(index.docstore.docs) == 0


@pytest.mark.django_db
def test_update_llm_index_no_documents(
    temp_llm_index_dir: Path,
    mock_embed_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_queryset = MagicMock()
    mock_queryset.exists.return_value = False
    mock_queryset.__iter__.return_value = iter([])
    mocker.patch("documents.models.Document.objects.all", return_value=mock_queryset)

    mock_logger = mocker.patch("paperless_ai.indexing.logger")
    indexing.update_llm_index(rebuild=True)
    mock_logger.warning.assert_called_once_with("No documents found to index.")


@pytest.mark.django_db
def test_queue_llm_index_update_if_needed_enqueues_when_idle_or_skips_recent(
    mocker: MockerFixture,
) -> None:
    mock_task = mocker.patch("documents.tasks.llmindex_index")
    result = indexing.queue_llm_index_update_if_needed(
        rebuild=True,
        reason="test enqueue",
    )

    assert result is True
    mock_task.apply_async.assert_called_once_with(
        kwargs={"rebuild": True},
        headers={"trigger_source": "system"},
    )

    PaperlessTaskFactory(
        task_type=PaperlessTask.TaskType.LLM_INDEX,
        trigger_source=PaperlessTask.TriggerSource.SYSTEM,
        status=PaperlessTask.Status.STARTED,
    )

    mock_task2 = mocker.patch("documents.tasks.llmindex_index")
    result = indexing.queue_llm_index_update_if_needed(
        rebuild=False,
        reason="should skip",
    )

    assert result is False
    mock_task2.apply_async.assert_not_called()


@pytest.mark.django_db
def test_query_similar_documents(
    temp_llm_index_dir: Path,
    real_document: Document,
    mocker: MockerFixture,
    settings: SettingsWrapper,
) -> None:
    settings.LLM_EMBEDDING_BACKEND = "huggingface"
    settings.LLM_BACKEND = "ollama"

    mock_storage = mocker.patch("paperless_ai.indexing.get_or_create_storage_context")
    mock_storage.return_value.persist_dir = temp_llm_index_dir
    mocker.patch("paperless_ai.indexing.vector_store_file_exists", return_value=True)

    mock_index = MagicMock()
    mocker.patch("paperless_ai.indexing.load_or_build_index", return_value=mock_index)

    mock_retriever = MagicMock()
    mocker.patch(
        "llama_index.core.retrievers.VectorIndexRetriever",
        return_value=mock_retriever,
    )

    mock_node1 = MagicMock()
    mock_node1.metadata = {"document_id": 1}
    mock_node2 = MagicMock()
    mock_node2.metadata = {"document_id": 2}
    mock_retriever.retrieve.return_value = [mock_node1, mock_node2]

    mock_filtered_docs = [MagicMock(pk=1), MagicMock(pk=2)]
    mock_filter = mocker.patch(
        "paperless_ai.indexing.Document.objects.filter",
        return_value=mock_filtered_docs,
    )

    result = indexing.query_similar_documents(real_document, top_k=3)

    mock_retriever.retrieve.assert_called_once_with(
        "Test Document\nThis is some test content.",
    )
    mock_filter.assert_called_once_with(pk__in=[1, 2])
    assert result == mock_filtered_docs


@pytest.mark.django_db
def test_query_similar_documents_triggers_update_when_index_missing(
    temp_llm_index_dir: Path,
    real_document: Document,
    mocker: MockerFixture,
) -> None:
    mocker.patch("paperless_ai.indexing.vector_store_file_exists", return_value=False)
    mock_queue = mocker.patch("paperless_ai.indexing.queue_llm_index_update_if_needed")
    mock_load = mocker.patch("paperless_ai.indexing.load_or_build_index")

    result = indexing.query_similar_documents(real_document, top_k=2)

    mock_queue.assert_called_once_with(
        rebuild=False,
        reason="LLM index not found for similarity query.",
    )
    mock_load.assert_not_called()
    assert result == []
