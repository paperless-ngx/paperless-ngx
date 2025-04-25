import logging

import llama_index.core.settings as llama_settings
from django.conf import settings
from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.vector_stores.faiss import FaissVectorStore

from documents.models import Document
from paperless.ai.embedding import get_embedding_model

logger = logging.getLogger("paperless.ai.indexing")


def load_index() -> VectorStoreIndex:
    """Loads the persisted LlamaIndex from disk."""
    vector_store = FaissVectorStore.from_persist_dir(settings.LLM_INDEX_DIR)
    embed_model = get_embedding_model()

    llama_settings.Settings.embed_model = embed_model
    llama_settings.Settings.chunk_size = 512

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=settings.LLM_INDEX_DIR,
    )
    return load_index_from_storage(storage_context)


def query_similar_documents(document: Document, top_k: int = 5) -> list[Document]:
    """Runs a similarity query and returns top-k similar Document objects."""

    # Load index
    index = load_index()
    retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)

    # Build query from the document text
    query_text = (document.title or "") + "\n" + (document.content or "")

    # Query
    results = retriever.retrieve(query_text)

    # Each result.node.metadata["document_id"] should match our stored doc
    document_ids = [
        int(node.metadata["document_id"])
        for node in results
        if "document_id" in node.metadata
    ]

    return list(Document.objects.filter(pk__in=document_ids))
