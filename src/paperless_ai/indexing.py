import logging
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from filelock import FileLock
from filelock import ReadWriteLock
from filelock import Timeout

from documents.models import Document
from documents.models import PaperlessTask
from documents.utils import IterWrapper
from documents.utils import identity
from paperless.config import AIConfig
from paperless_ai.db import db_connection_released
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_configured_model_name
from paperless_ai.embedding import get_embedding_model

if TYPE_CHECKING:
    from llama_index.core.schema import BaseNode

    from paperless_ai.vector_store import PaperlessSqliteVecVectorStore


logger = logging.getLogger("paperless_ai.indexing")

RAG_NUM_OUTPUT = 512
RAG_CHUNK_OVERLAP = 200


def queue_llm_index_update_if_needed(*, rebuild: bool, reason: str) -> bool:
    # NOTE: The check-then-enqueue sequence below is non-atomic (TOCTOU): two
    # concurrent workers can both observe no running task and both enqueue a
    # full rebuild. This is wasteful but not data-corrupting — update_llm_index
    # is itself protected by settings.LLM_INDEX_LOCK, so only one rebuild runs at a
    # time and the second one is serialised after the first completes.
    from documents.tasks import llmindex_index

    has_running = PaperlessTask.objects.filter(
        task_type=PaperlessTask.TaskType.LLM_INDEX,
        status__in=[PaperlessTask.Status.PENDING, PaperlessTask.Status.STARTED],
    ).exists()
    has_recent = PaperlessTask.objects.filter(
        task_type=PaperlessTask.TaskType.LLM_INDEX,
        date_created__gte=(timezone.now() - timedelta(minutes=5)),
    ).exists()
    if has_running or has_recent:
        return False

    llmindex_index.apply_async(
        kwargs={"rebuild": rebuild},
        headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
    )
    logger.warning(
        "Queued LLM index update%s: %s",
        " (rebuild)" if rebuild else "",
        reason,
    )
    return True


def get_vector_store() -> "PaperlessSqliteVecVectorStore":
    from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

    settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return PaperlessSqliteVecVectorStore(
        uri=str(settings.LLM_INDEX_DIR),
    )


# --- LLM index locking ---------------------------------------------------
#
# Two locks guard the index; they answer different questions and are NOT
# interchangeable:
#
# * settings.LLM_INDEX_LOCK (FileLock, exclusive) -- serializes WRITERS against
#   each other, so only one rebuild/upsert/delete/compaction runs at a time.
#   Taken by write_store(). Readers never take it, so it never blocks reads.
#
# * settings.LLM_INDEX_RWLOCK (ReadWriteLock) -- coordinates readers against the
#   compaction/migration file swap. read_store() takes it SHARED (readers run
#   concurrently); _exclude_readers() takes it EXCLUSIVE, only for the swap, so
#   the database file is never replaced while a reader connection is open (that
#   would alias the old WAL onto the new file and corrupt it).
#
#                    | vs another writer | vs a reader
#   -----------------+-------------------+----------------------------
#   normal write     | LLM_INDEX_LOCK    | nothing (WAL gives MVCC)
#   compaction/swap  | LLM_INDEX_LOCK    | LLM_INDEX_RWLOCK (exclusive)
#   reader           | nothing (WAL)     | LLM_INDEX_RWLOCK (shared)
#
# They can't be merged into one ReadWriteLock: a normal write must exclude other
# writers WITHOUT blocking readers (WAL already gives reader/writer concurrency),
# and ReadWriteLock has no "exclusive vs writers, shared vs readers" mode. Only
# the swap needs to exclude readers.
def _index_rwlock() -> ReadWriteLock:
    """Return a fresh read/write lock instance for the index swap.

    ``is_singleton=False`` so reads and the swap always coordinate through
    SQLite (the actual cross-process case) rather than hitting the in-process
    reentrant-upgrade guard; callers must ``close()`` it (the context managers
    below do).
    """
    settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return ReadWriteLock(str(settings.LLM_INDEX_RWLOCK), is_singleton=False)


@contextmanager
def read_store():
    """Acquire the shared read lock and yield the vector store for a read.

    The shared lock is held for the whole lifetime of the connection (and
    closed on exit) so the compaction/migration swap, which takes the exclusive
    lock, never runs while this connection is open. Concurrent readers do not
    block each other; only the swap does.
    """
    lock = _index_rwlock()
    try:
        with lock.read_lock(), get_vector_store() as store:
            yield store
    finally:
        lock.close()


@contextmanager
def _exclude_readers():
    """Acquire exclusive index access, blocking until readers have drained.

    The exclusive counterpart to ``read_store()``: a compaction or migration
    must not run while any reader connection is open. Raises
    :class:`filelock.Timeout` if active readers do not drain within
    ``LLM_INDEX_COMPACTION_LOCK_TIMEOUT``; callers skip the operation on timeout.
    """
    lock = _index_rwlock()
    try:
        with lock.write_lock(timeout=settings.LLM_INDEX_COMPACTION_LOCK_TIMEOUT):
            yield
    finally:
        lock.close()


@contextmanager
def write_store(embed_model_name: str | None = None):
    """Acquire the write lock and yield the vector store.

    All mutating operations (upsert, delete, rebuild, compact) must go through
    this context manager to serialise concurrent Celery writers.
    Read paths use ``read_store()`` so they hold the shared read lock.

    Pass ``embed_model_name`` whenever the operation may create the table so
    the model name is recorded in the schema metadata for future mismatch checks.
    """
    from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

    settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with (
        FileLock(settings.LLM_INDEX_LOCK),
        PaperlessSqliteVecVectorStore(
            uri=str(settings.LLM_INDEX_DIR),
            embed_model_name=embed_model_name,
        ) as store,
    ):
        yield store


def build_document_node(
    document: Document,
    *,
    chunk_size: int | None = None,
) -> list["BaseNode"]:
    """
    Given a Document, returns parsed Nodes ready for indexing.
    """
    text = build_llm_index_text(document)
    metadata = {
        "document_id": str(document.id),
        "title": document.title,
        "tags": [t.name for t in document.tags.all()],
        "correspondent": document.correspondent.name
        if document.correspondent
        else None,
        "document_type": document.document_type.name
        if document.document_type
        else None,
        "filename": document.filename,
        "storage_path": document.storage_path.name if document.storage_path else None,
        "archive_serial_number": document.archive_serial_number,
        "created": document.created.isoformat() if document.created else None,
        "added": document.added.isoformat() if document.added else None,
        "modified": document.modified.isoformat(),
    }
    from llama_index.core import Document as LlamaDocument
    from llama_index.core.node_parser import SimpleNodeParser

    # Exclude all metadata keys from the embedding text — build_llm_index_text
    # already encodes this info in the body, so prepending it again would double
    # the token count and exceed embedding models with small context windows
    # (e.g. nomic-embed-text via Ollama defaults to num_ctx=2048).
    doc = LlamaDocument(
        id_=str(document.id),
        text=text,
        metadata=metadata,
        excluded_embed_metadata_keys=list(metadata.keys()),
        excluded_llm_metadata_keys=["document_id"],
    )
    chunk_size = chunk_size or get_rag_chunk_size()
    parser = SimpleNodeParser(
        chunk_size=chunk_size,
        chunk_overlap=get_rag_chunk_overlap(chunk_size),
    )
    return parser.get_nodes_from_documents([doc])


def load_or_build_index(config: AIConfig, store: "PaperlessSqliteVecVectorStore"):
    """Return a VectorStoreIndex backed by ``store``.

    ``store`` is supplied by the caller's ``read_store()`` context so the shared
    read lock and the connection stay alive for the whole retrieval.
    """
    import llama_index.core.settings as llama_settings
    from llama_index.core import VectorStoreIndex

    embed_model = get_embedding_model(config)
    llama_settings.Settings.embed_model = embed_model
    return VectorStoreIndex.from_vector_store(
        vector_store=store,
        embed_model=embed_model,
    )


def llm_index_exists() -> bool:
    """True when the index table exists on disk."""
    with read_store() as store:
        return store.table_exists()


def get_rag_chunk_size() -> int:
    return AIConfig().llm_embedding_chunk_size


def get_rag_chunk_overlap(chunk_size: int | None = None) -> int:
    chunk_size = chunk_size or get_rag_chunk_size()
    return min(RAG_CHUNK_OVERLAP, chunk_size - 1)


def get_rag_prompt_helper(
    *,
    chunk_size: int | None = None,
    context_size: int | None = None,
):
    from llama_index.core.indices.prompt_helper import PromptHelper

    if chunk_size is None or context_size is None:
        config = AIConfig()
        chunk_size = chunk_size or config.llm_embedding_chunk_size
        context_size = context_size or config.llm_context_size

    return PromptHelper(
        context_window=context_size,
        num_output=RAG_NUM_OUTPUT,
        chunk_overlap_ratio=0.1,
        chunk_size_limit=chunk_size,
    )


def _embed_nodes(nodes: list["BaseNode"], embed_model) -> None:
    """Embed ``nodes`` in place using ``embed_model``."""
    from llama_index.core.schema import MetadataMode

    texts = [n.get_content(metadata_mode=MetadataMode.EMBED) for n in nodes]
    for node, emb in zip(
        nodes,
        embed_model.get_text_embedding_batch(texts),
        strict=True,
    ):
        node.embedding = emb


def _document_id_filters(doc_ids):
    """Return a MetadataFilters IN filter scoped to ``doc_ids``."""
    from llama_index.core.vector_stores.types import FilterOperator
    from llama_index.core.vector_stores.types import MetadataFilter
    from llama_index.core.vector_stores.types import MetadataFilters

    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.IN,
                value=sorted(doc_ids),
            ),
        ],
    )


def update_llm_index(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
    rebuild=False,
) -> str:
    """Rebuild or incrementally update the LLM index."""
    with write_store() as store:
        try:
            with _exclude_readers():
                needs_reembed = store.check_and_run_migrations()
        except Timeout:
            logger.info(
                "Skipping LLM index migration check: index readers are active; "
                "will retry next run.",
            )
            needs_reembed = False
        if needs_reembed:
            logger.warning(
                "LLM index migration requires re-embedding; forcing rebuild.",
            )
            rebuild = True
    documents = Document.objects.all()
    no_documents = not documents.exists()

    # Fast exit before touching config: nothing to index and no existing index.
    if no_documents and not rebuild and not llm_index_exists():
        logger.warning("No documents found to index.")
        return "No documents found to index."

    config = AIConfig()
    model_name = get_configured_model_name(config)

    if not rebuild and llm_index_exists():
        with read_store() as store:
            config_mismatch = store.config_mismatch(model_name)
        if config_mismatch:
            logger.warning("Embedding model changed; forcing LLM index rebuild.")
            rebuild = True

    if no_documents:
        logger.warning("No documents found to index.")

    chunk_size = config.llm_embedding_chunk_size
    embed_model = get_embedding_model(config)

    with write_store(embed_model_name=model_name) as store:
        if rebuild or not store.table_exists():
            logger.info("Rebuilding LLM index.")
            store.drop_table()
            for document in iter_wrapper(documents):
                nodes = build_document_node(document, chunk_size=chunk_size)
                _embed_nodes(nodes, embed_model)
                store.add(nodes)
            msg = "LLM index rebuilt successfully."
        else:
            existing = store.get_modified_times()
            changed = 0
            for document in iter_wrapper(documents):
                doc_id = str(document.id)
                if existing.get(doc_id) == document.modified.isoformat():
                    continue
                nodes = build_document_node(document, chunk_size=chunk_size)
                _embed_nodes(nodes, embed_model)
                store.upsert_document(doc_id, nodes)
                changed += 1
            msg = (
                "LLM index updated successfully."
                if changed
                else "No changes detected in LLM index."
            )

        try:
            with _exclude_readers():
                store.compact()
        except Timeout:
            logger.info(
                "Skipping LLM index compaction: index readers are active; "
                "will retry next run.",
            )
    return msg


def llm_index_add_or_update_document(document: Document):
    """Add or atomically replace a document's chunks in the index."""
    config = AIConfig()
    new_nodes = build_document_node(
        document,
        chunk_size=config.llm_embedding_chunk_size,
    )
    if new_nodes:
        _embed_nodes(new_nodes, get_embedding_model(config))

    with write_store(embed_model_name=get_configured_model_name(config)) as store:
        store.upsert_document(str(document.id), new_nodes)


def llm_index_compact() -> None:
    """Compact the index immediately, rebuilding the table to reclaim space."""
    with write_store() as store:
        try:
            with _exclude_readers():
                store.compact(force=True)
        except Timeout:
            logger.info(
                "Skipping LLM index compaction: index readers are active; "
                "will retry next run.",
            )


def llm_index_remove_document(document: Document):
    """Remove a document's chunks from the LLM index."""
    with write_store() as store:
        store.delete(str(document.id))


def truncate_content(
    content: str,
    *,
    chunk_size: int | None = None,
    context_size: int | None = None,
) -> str:
    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.text_splitter import TokenTextSplitter

    if chunk_size is None or context_size is None:
        config = AIConfig()
        chunk_size = chunk_size or config.llm_embedding_chunk_size
        context_size = context_size or config.llm_context_size
    prompt_helper = get_rag_prompt_helper(
        chunk_size=chunk_size,
        context_size=context_size,
    )
    splitter = TokenTextSplitter(
        separator=" ",
        chunk_size=chunk_size,
        chunk_overlap=get_rag_chunk_overlap(chunk_size),
    )
    content_chunks = splitter.split_text(content)
    truncated_chunks = prompt_helper.truncate(
        prompt=PromptTemplate(template="{content}"),
        text_chunks=content_chunks,
        padding=5,
    )
    return " ".join(truncated_chunks)


def truncate_embedding_query(content: str, *, chunk_size: int) -> str:
    from llama_index.core.text_splitter import TokenTextSplitter

    splitter = TokenTextSplitter(
        separator=" ",
        chunk_size=chunk_size,
        chunk_overlap=0,
    )
    content_chunks = splitter.split_text(content)
    return content_chunks[0] if content_chunks else ""


def normalize_document_ids(document_ids: Iterable[int | str] | None) -> set[str] | None:
    if document_ids is None:
        return None
    return {str(document_id) for document_id in document_ids}


def query_similar_documents(
    document: Document,
    top_k: int = 5,
    document_ids: Iterable[int | str] | None = None,
) -> list[Document]:
    """Return up to ``top_k`` Documents most similar to ``document``."""
    allowed_document_ids = normalize_document_ids(document_ids)
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    if not llm_index_exists():
        queue_llm_index_update_if_needed(
            rebuild=False,
            reason="LLM index not found for similarity query.",
        )
        return []

    config = AIConfig()

    from llama_index.core.retrievers import VectorIndexRetriever

    filters = (
        _document_id_filters(allowed_document_ids)
        if allowed_document_ids is not None
        else None
    )

    query_text = truncate_embedding_query(
        (document.title or "") + "\n" + (document.content or ""),
        chunk_size=config.llm_embedding_chunk_size,
    )
    # Hold the shared read lock for the whole retrieval so the connection is
    # never open across a compaction swap. The retrieve() call generates a
    # query embedding (a slow external request) and searches the vector store;
    # no Django ORM access happens during it, so release the pooled DB
    # connection for its duration. See #12976.
    with read_store() as store:
        index = load_or_build_index(config, store)
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=top_k,
            filters=filters,
        )
        with db_connection_released():
            results = retriever.retrieve(query_text)

    retrieved_document_ids: list[int] = []
    for node in results:
        document_id = node.metadata.get("document_id")
        if document_id is None:
            continue
        normalized = str(document_id)
        if allowed_document_ids is not None and normalized not in allowed_document_ids:
            continue
        try:
            retrieved_document_ids.append(int(normalized))
        except ValueError:  # pragma: no cover
            logger.warning(
                "Skipping LLM index result with invalid document_id %r.",
                document_id,
            )

    return list(Document.objects.filter(pk__in=retrieved_document_ids))
