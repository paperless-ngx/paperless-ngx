import logging
import sys

from llama_index.core import VectorStoreIndex
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import RetrieverQueryEngine

from documents.models import Document
from paperless_ai.client import AIClient
from paperless_ai.indexing import load_or_build_index

logger = logging.getLogger("paperless_ai.chat")

MAX_SINGLE_DOC_CONTEXT_CHARS = 15000
SINGLE_DOC_SNIPPET_CHARS = 800

CHAT_PROMPT_TMPL = PromptTemplate(
    template="""Context information is below.
    ---------------------
    {context_str}
    ---------------------
    Given the context information and not prior knowledge, answer the query.
    Query: {query_str}
    Answer:""",
)


def stream_chat_with_documents(query_str: str, documents: list[Document]):
    client = AIClient()
    index = load_or_build_index()

    doc_ids = [str(doc.pk) for doc in documents]

    # Filter only the node(s) that match the document IDs
    nodes = [
        node
        for node in index.docstore.docs.values()
        if node.metadata.get("document_id") in doc_ids
    ]

    if len(nodes) == 0:
        logger.warning("No nodes found for the given documents.")
        yield "Sorry, I couldn't find any content to answer your question."
        return

    local_index = VectorStoreIndex(nodes=nodes)
    retriever = local_index.as_retriever(
        similarity_top_k=3 if len(documents) == 1 else 5,
    )

    if len(documents) == 1:
        # Just one doc — provide full content
        doc = documents[0]
        # TODO: include document metadata in the context
        content = doc.content or ""
        context_body = content

        if len(content) > MAX_SINGLE_DOC_CONTEXT_CHARS:
            logger.info(
                "Truncating single-document context from %s to %s characters",
                len(content),
                MAX_SINGLE_DOC_CONTEXT_CHARS,
            )
            context_body = content[:MAX_SINGLE_DOC_CONTEXT_CHARS]

            top_nodes = retriever.retrieve(query_str)
            if len(top_nodes) > 0:
                snippets = "\n\n".join(
                    f"TITLE: {node.metadata.get('title')}\n{node.text[:SINGLE_DOC_SNIPPET_CHARS]}"
                    for node in top_nodes
                )
                context_body = f"{context_body}\n\nTOP MATCHES:\n{snippets}"

        context = f"TITLE: {doc.title or doc.filename}\n{context_body}"
    else:
        top_nodes = retriever.retrieve(query_str)

        if len(top_nodes) == 0:
            logger.warning("Retriever returned no nodes for the given documents.")
            yield "Sorry, I couldn't find any content to answer your question."
            return

        context = "\n\n".join(
            f"TITLE: {node.metadata.get('title')}\n{node.text[:SINGLE_DOC_SNIPPET_CHARS]}"
            for node in top_nodes
        )

    prompt = CHAT_PROMPT_TMPL.partial_format(
        context_str=context,
        query_str=query_str,
    ).format(llm=client.llm)

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        llm=client.llm,
        streaming=True,
    )

    logger.debug("Document chat prompt: %s", prompt)

    response_stream = query_engine.query(prompt)

    for chunk in response_stream.response_gen:
        yield chunk
        sys.stdout.flush()
