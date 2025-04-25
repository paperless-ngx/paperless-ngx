import logging

from django.contrib.auth.models import User
from llama_index.core.query_engine import RetrieverQueryEngine

from paperless.ai.client import AIClient
from paperless.ai.indexing import get_document_retriever

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
