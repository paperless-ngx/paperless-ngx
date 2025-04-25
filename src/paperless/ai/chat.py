import logging

from llama_index.core import VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine

from documents.models import Document
from paperless.ai.client import AIClient
from paperless.ai.indexing import load_index

logger = logging.getLogger("paperless.ai.chat")


def chat_with_documents(prompt: str, documents: list[Document]) -> str:
    client = AIClient()

    index = load_index()

    doc_ids = [doc.pk for doc in documents]

    # Filter only the node(s) that match the document IDs
    nodes = [
        node
        for node in index.docstore.docs.values()
        if node.metadata.get("document_id") in doc_ids
    ]

    if len(nodes) == 0:
        logger.warning("No nodes found for the given documents.")
        return "Sorry, I couldn't find any content to answer your question."

    local_index = VectorStoreIndex.from_documents(nodes)
    retriever = local_index.as_retriever(
        similarity_top_k=3 if len(documents) == 1 else 5,
    )

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        llm=client.llm,
    )

    logger.debug("Document chat prompt: %s", prompt)
    response = query_engine.query(prompt)
    logger.debug("Document chat response: %s", response)
    return str(response)
