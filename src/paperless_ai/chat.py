import json
import logging
import sys

from documents.models import Document
from paperless_ai.client import AIClient
from paperless_ai.indexing import load_or_build_index

logger = logging.getLogger("paperless_ai.chat")

MAX_SINGLE_DOC_CONTEXT_CHARS = 15000
SINGLE_DOC_SNIPPET_CHARS = 800
CHAT_METADATA_DELIMITER = "\n\n__PAPERLESS_CHAT_METADATA__"
MAX_CHAT_REFERENCES = 3

CHAT_PROMPT_TMPL = """Context information is below.
    ---------------------
    {context_str}
    ---------------------
    Given the context information and not prior knowledge, answer the query.
    Query: {query_str}
    Answer:"""


def _build_document_reference(
    document: Document,
    title: str | None = None,
) -> dict[str, int | str]:
    return {
        "id": document.pk,
        "title": title or document.title or document.filename,
    }


def _get_document_references(
    documents: list[Document],
    top_nodes: list,
) -> list[dict[str, int | str]]:
    allowed_documents = {doc.pk: doc for doc in documents}
    references: list[dict[str, int | str]] = []
    seen_document_ids: set[int] = set()

    for node in top_nodes:
        try:
            document_id = int(node.metadata["document_id"])
        except (KeyError, TypeError, ValueError):  # pragma: no cover
            continue

        if document_id in seen_document_ids or document_id not in allowed_documents:
            continue

        seen_document_ids.add(document_id)
        document = allowed_documents[document_id]
        references.append(
            _build_document_reference(document, node.metadata.get("title")),
        )

        if len(references) >= MAX_CHAT_REFERENCES:  # pragma: no cover
            break

    return references


def _format_chat_metadata_trailer(references: list[dict[str, int | str]]) -> str:
    return (
        f"{CHAT_METADATA_DELIMITER}"
        f"{json.dumps({'references': references}, separators=(',', ':'))}"
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

    from llama_index.core import VectorStoreIndex
    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.query_engine import RetrieverQueryEngine

    local_index = VectorStoreIndex(nodes=nodes)
    retriever = local_index.as_retriever(
        similarity_top_k=3 if len(documents) == 1 else 5,
    )

    if len(documents) == 1:
        # Just one doc — provide full content
        doc = documents[0]
        references = [_build_document_reference(doc)]
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

        references = _get_document_references(documents, top_nodes)
        context = "\n\n".join(
            f"TITLE: {node.metadata.get('title')}\n{node.text[:SINGLE_DOC_SNIPPET_CHARS]}"
            for node in top_nodes
        )

    prompt_template = PromptTemplate(template=CHAT_PROMPT_TMPL)
    prompt = prompt_template.partial_format(
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

    if references:
        yield _format_chat_metadata_trailer(references)
