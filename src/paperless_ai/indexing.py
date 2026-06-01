import logging
import shutil
from collections import defaultdict
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
from paperless_ai.embedding import get_embedding_dim
from paperless_ai.embedding import get_embedding_model

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex
    from llama_index.core.schema import BaseNode


logger = logging.getLogger("paperless_ai.indexing")

RAG_NUM_OUTPUT = 512
RAG_CHUNK_OVERLAP = 200


def _index_lock_path() -> Path:
    """Return the path used as the file lock for FAISS index mutations."""
    return settings.LLM_INDEX_DIR / "index.lock"


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


def get_or_create_storage_context(*, rebuild=False):
    """
    Loads or creates the StorageContext (vector store, docstore, index store).
    If rebuild=True, deletes and recreates everything.
    """
    if rebuild:
        shutil.rmtree(settings.LLM_INDEX_DIR, ignore_errors=True)
        settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if rebuild or not settings.LLM_INDEX_DIR.exists():
        import faiss
        from llama_index.core import StorageContext
        from llama_index.core.storage.docstore import SimpleDocumentStore
        from llama_index.core.storage.index_store import SimpleIndexStore
        from llama_index.vector_stores.faiss import FaissVectorStore

        settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        embedding_dim = get_embedding_dim()
        faiss_index = faiss.IndexFlatL2(embedding_dim)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        docstore = SimpleDocumentStore()
        index_store = SimpleIndexStore()
    else:
        from llama_index.core import StorageContext
        from llama_index.core.storage.docstore import SimpleDocumentStore
        from llama_index.core.storage.index_store import SimpleIndexStore
        from llama_index.vector_stores.faiss import FaissVectorStore

        vector_store = FaissVectorStore.from_persist_dir(settings.LLM_INDEX_DIR)
        docstore = SimpleDocumentStore.from_persist_dir(settings.LLM_INDEX_DIR)
        index_store = SimpleIndexStore.from_persist_dir(settings.LLM_INDEX_DIR)

    return StorageContext.from_defaults(
        docstore=docstore,
        index_store=index_store,
        vector_store=vector_store,
        persist_dir=settings.LLM_INDEX_DIR,
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
    """
    Load an existing VectorStoreIndex if present,
    or build a new one using provided nodes if storage is empty.
    """
    import llama_index.core.settings as llama_settings
    from llama_index.core import VectorStoreIndex
    from llama_index.core import load_index_from_storage

    embed_model = get_embedding_model()
    llama_settings.Settings.embed_model = embed_model
    storage_context = get_or_create_storage_context()
    try:
        return load_index_from_storage(storage_context=storage_context)
    except ValueError as e:
        logger.warning("Failed to load index from storage: %s", e)
        if not nodes:
            queue_llm_index_update_if_needed(
                rebuild=vector_store_file_exists(),
                reason="LLM index missing or invalid while loading.",
            )
            logger.info("No nodes provided for index creation.")
            raise
        return VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
        )


def remove_document_docstore_nodes(document: Document, index: "VectorStoreIndex"):
    """
    Removes existing documents from docstore for a given document from the index.
    This is necessary because FAISS IndexFlatL2 is append-only.
    """
    all_node_ids = list(index.docstore.docs.keys())
    existing_nodes = [
        node.node_id
        for node in index.docstore.get_nodes(all_node_ids)
        if node.metadata.get("document_id") == str(document.id)
    ]
    for node_id in existing_nodes:
        # Delete from docstore, FAISS IndexFlatL2 are append-only
        index.docstore.delete_document(node_id)


def vector_store_file_exists():
    """
    Check if the vector store file exists in the LLM index directory.
    """
    return Path(settings.LLM_INDEX_DIR / "default__vector_store.json").exists()


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


def update_llm_index(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
    rebuild=False,
) -> str:
    """
    Rebuild or update the LLM index.
    """
    from llama_index.core import VectorStoreIndex

    nodes = []

    documents = Document.objects.all()
    if not documents.exists():
        logger.warning("No documents found to index.")
        if not rebuild and not vector_store_file_exists():
            return "No documents found to index."

    config = AIConfig()
    chunk_size = config.llm_embedding_chunk_size

    with FileLock(_index_lock_path()):
        if rebuild or not vector_store_file_exists():
            # remove meta.json to force re-detection of embedding dim
            (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
            # Rebuild index from scratch
            logger.info("Rebuilding LLM index.")
            import llama_index.core.settings as llama_settings

            embed_model = get_embedding_model()
            llama_settings.Settings.embed_model = embed_model
            storage_context = get_or_create_storage_context(rebuild=True)
            for document in iter_wrapper(documents):
                document_nodes = build_document_node(document, chunk_size=chunk_size)
                nodes.extend(document_nodes)

            index = VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=False,
            )
            msg = "LLM index rebuilt successfully."
        else:
            # Update existing index
            index = load_or_build_index()
            existing_nodes: defaultdict[str, list] = defaultdict(list)
            for node in index.docstore.docs.values():
                doc_id = node.metadata.get("document_id")
                if doc_id is not None:
                    existing_nodes[doc_id].append(node)

            for document in iter_wrapper(documents):
                doc_id = str(document.id)
                document_modified = document.modified.isoformat()

                if doc_id in existing_nodes:
                    doc_nodes = existing_nodes[doc_id]
                    node_modified = doc_nodes[0].metadata.get("modified")

                    if node_modified == document_modified:
                        continue

                    # Delete from docstore, FAISS IndexFlatL2 are append-only
                    for node in doc_nodes:
                        index.docstore.delete_document(node.node_id)

                nodes.extend(build_document_node(document, chunk_size=chunk_size))

            if nodes:
                msg = "LLM index updated successfully."
                logger.info(
                    "Updating %d nodes in LLM index.",
                    len(nodes),
                )
                index.insert_nodes(nodes)
            else:
                msg = "No changes detected in LLM index."
                logger.info(msg)

        index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)
    return msg


def llm_index_add_or_update_document(document: Document):
    """
    Adds or updates a document in the LLM index.
    If the document already exists, it will be replaced.
    """
    new_nodes = build_document_node(document, chunk_size=get_rag_chunk_size())
    if not new_nodes:
        logger.warning(
            "No indexable content for document %s; skipping LLM index update.",
            document.pk,
        )
        return

    with FileLock(_index_lock_path()):
        index = load_or_build_index(nodes=new_nodes)

        remove_document_docstore_nodes(document, index)

        index.insert_nodes(new_nodes)

        index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)


def llm_index_remove_document(document: Document):
    """
    Removes a document from the LLM index.
    """
    with FileLock(_index_lock_path()):
        index = load_or_build_index()

        remove_document_docstore_nodes(document, index)

        index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)


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
    """
    Runs a similarity query and returns top-k similar Document objects.
    """
    allowed_document_ids = normalize_document_ids(document_ids)
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    if not vector_store_file_exists():
        queue_llm_index_update_if_needed(
            rebuild=False,
            reason="LLM index not found for similarity query.",
        )
        return []

    index = load_or_build_index()

    # constrain only the node(s) that match the document IDs, if given
    doc_node_ids = (
        [
            node.node_id
            for node in index.docstore.docs.values()
            if node.metadata.get("document_id") in allowed_document_ids
        ]
        if allowed_document_ids is not None
        else None
    )
    if doc_node_ids is not None and not doc_node_ids:
        return []

    from llama_index.core.retrievers import VectorIndexRetriever

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
        doc_ids=doc_node_ids,
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
        normalized_document_id = str(document_id)
        if (
            allowed_document_ids is not None
            and normalized_document_id not in allowed_document_ids
        ):
            continue
        try:
            retrieved_document_ids.append(int(normalized_document_id))
        except ValueError:
            logger.warning(
                "Skipping LLM index result with invalid document_id %r.",
                document_id,
            )

    return list(Document.objects.filter(pk__in=retrieved_document_ids))
