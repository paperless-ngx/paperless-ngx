import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_mock
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from faker import Faker
from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from documents.models import PaperlessTask
from documents.signals import document_consumption_finished
from documents.signals import document_updated
from documents.tests.factories import DocumentFactory
from documents.tests.factories import PaperlessTaskFactory
from paperless.models import ApplicationConfiguration
from paperless_ai import indexing


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
def test_build_document_node_excludes_metadata_from_embedding(real_document) -> None:
    """Metadata keys must not be prepended to the embedding text.

    build_llm_index_text already encodes all metadata in the body text, so
    including it again via llama_index's default MetadataMode.EMBED would
    double the token count and exceed embedding models with small context
    windows (e.g. nomic-embed-text via Ollama defaults to num_ctx=2048).
    """
    from llama_index.core.schema import MetadataMode

    nodes = indexing.build_document_node(real_document)
    for node in nodes:
        embed_text = node.get_content(metadata_mode=MetadataMode.EMBED)
        for key in node.metadata:
            assert key not in embed_text, (
                f"Metadata key '{key}' should not appear in embedding text"
            )


@pytest.mark.django_db
def test_build_document_node_uses_rag_chunk_settings(real_document) -> None:
    app_config, _ = ApplicationConfiguration.objects.get_or_create()
    app_config.llm_embedding_chunk_size = 512
    app_config.save()

    with patch("llama_index.core.node_parser.SimpleNodeParser") as mock_parser:
        mock_parser.return_value.get_nodes_from_documents.return_value = []

        indexing.build_document_node(real_document)

        mock_parser.assert_called_once_with(chunk_size=512, chunk_overlap=200)


def test_get_rag_chunk_overlap_clamps_to_chunk_size() -> None:
    with patch("paperless_ai.indexing.RAG_CHUNK_OVERLAP", 128):
        assert indexing.get_rag_chunk_overlap(64) == 63


@pytest.mark.django_db
def test_get_rag_prompt_helper_uses_context_setting() -> None:
    app_config, _ = ApplicationConfiguration.objects.get_or_create()
    app_config.llm_context_size = 4096
    app_config.save()

    prompt_helper = indexing.get_rag_prompt_helper()

    assert prompt_helper.context_window == 4096


@pytest.mark.django_db
def test_update_llm_index(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    mock_config = MagicMock()
    mock_config.llm_embedding_chunk_size = 512
    with (
        patch("documents.models.Document.objects.all") as mock_all,
        patch("paperless_ai.indexing.AIConfig", return_value=mock_config) as ai_config,
        patch("paperless_ai.indexing.build_document_node") as build_document_node,
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        build_document_node.return_value = []
        indexing.update_llm_index(rebuild=True)

        ai_config.assert_called_once()
        build_document_node.assert_called_once_with(real_document, chunk_size=512)
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
        if config.llm_embedding_backend == "openai-like"
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
            "llama_index.core.load_index_from_storage",
            side_effect=ValueError("Index not found"),
        ),
        patch(
            "llama_index.core.VectorStoreIndex",
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
            "llama_index.core.load_index_from_storage",
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
            "llama_index.core.load_index_from_storage",
            side_effect=ValueError("Index not found"),
        ),
        patch(
            "llama_index.core.VectorStoreIndex",
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
def test_query_after_remove_does_not_raise_key_error(
    temp_llm_index_dir,
    real_document,
    mock_embed_model,
) -> None:
    indexing.update_llm_index(rebuild=True)

    query_doc = Document.objects.create(
        title="Query",
        content="query content",
        added=timezone.now(),
    )

    indexing.llm_index_remove_document(real_document)

    result = indexing.query_similar_documents(query_doc, top_k=5)
    assert isinstance(result, list)


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
    mock_task.apply_async.assert_called_once_with(
        kwargs={"rebuild": True},
        headers={"trigger_source": "system"},
    )

    PaperlessTaskFactory(
        task_type=PaperlessTask.TaskType.LLM_INDEX,
        trigger_source=PaperlessTask.TriggerSource.SYSTEM,
        status=PaperlessTask.Status.STARTED,
    )

    # Existing running task
    with patch("documents.tasks.llmindex_index") as mock_task:
        result = indexing.queue_llm_index_update_if_needed(
            rebuild=False,
            reason="should skip",
        )

    assert result is False
    mock_task.apply_async.assert_not_called()


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
        patch("llama_index.core.retrievers.VectorIndexRetriever") as mock_retriever_cls,
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


@pytest.mark.django_db
def test_query_similar_documents_normalizes_and_post_filters_allowed_ids(
    real_document,
) -> None:
    real_document.owner = User.objects.create_user(username="rag-owner")
    real_document.save()
    private_owner = User.objects.create_user(username="rag-private-owner")
    private_document = Document.objects.create(
        title="Private similar document",
        content="Similar private content that must not reach RAG.",
        owner=private_owner,
        added=timezone.now(),
    )

    with (
        patch(
            "paperless_ai.indexing.vector_store_file_exists",
            return_value=True,
        ),
        patch("paperless_ai.indexing.load_or_build_index") as mock_load_or_build_index,
        patch("llama_index.core.retrievers.VectorIndexRetriever") as mock_retriever_cls,
    ):
        allowed_node = MagicMock()
        allowed_node.node_id = "allowed-node"
        allowed_node.metadata = {"document_id": str(real_document.pk)}
        private_node = MagicMock()
        private_node.node_id = "private-node"
        private_node.metadata = {"document_id": str(private_document.pk)}

        mock_index = MagicMock()
        mock_index.docstore.docs.values.return_value = [allowed_node, private_node]
        mock_load_or_build_index.return_value = mock_index

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [private_node, allowed_node]
        mock_retriever_cls.return_value = mock_retriever

        result = indexing.query_similar_documents(
            real_document,
            top_k=2,
            document_ids=[real_document.pk],
        )

    mock_retriever_cls.assert_called_once_with(
        index=mock_index,
        similarity_top_k=2,
        doc_ids=["allowed-node"],
    )
    assert result == [real_document]
    assert private_document not in result


class TestUpdateLlmIndexStaleNodes:
    """Tests that update_llm_index removes ALL nodes for a multi-chunk document."""

    @pytest.mark.django_db
    def test_incremental_update_removes_all_old_nodes_for_multi_chunk_document(
        self,
        temp_llm_index_dir,
        mock_embed_model: MagicMock,
    ) -> None:
        """Ghost nodes from all chunks of a modified document must be removed.

        When a document is split into multiple chunks (chunk_size=1024), the
        incremental update path must delete every old node, not just the last
        one captured by a dict comprehension keyed on document_id.
        """
        # Content long enough to produce at least two chunks at chunk_size=1024.
        # Generate many paragraphs so the token count comfortably exceeds 1024.
        fake = Faker()
        long_content = "\n\n".join(fake.paragraph(nb_sentences=20) for _ in range(20))
        doc = DocumentFactory(content=long_content)

        # Build the initial index (rebuild=True) so it has multiple nodes
        indexing.update_llm_index(rebuild=True)

        # Verify the initial index has more than one node for this document
        initial_index = indexing.load_or_build_index()
        initial_node_ids = [
            nid
            for nid, node in initial_index.docstore.docs.items()
            if node.metadata.get("document_id") == str(doc.id)
        ]
        assert len(initial_node_ids) > 1, (
            f"Expected multiple chunks but got {len(initial_node_ids)}; "
            "increase long_content length"
        )

        # Simulate a modification so the incremental path treats it as changed.
        # Use queryset.update() to bypass auto_now and actually change the DB value.
        new_modified = timezone.now()
        Document.objects.filter(pk=doc.pk).update(modified=new_modified)

        # Run incremental update (rebuild=False) with the modified document
        indexing.update_llm_index(rebuild=False)

        # Reload the persisted index and check that no OLD node ids remain
        updated_index = indexing.load_or_build_index()
        remaining_old_node_ids = [
            nid for nid in initial_node_ids if nid in updated_index.docstore.docs
        ]
        assert remaining_old_node_ids == [], (
            f"Ghost nodes still present after incremental update: "
            f"{remaining_old_node_ids}"
        )


@pytest.mark.django_db
def test_query_similar_documents_empty_allow_list_fails_closed(
    real_document,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.vector_store_file_exists",
            return_value=True,
        ) as mock_vector_store_exists,
        patch("paperless_ai.indexing.load_or_build_index") as mock_load_or_build_index,
        patch("llama_index.core.retrievers.VectorIndexRetriever") as mock_retriever_cls,
    ):
        result = indexing.query_similar_documents(
            real_document,
            document_ids=[],
        )

    assert result == []
    mock_vector_store_exists.assert_not_called()
    mock_load_or_build_index.assert_not_called()
    mock_retriever_cls.assert_not_called()


class TestUpdateLlmIndexEmptyDocumentSet:
    """update_llm_index must persist an empty index when all documents are deleted.

    Without this, the stale on-disk FAISS vectors are never cleared and
    subsequent similarity searches return phantom hits for document IDs that
    no longer exist in the DB.
    """

    @pytest.mark.django_db
    def test_rebuild_clears_stale_index_when_no_documents_exist(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: MagicMock,
    ) -> None:
        """After deleting all documents, rebuild=True must persist an empty index.

        Steps:
        1. Build an index with one document so the on-disk state is non-empty.
        2. Delete all documents from the DB.
        3. Call update_llm_index(rebuild=True).
        4. Reload the index from disk.
        5. Assert the reloaded index has zero nodes (no phantom vectors).
        """
        # Step 1: create a document and build a non-empty index
        Document.objects.create(
            title="Soon-to-be-deleted document",
            content="Some content that will become a phantom vector.",
            added=timezone.now(),
        )
        indexing.update_llm_index(rebuild=True)

        initial_index = indexing.load_or_build_index()
        assert len(initial_index.docstore.docs) > 0, (
            "Precondition failed: expected at least one node before deletion"
        )

        # Step 2: delete all documents
        Document.objects.all().delete()
        assert not Document.objects.exists()

        # Step 3: rebuild with no documents
        indexing.update_llm_index(rebuild=True)

        # Step 4: reload the persisted index from disk
        reloaded_index = indexing.load_or_build_index()

        # Step 5: phantom vectors must be gone
        assert len(reloaded_index.docstore.docs) == 0, (
            f"Expected 0 nodes after clearing all documents, "
            f"but found {len(reloaded_index.docstore.docs)}: "
            f"{list(reloaded_index.docstore.docs.keys())}"
        )


class TestDocumentUpdatedSignalTriggersLlmReindex:
    """document_updated must enqueue an LLM index update, just like document_consumption_finished."""

    @pytest.mark.django_db
    @override_settings(AI_ENABLED=True, LLM_EMBEDDING_BACKEND="huggingface")
    def test_document_updated_enqueues_llm_reindex(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Firing document_updated should call update_document_in_llm_index.apply_async."""
        mock_task = mocker.patch("documents.tasks.update_document_in_llm_index")

        doc = DocumentFactory()
        document_updated.send(sender=object, document=doc)

        mock_task.apply_async.assert_called_once_with(kwargs={"document": doc})

    @pytest.mark.django_db
    @override_settings(AI_ENABLED=True, LLM_EMBEDDING_BACKEND="huggingface")
    def test_version_addition_consumption_enqueues_llm_index_once(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """When a new version is consumed, the root document must be enqueued exactly once."""
        mock_task = mocker.patch("documents.tasks.update_document_in_llm_index")

        root_doc = DocumentFactory()
        document_consumption_finished.send(
            sender=object,
            document=root_doc,
            logging_group=None,
            classifier=None,
            original_file=None,
        )
        document_updated.send(sender=object, document=root_doc, skip_ai_index=True)

        assert mock_task.apply_async.call_count == 1


@pytest.mark.django_db
class TestLlmIndexAddOrUpdateDocumentEmptyContent:
    """llm_index_add_or_update_document must handle empty node lists gracefully."""

    def test_returns_without_error_when_build_document_node_returns_empty(
        self,
        temp_llm_index_dir: Path,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """When build_document_node returns [], the function must return without error
        and must not call load_or_build_index at all."""
        mocker.patch(
            "paperless_ai.indexing.build_document_node",
            return_value=[],
        )
        mock_load = mocker.patch("paperless_ai.indexing.load_or_build_index")

        doc = MagicMock(spec=Document)
        # Must not raise
        indexing.llm_index_add_or_update_document(doc)

        mock_load.assert_not_called()


@pytest.mark.django_db
class TestLlmIndexLocking:
    """The FAISS index mutation functions must acquire the index lock before touching the index.

    Without locking, two concurrent Celery workers can each load the same
    on-disk index, make independent modifications, and the last writer silently
    overwrites the first's changes.
    """

    def test_add_or_update_document_acquires_lock(
        self,
        temp_llm_index_dir: Path,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """llm_index_add_or_update_document must enter the file lock before touching the index."""
        call_order: list[str] = []

        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(
            side_effect=lambda *_: call_order.append("lock_acquired"),
        )
        mock_lock_instance.__exit__ = MagicMock(return_value=False)

        mock_file_lock_cls = mocker.patch(
            "paperless_ai.indexing.FileLock",
            return_value=mock_lock_instance,
        )

        mock_load = mocker.patch(
            "paperless_ai.indexing.load_or_build_index",
            side_effect=lambda *_a, **_kw: (
                call_order.append("index_loaded") or MagicMock()
            ),
        )
        mocker.patch(
            "paperless_ai.indexing.build_document_node",
            return_value=[MagicMock()],
        )
        mocker.patch("paperless_ai.indexing.remove_document_docstore_nodes")

        doc = MagicMock(spec=Document)
        indexing.llm_index_add_or_update_document(doc)

        mock_file_lock_cls.assert_called_once()
        mock_lock_instance.__enter__.assert_called_once()
        mock_load.assert_called_once()
        assert call_order.index("lock_acquired") < call_order.index("index_loaded"), (
            "Lock must be acquired before the index is loaded"
        )

    def test_remove_document_acquires_lock(
        self,
        temp_llm_index_dir: Path,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """llm_index_remove_document must enter the file lock before loading the index."""
        call_order: list[str] = []

        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(
            side_effect=lambda *_: call_order.append("lock_acquired"),
        )
        mock_lock_instance.__exit__ = MagicMock(return_value=False)

        mock_file_lock_cls = mocker.patch(
            "paperless_ai.indexing.FileLock",
            return_value=mock_lock_instance,
        )

        mock_load = mocker.patch(
            "paperless_ai.indexing.load_or_build_index",
            side_effect=lambda *_a, **_kw: (
                call_order.append("index_loaded") or MagicMock()
            ),
        )
        mocker.patch("paperless_ai.indexing.remove_document_docstore_nodes")

        doc = MagicMock(spec=Document)
        indexing.llm_index_remove_document(doc)

        mock_file_lock_cls.assert_called_once()
        mock_lock_instance.__enter__.assert_called_once()
        mock_load.assert_called_once()
        assert call_order.index("lock_acquired") < call_order.index("index_loaded"), (
            "Lock must be acquired before the index is loaded"
        )

    def test_update_llm_index_rebuild_acquires_lock(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: MagicMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """update_llm_index must enter the file lock during the rebuild/persist cycle."""
        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(return_value=None)
        mock_lock_instance.__exit__ = MagicMock(return_value=False)

        mock_file_lock_cls = mocker.patch(
            "paperless_ai.indexing.FileLock",
            return_value=mock_lock_instance,
        )

        # exists=True so the code reaches the lock; iterate over an empty
        # queryset so VectorStoreIndex is called with no nodes (still exercises
        # the lock path without needing heavy FAISS fixture data)
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mocker.patch("paperless_ai.indexing.Document.objects.all", return_value=mock_qs)
        mocker.patch(
            "paperless_ai.indexing.get_or_create_storage_context",
            return_value=MagicMock(),
        )

        indexing.update_llm_index(rebuild=True)

        mock_file_lock_cls.assert_called_once()
        mock_lock_instance.__enter__.assert_called_once()

    def test_query_similar_documents_acquires_lock(
        self,
        temp_llm_index_dir: Path,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """query_similar_documents must enter the file lock before loading the index."""
        call_order: list[str] = []

        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(
            side_effect=lambda *_: call_order.append("lock_acquired"),
        )
        mock_lock_instance.__exit__ = MagicMock(return_value=False)

        mock_file_lock_cls = mocker.patch(
            "paperless_ai.indexing.FileLock",
            return_value=mock_lock_instance,
        )

        mocker.patch(
            "paperless_ai.indexing.vector_store_file_exists",
            return_value=True,
        )

        mock_index = MagicMock()
        mock_index.docstore.docs = {}

        mocker.patch(
            "paperless_ai.indexing.load_or_build_index",
            side_effect=lambda *_a, **_kw: (
                call_order.append("index_loaded") or mock_index
            ),
        )

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        mocker.patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=mock_retriever,
        )

        mocker.patch("paperless_ai.indexing.truncate_content", return_value="")

        indexing.query_similar_documents(MagicMock(spec=Document))

        mock_file_lock_cls.assert_called()
        mock_lock_instance.__enter__.assert_called()
        assert call_order.index("lock_acquired") < call_order.index("index_loaded"), (
            "Lock must be acquired before the index is loaded"
        )
