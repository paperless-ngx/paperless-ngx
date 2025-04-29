import logging
import shutil

import faiss
import llama_index.core.settings as llama_settings
import tqdm
from django.conf import settings
from llama_index.core import Document as LlamaDocument
from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.vector_stores.faiss import FaissVectorStore

from documents.models import Document
from paperless.ai.embedding import build_llm_index_text
from paperless.ai.embedding import get_embedding_dim
from paperless.ai.embedding import get_embedding_model

logger = logging.getLogger("paperless.ai.indexing")


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


def update_llm_index(*, progress_bar_disable=False, rebuild=False):
    """
    Rebuild or update the LLM index.
    """
    nodes = []

    documents = Document.objects.all()
    if not documents.exists():
        logger.warning("No documents found to index.")
        return

    if rebuild:
        embed_model = get_embedding_model()
        llama_settings.Settings.embed_model = embed_model
        storage_context = get_or_create_storage_context(rebuild=rebuild)
        # Rebuild index from scratch
        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            document_nodes = build_document_node(document)
            nodes.extend(document_nodes)

        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=not progress_bar_disable,
        )
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
            logger.info(
                "Updating %d nodes in LLM index.",
                len(nodes),
            )
            index.insert_nodes(nodes)
        else:
            logger.info("No changes detected, skipping llm index rebuild.")

    index.storage_context.persist(persist_dir=settings.LLM_INDEX_DIR)


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


def query_similar_documents(document: Document, top_k: int = 5) -> list[Document]:
    """
    Runs a similarity query and returns top-k similar Document objects.
    """
    index = load_or_build_index()
    retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)

    query_text = (document.title or "") + "\n" + (document.content or "")
    results = retriever.retrieve(query_text)

    document_ids = [
        int(node.metadata["document_id"])
        for node in results
        if "document_id" in node.metadata
    ]

    return list(Document.objects.filter(pk__in=document_ids))
