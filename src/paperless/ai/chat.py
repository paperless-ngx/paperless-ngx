import logging

from django.contrib.auth.models import User
from llama_index.core import VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine

from paperless.ai.client import AIClient
from paperless.ai.indexing import get_document_retriever
from paperless.ai.indexing import load_index

logger = logging.getLogger("paperless.ai.chat")


def chat_with_documents(prompt: str, user: User) -> str:
    retriever = get_document_retriever(top_k=5)
    client = AIClient()

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        llm=client.llm,
    )

    logger.debug("Document chat prompt: %s", prompt)
    response = query_engine.query(prompt)
    logger.debug("Document chat response: %s", response)
    return str(response)


def chat_with_single_document(document, question: str, user):
    index = load_index()

    # Filter only the node(s) belonging to this doc
    nodes = [
        node
        for node in index.docstore.docs.values()
        if node.metadata.get("document_id") == str(document.id)
    ]

    if not nodes:
        raise Exception("This document is not indexed yet.")

    local_index = VectorStoreIndex.from_documents(nodes)

    client = AIClient()

    engine = RetrieverQueryEngine.from_args(
        retriever=local_index.as_retriever(similarity_top_k=3),
        llm=client.llm,
    )

    response = engine.query(question)
    return str(response)
