import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_mock
from django.test import override_settings
from django.utils import timezone

from documents.models import Document
from documents.models import PaperlessTask
from documents.signals import document_consumption_finished
from documents.signals import document_updated
from documents.tests.factories import DocumentFactory
from documents.tests.factories import PaperlessTaskFactory
from paperless.models import ApplicationConfiguration
from paperless_ai import indexing
from paperless_ai.tests.conftest import FakeEmbedding


@pytest.fixture
def real_document(db: None) -> Document:
    return Document.objects.create(
        title="Test Document",
        content="This is some test content.",
        added=timezone.now(),
    )


@pytest.mark.django_db
def test_build_document_node(real_document: Document) -> None:
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    assert nodes[0].metadata["document_id"] == str(real_document.id)


@pytest.mark.django_db
def test_build_document_node_sets_ref_doc_id(real_document: Document) -> None:
    """Every node produced by build_document_node must carry the paperless document id
    as its ref_doc_id so that the LanceDB adapter's delete(str(doc.id)) works correctly."""
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0, "Expected at least one node"
    for node in nodes:
        assert node.ref_doc_id == str(real_document.id), (
            f"Expected ref_doc_id={real_document.id!r}, got {node.ref_doc_id!r}"
        )


@pytest.mark.django_db
def test_build_document_node_excludes_metadata_from_embedding(
    real_document: Document,
) -> None:
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
def test_build_document_node_structured_fields_in_metadata(
    real_document: Document,
) -> None:
    """Structured fields must be in node.metadata so the LLM receives them via metadata prepend."""
    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    for node in nodes:
        assert "title" in node.metadata
        assert "tags" in node.metadata
        assert "correspondent" in node.metadata
        assert "document_type" in node.metadata
        assert "created" in node.metadata
        assert "added" in node.metadata
        assert "modified" in node.metadata


@pytest.mark.django_db
def test_build_document_node_excludes_document_id_from_llm_context(
    real_document: Document,
) -> None:
    """document_id is an internal key and must not appear in LLM context text."""
    from llama_index.core.schema import MetadataMode

    nodes = indexing.build_document_node(real_document)
    assert len(nodes) > 0
    for node in nodes:
        assert "document_id" in node.excluded_llm_metadata_keys
        assert "document_id" not in node.get_content(metadata_mode=MetadataMode.LLM)


@pytest.mark.django_db
def test_build_document_node_uses_rag_chunk_settings(real_document: Document) -> None:
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
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
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


@pytest.mark.django_db
def test_update_llm_index_cleans_stale_meta_on_rebuild(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
) -> None:
    # A meta.json left over from the FAISS era (or written by older code) must be
    # deleted on rebuild so stale artifacts don't accumulate on disk.
    stale_meta = temp_llm_index_dir / "meta.json"
    stale_meta.write_text(json.dumps({"embedding_model": "old", "dim": 1}))

    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

    assert not stale_meta.exists(), (
        "update_llm_index(rebuild=True) must remove stale meta.json"
    )


@pytest.mark.django_db
def test_update_llm_index_rebuilds_on_model_name_change(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
) -> None:
    # Build initial index with model "model-a".
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        with patch(
            "paperless_ai.indexing.get_configured_model_name",
            return_value="model-a",
        ):
            indexing.update_llm_index(rebuild=True)

    # Simulate config change to "model-b"; the incremental run must force a rebuild.
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        with patch(
            "paperless_ai.indexing.get_configured_model_name",
            return_value="model-b",
        ):
            indexing.update_llm_index(rebuild=False)

    store = indexing.get_vector_store()
    # Schema metadata only updates when the table is dropped and recreated, never on
    # incremental writes -- so "model-b" here proves a full rebuild happened.
    assert store.stored_model_name() == "model-b"


@pytest.mark.django_db
def test_update_llm_index_partial_update(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
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

        indexing.update_llm_index(rebuild=False)

    store = indexing.get_vector_store()
    assert store.table_exists(), (
        "Expected the LanceDB table to exist after incremental update"
    )


@pytest.mark.django_db
def test_add_or_update_document_updates_existing_entry(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
) -> None:
    indexing.update_llm_index(rebuild=True)
    indexing.llm_index_add_or_update_document(real_document)

    store = indexing.get_vector_store()
    assert store.table_exists(), (
        "Expected the LanceDB table to exist after add-or-update"
    )


@pytest.mark.django_db
def test_query_after_remove_does_not_raise_key_error(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
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
    temp_llm_index_dir: Path,
    mock_embed_model: FakeEmbedding,
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
def test_update_no_documents_no_index_returns_early(
    temp_llm_index_dir: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """update with no documents and no existing index must return early."""
    mock_qs = MagicMock()
    mock_qs.exists.return_value = False
    mock_qs.__iter__ = MagicMock(return_value=iter([]))
    mocker.patch("paperless_ai.indexing.Document.objects.all", return_value=mock_qs)

    result = indexing.update_llm_index(rebuild=False)

    assert result == "No documents found to index."


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
    temp_llm_index_dir: Path,
    real_document: Document,
) -> None:
    with (
        patch("paperless_ai.indexing.load_or_build_index") as mock_load_or_build_index,
        patch(
            "paperless_ai.indexing.llm_index_exists",
        ) as mock_vector_store_exists,
        patch("llama_index.core.retrievers.VectorIndexRetriever") as mock_retriever_cls,
        patch("paperless_ai.indexing.Document.objects.filter") as mock_filter,
    ):
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
    temp_llm_index_dir: Path,
    real_document: Document,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.llm_index_exists",
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
def test_query_similar_documents_empty_allow_list_fails_closed(
    real_document: Document,
) -> None:
    with (
        patch(
            "paperless_ai.indexing.llm_index_exists",
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
    """update_llm_index must clear the LanceDB table when all documents are deleted.

    Without this, the stale vectors are never cleared and subsequent similarity
    searches return phantom hits for document IDs that no longer exist in the DB.
    """

    @pytest.mark.django_db
    def test_rebuild_clears_stale_index_when_no_documents_exist(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
    ) -> None:
        """After deleting all documents, rebuild=True must produce a table with zero rows.

        Steps:
        1. Build an index with one document so the on-disk state is non-empty.
        2. Delete all documents from the DB.
        3. Call update_llm_index(rebuild=True).
        4. Open the LanceDB table directly and assert zero rows.
        """
        # Step 1: create a document and build a non-empty index
        Document.objects.create(
            title="Soon-to-be-deleted document",
            content="Some content that will become a phantom vector.",
            added=timezone.now(),
        )
        indexing.update_llm_index(rebuild=True)

        store = indexing.get_vector_store()
        assert store.table_exists(), (
            "Precondition failed: expected the LanceDB table to exist before deletion"
        )

        # Step 2: delete all documents
        Document.objects.all().delete()
        assert not Document.objects.exists()

        # Step 3: rebuild with no documents — drop_table is called so the table
        # is removed (no rows to re-insert, so it stays absent).
        indexing.update_llm_index(rebuild=True)

        # Step 4: the table must be absent (no rows) — phantom vectors gone
        store2 = indexing.get_vector_store()
        assert not store2.table_exists(), (
            "Expected the LanceDB table to be absent after rebuilding with no documents"
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
        mock_embed_model: MagicMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """When build_document_node returns [], the function must return without error.

        The store's upsert_document treats an empty node list as a removal (no-op
        delete), so load_or_build_index must not be called.
        """
        mocker.patch(
            "paperless_ai.indexing.build_document_node",
            return_value=[],
        )
        mock_load = mocker.patch("paperless_ai.indexing.load_or_build_index")

        doc = MagicMock(spec=Document)
        doc.id = 42
        # Must not raise
        indexing.llm_index_add_or_update_document(doc)

        mock_load.assert_not_called()


@pytest.mark.django_db
def test_llm_index_compact_uses_zero_retention(
    temp_llm_index_dir: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """compact must use retention_seconds=0 to clear all MVCC history immediately."""
    mock_store = mocker.MagicMock()
    mocker.patch(
        "paperless_ai.indexing.write_store",
        return_value=mocker.MagicMock(
            __enter__=mocker.MagicMock(return_value=mock_store),
            __exit__=mocker.MagicMock(return_value=False),
        ),
    )

    indexing.llm_index_compact()

    mock_store.compact.assert_called_once_with(retention_seconds=0)


@pytest.mark.django_db
class TestLlmIndexLocking:
    """Index mutation functions must go through write_store(), which holds the lock.

    Without locking, two concurrent Celery workers can open the same store,
    make independent modifications, and trigger CommitConflictError.
    """

    def test_add_or_update_document_uses_write_store(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mock_store = MagicMock()
        mocker.patch(
            "paperless_ai.indexing.write_store",
            return_value=mocker.MagicMock(
                __enter__=mocker.MagicMock(return_value=mock_store),
                __exit__=mocker.MagicMock(return_value=False),
            ),
        )
        mock_node = MagicMock()
        mock_node.get_content.return_value = "fake node text"
        mocker.patch(
            "paperless_ai.indexing.build_document_node",
            return_value=[mock_node],
        )

        doc = MagicMock(spec=Document)
        doc.id = 1
        indexing.llm_index_add_or_update_document(doc)

        mock_store.upsert_document.assert_called_once()

    def test_remove_document_uses_write_store(
        self,
        temp_llm_index_dir: Path,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mock_store = MagicMock()
        mocker.patch(
            "paperless_ai.indexing.write_store",
            return_value=mocker.MagicMock(
                __enter__=mocker.MagicMock(return_value=mock_store),
                __exit__=mocker.MagicMock(return_value=False),
            ),
        )

        doc = MagicMock(spec=Document)
        doc.id = 1
        indexing.llm_index_remove_document(doc)

        mock_store.delete.assert_called_once_with("1")

    def test_update_llm_index_rebuild_uses_write_store(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mock_store = MagicMock()
        mocker.patch(
            "paperless_ai.indexing.write_store",
            return_value=mocker.MagicMock(
                __enter__=mocker.MagicMock(return_value=mock_store),
                __exit__=mocker.MagicMock(return_value=False),
            ),
        )
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mocker.patch("paperless_ai.indexing.Document.objects.all", return_value=mock_qs)

        indexing.update_llm_index(rebuild=True)

        mock_store.drop_table.assert_called_once()


@pytest.mark.django_db
@pytest.mark.django_db
class TestLanceDbIndexing:
    def test_get_vector_store_roundtrip(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
    ) -> None:
        from paperless_ai.vector_store import PaperlessLanceVectorStore

        store = indexing.get_vector_store()
        assert isinstance(store, PaperlessLanceVectorStore)

    def test_add_then_remove_document(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        real_document: Document,
    ) -> None:
        indexing.llm_index_add_or_update_document(real_document)
        store = indexing.get_vector_store()
        table = store.client.open_table(indexing.LLM_INDEX_TABLE)
        assert table.count_rows() >= 1

        indexing.llm_index_remove_document(real_document)
        assert store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows() == 0

    def test_update_shrinks_chunks_without_orphans(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        real_document: Document,
    ) -> None:
        real_document.content = "word " * 4000  # many chunks
        real_document.save()
        indexing.llm_index_add_or_update_document(real_document)
        store = indexing.get_vector_store()
        big = store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows()

        real_document.content = "short"  # one chunk
        real_document.save()
        indexing.llm_index_add_or_update_document(real_document)

        rows = store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows()
        assert rows < big
        assert rows >= 1


@pytest.mark.django_db
class TestQuerySimilarDocuments:
    def test_query_similar_documents_respects_allowed_ids(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
    ) -> None:
        a = DocumentFactory.create(content="alpha shared content here")
        b = DocumentFactory.create(content="beta shared content here")
        c = DocumentFactory.create(content="gamma shared content here")
        for doc in (a, b, c):
            indexing.llm_index_add_or_update_document(doc)

        results = indexing.query_similar_documents(a, document_ids=[b.id])

        assert all(doc.id == b.id for doc in results)
