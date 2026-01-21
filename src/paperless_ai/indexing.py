import logging
import shutil
from datetime import timedelta
from pathlib import Path

import faiss
import llama_index.core.settings as llama_settings
import tqdm
from celery import states
from django.conf import settings
from django.utils import timezone
from llama_index.core import Document as LlamaDocument
from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.indices.prompt_helper import PromptHelper
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.prompts import PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.core.text_splitter import TokenTextSplitter
from llama_index.vector_stores.faiss import FaissVectorStore

from documents.models import Document
from documents.models import PaperlessTask
from paperless_ai.embedding import build_llm_index_text
from paperless_ai.embedding import get_embedding_dim
from paperless_ai.embedding import get_embedding_model

logger = logging.getLogger("paperless_ai.indexing")


def queue_llm_index_update_if_needed(*, rebuild: bool, reason: str) -> bool:
    from documents.tasks import llmindex_index

    has_running = PaperlessTask.objects.filter(
        task_name=PaperlessTask.TaskName.LLMINDEX_UPDATE,
        status__in=[states.PENDING, states.STARTED],
    ).exists()
    has_recent = PaperlessTask.objects.filter(
        task_name=PaperlessTask.TaskName.LLMINDEX_UPDATE,
        date_created__gte=(timezone.now() - timedelta(minutes=5)),
    ).exists()
    if has_running or has_recent:
        return False

    llmindex_index.delay(rebuild=rebuild, scheduled=False, auto=True)
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
        embedding_dim = get_embedding_dim()
        faiss_index = faiss.IndexFlatL2(embedding_dim)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        docstore = SimpleDocumentStore()
        index_store = SimpleIndexStore()
    else:
        vector_store = FaissVectorStore.from_persist_dir(settings.LLM_INDEX_DIR)
        docstore = SimpleDocumentStore.from_persist_dir(settings.LLM_INDEX_DIR)
        index_store = SimpleIndexStore.from_persist_dir(settings.LLM_INDEX_DIR)

    return StorageContext.from_defaults(
        docstore=docstore,
        index_store=index_store,
        vector_store=vector_store,
        persist_dir=settings.LLM_INDEX_DIR,
    )


def build_document_node(document: Document) -> list[BaseNode]:
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
    doc = LlamaDocument(text=text, metadata=metadata)
    parser = SimpleNodeParser()
    return parser.get_nodes_from_documents([doc])


def load_or_build_index(nodes=None):
    """
    Load an existing VectorStoreIndex if present,
    or build a new one using provided nodes if storage is empty.
    """
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


def remove_document_docstore_nodes(document: Document, index: VectorStoreIndex):
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


def update_llm_index(*, progress_bar_disable=False, rebuild=False) -> str:
    """
    Rebuild or update the LLM index.
    """
    nodes = []

    documents = Document.objects.all()
    if not documents.exists():
        msg = "No documents found to index."
        logger.warning(msg)
        return msg

    if rebuild or not vector_store_file_exists():
        # remove meta.json to force re-detection of embedding dim
        (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
        # Rebuild index from scratch
        logger.info("Rebuilding LLM index.")
        embed_model = get_embedding_model()
        llama_settings.Settings.embed_model = embed_model
        storage_context = get_or_create_storage_context(rebuild=True)
        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            document_nodes = build_document_node(document)
            nodes.extend(document_nodes)

        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=not progress_bar_disable,
        )
        msg = "LLM index rebuilt successfully."
    else:
        # Update existing index
        index = load_or_build_index()
        all_node_ids = list(index.docstore.docs.keys())
        existing_nodes = {
            node.metadata.get("document_id"): node
            for node in index.docstore.get_nodes(all_node_ids)
        }

        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            doc_id = str(document.id)
            document_modified = document.modified.isoformat()

            if doc_id in existing_nodes:
                node = existing_nodes[doc_id]
                node_modified = node.metadata.get("modified")

                if node_modified == document_modified:
                    continue

                # Again, delete from docstore, FAISS IndexFlatL2 are append-only
                index.docstore.delete_document(node.node_id)
                nodes.extend(build_document_node(document))
            else:
                # New document, add it
                nodes.extend(build_document_node(document))

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
    new_nodes = build_document_node(document)

    index = load_or_build_index(nodes=new_nodes)

    remove_document_docstore_nodes(document, index)

    index.insert_nodes(new_nodes)

    index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)


def llm_index_remove_document(document: Document):
    """
    Removes a document from the LLM index.
    """
    index = load_or_build_index()

    remove_document_docstore_nodes(document, index)

    index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)


def truncate_content(content: str) -> str:
    prompt_helper = PromptHelper(
        context_window=8192,
        num_output=512,
        chunk_overlap_ratio=0.1,
        chunk_size_limit=None,
    )
    splitter = TokenTextSplitter(separator=" ", chunk_size=512, chunk_overlap=50)
    content_chunks = splitter.split_text(content)
    truncated_chunks = prompt_helper.truncate(
        prompt=PromptTemplate(template="{content}"),
        text_chunks=content_chunks,
        padding=5,
    )
    return " ".join(truncated_chunks)


def query_similar_documents(
    document: Document,
    top_k: int = 5,
    document_ids: list[int] | None = None,
) -> list[Document]:
    """
    Runs a similarity query and returns top-k similar Document objects.
    """
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
            if node.metadata.get("document_id") in document_ids
        ]
        if document_ids
        else None
    )

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
        doc_ids=doc_node_ids,
    )

    query_text = truncate_content(
        (document.title or "") + "\n" + (document.content or ""),
    )
    results = retriever.retrieve(query_text)

    document_ids = [
        int(node.metadata["document_id"])
        for node in results
        if "document_id" in node.metadata
    ]

    return list(Document.objects.filter(pk__in=document_ids))
