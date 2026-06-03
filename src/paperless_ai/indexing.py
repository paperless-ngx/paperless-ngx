import json
import logging
import shutil
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from filelock import FileLock

from documents.models import Document
from documents.models import PaperlessTask
from documents.utils import IterWrapper
from documents.utils import identity
from paperless.config import AIConfig
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_embedding_model

if TYPE_CHECKING:
    from llama_index.core.schema import BaseNode

    from paperless_ai.vector_store import PaperlessLanceVectorStore


logger = logging.getLogger("paperless_ai.indexing")

LLM_INDEX_TABLE = "documents"

RAG_NUM_OUTPUT = 512
RAG_CHUNK_OVERLAP = 200


def _index_lock_path() -> Path:
    """Return the path used as the file lock for LanceDB index mutations.

    The lock file lives in DATA_DIR/locks/ (not inside LLM_INDEX_DIR) so that a
    rebuild — which calls store.drop_table() — cannot interfere with another
    worker that still holds the lock.
    """
    return settings.LLM_INDEX_LOCK


def queue_llm_index_update_if_needed(*, rebuild: bool, reason: str) -> bool:
    # NOTE: The check-then-enqueue sequence below is non-atomic (TOCTOU): two
    # concurrent workers can both observe no running task and both enqueue a
    # full rebuild. This is wasteful but not data-corrupting — update_llm_index
    # is itself protected by _index_lock_path(), so only one rebuild runs at a
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


def get_vector_store() -> "PaperlessLanceVectorStore":
    """Open (or lazily create) the LanceDB-backed vector store.

    Imports ``vector_store`` lazily so that importing ``indexing`` (which
    ``documents.tasks`` does at module top) never drags in lancedb/llama_index.
    """
    from paperless_ai.vector_store import PaperlessLanceVectorStore

    settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return PaperlessLanceVectorStore(
        uri=str(settings.LLM_INDEX_DIR),
        table_name=LLM_INDEX_TABLE,
    )


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
    )
    chunk_size = chunk_size or get_rag_chunk_size()
    parser = SimpleNodeParser(
        chunk_size=chunk_size,
        chunk_overlap=get_rag_chunk_overlap(chunk_size),
    )
    return parser.get_nodes_from_documents([doc])


def load_or_build_index(nodes=None):
    """Load the VectorStoreIndex backed by the LanceDB store.

    With ``stores_text=True`` the index runs off the vector store alone — no
    docstore or index store. ``nodes`` is accepted for signature compatibility
    but unused; the store is the source of truth.
    """
    import llama_index.core.settings as llama_settings
    from llama_index.core import VectorStoreIndex

    embed_model = get_embedding_model()
    llama_settings.Settings.embed_model = embed_model
    vector_store = get_vector_store()
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )


def vector_store_file_exists() -> bool:
    """True when the LanceDB table exists."""
    return get_vector_store().table_exists()


def migrate_stale_faiss_index() -> None:
    """Remove a pre-LanceDB FAISS index directory so it is rebuilt fresh."""
    stale_marker = settings.LLM_INDEX_DIR / "default__vector_store.json"
    if stale_marker.exists():
        logger.info("Removing stale FAISS LLM index; it will be rebuilt.")
        shutil.rmtree(settings.LLM_INDEX_DIR, ignore_errors=True)
        settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)


def embedding_dim_mismatch() -> bool:
    """True when the stored table's vector dim differs from the current model."""
    store = get_vector_store()
    stored = store.vector_dim()
    if stored is None:
        return False
    from paperless_ai.embedding import current_embedding_dim

    return stored != current_embedding_dim()


def get_rag_chunk_size() -> int:
    return AIConfig().llm_embedding_chunk_size


def get_rag_context_size() -> int:
    return AIConfig().llm_context_size


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


def _iter_existing_modified(store: "PaperlessLanceVectorStore") -> list[dict]:
    """One representative row per document_id, for modified-time comparison."""
    if not store.table_exists():
        return []
    seen: dict[str, dict] = {}
    for row in store.client.open_table(LLM_INDEX_TABLE).search().to_list():
        seen.setdefault(str(row["document_id"]), row)
    return list(seen.values())


def get_llm_index_compaction_retention() -> int:
    """Seconds of MVCC version history to keep during compaction."""
    return 60 * 60  # 1 hour: safe for in-flight readers, reclaims daily


def update_llm_index(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
    rebuild=False,
) -> str:
    """Rebuild or incrementally update the LLM index."""
    from llama_index.core.schema import MetadataMode

    migrate_stale_faiss_index()
    if not rebuild and vector_store_file_exists() and embedding_dim_mismatch():
        logger.warning("Embedding dimension changed; forcing LLM index rebuild.")
        rebuild = True

    documents = Document.objects.all()
    if not documents.exists():
        logger.warning("No documents found to index.")
        if not rebuild and not vector_store_file_exists():
            return "No documents found to index."

    chunk_size = AIConfig().llm_embedding_chunk_size
    embed_model = get_embedding_model()

    with FileLock(_index_lock_path()):
        if rebuild or not vector_store_file_exists():
            (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
            logger.info("Rebuilding LLM index.")
            store = get_vector_store()
            store.drop_table()
            for document in iter_wrapper(documents):
                nodes = build_document_node(document, chunk_size=chunk_size)
                for node in nodes:
                    node.embedding = embed_model.get_text_embedding(
                        node.get_content(metadata_mode=MetadataMode.EMBED),
                    )
                store.add(nodes)
            msg = "LLM index rebuilt successfully."
        else:
            store = get_vector_store()
            existing = {
                str(row["document_id"]): json.loads(row["node_content"])
                for row in _iter_existing_modified(store)
            }
            changed = 0
            for document in iter_wrapper(documents):
                doc_id = str(document.id)
                node_meta = existing.get(doc_id)
                if node_meta is not None:
                    stored_modified = node_meta.get("modified")
                    if stored_modified == document.modified.isoformat():
                        continue
                nodes = build_document_node(document, chunk_size=chunk_size)
                for node in nodes:
                    node.embedding = embed_model.get_text_embedding(
                        node.get_content(metadata_mode=MetadataMode.EMBED),
                    )
                store.upsert_document(doc_id, nodes)
                changed += 1
            msg = (
                "LLM index updated successfully."
                if changed
                else "No changes detected in LLM index."
            )

        store.ensure_document_id_scalar_index()
        store.maybe_create_ann_index()
        store.compact(retention_seconds=get_llm_index_compaction_retention())
    return msg


def llm_index_add_or_update_document(document: Document):
    """Add or atomically replace a document's chunks in the LLM index."""
    from llama_index.core.schema import MetadataMode

    new_nodes = build_document_node(document, chunk_size=get_rag_chunk_size())

    embed_model = get_embedding_model()
    for node in new_nodes:
        node.embedding = embed_model.get_text_embedding(
            node.get_content(metadata_mode=MetadataMode.EMBED),
        )

    with FileLock(_index_lock_path()):
        store = get_vector_store()
        store.upsert_document(str(document.id), new_nodes)
        store.ensure_document_id_scalar_index()


def llm_index_remove_document(document: Document):
    """Remove a document's chunks from the LLM index."""
    with FileLock(_index_lock_path()):
        store = get_vector_store()
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

    if not vector_store_file_exists():
        queue_llm_index_update_if_needed(
            rebuild=False,
            reason="LLM index not found for similarity query.",
        )
        return []

    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.vector_stores.types import FilterOperator
    from llama_index.core.vector_stores.types import MetadataFilter
    from llama_index.core.vector_stores.types import MetadataFilters

    index = load_or_build_index()

    filters = None
    if allowed_document_ids is not None:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    operator=FilterOperator.IN,
                    value=sorted(allowed_document_ids),
                ),
            ],
        )

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
        filters=filters,
    )

    config = AIConfig()
    query_text = truncate_content(
        (document.title or "") + "\n" + (document.content or ""),
        chunk_size=config.llm_embedding_chunk_size,
        context_size=config.llm_context_size,
    )
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
        except ValueError:
            logger.warning(
                "Skipping LLM index result with invalid document_id %r.",
                document_id,
            )

    return list(Document.objects.filter(pk__in=retrieved_document_ids))
