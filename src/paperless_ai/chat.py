import json
import logging
import sys

from django.db.models import QuerySet

from documents.models import Document
from paperless.config import AIConfig
from paperless_ai.client import AIClient
from paperless_ai.db import db_connection_released
from paperless_ai.indexing import _document_id_filters
from paperless_ai.indexing import get_rag_prompt_helper
from paperless_ai.indexing import load_or_build_index
from paperless_ai.indexing import read_store
from paperless_ai.prompts.context import ChatQaPromptContext
from paperless_ai.prompts.context import ChatRefinePromptContext
from paperless_ai.prompts.render import render_prompt

logger = logging.getLogger("paperless_ai.chat")

CHAT_METADATA_DELIMITER = "\n\n__PAPERLESS_CHAT_METADATA__"
CHAT_ERROR_MESSAGE = "Sorry, something went wrong while generating a response."
CHAT_NO_CONTENT_MESSAGE = "Sorry, I couldn't find any content to answer your question."
MAX_CHAT_REFERENCES = 3
CHAT_RETRIEVER_TOP_K = 5


def _build_chat_prompt(output_language: str | None) -> str:
    return render_prompt(ChatQaPromptContext(output_language=output_language))


def _build_refine_prompt(output_language: str | None) -> str:
    return render_prompt(
        ChatRefinePromptContext(output_language=output_language),
    )


def _build_document_reference(
    document: Document,
    title: str | None = None,
) -> dict[str, int | str]:
    return {
        "id": document.pk,
        "title": title or document.title or document.filename,
    }


def _get_document_references(
    documents: QuerySet[Document],
    top_nodes: list,
) -> list[dict[str, int | str]]:
    candidate_ids: set[int] = set()
    for node in top_nodes:
        try:
            candidate_ids.add(int(node.metadata["document_id"]))
        except (KeyError, TypeError, ValueError):  # pragma: no cover
            continue

    if not candidate_ids:
        return []

    allowed_documents = {doc.pk: doc for doc in documents.filter(pk__in=candidate_ids)}

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


def stream_chat_with_documents(
    query_str: str,
    documents: QuerySet[Document],
    output_language: str | None = None,
):
    try:
        yield from _stream_chat_with_documents(
            query_str,
            documents,
            output_language=output_language,
        )
    except Exception:
        logger.exception("Failed to stream document chat response")
        yield CHAT_ERROR_MESSAGE


def _stream_chat_with_documents(
    query_str: str,
    documents: QuerySet[Document],
    output_language: str | None = None,
):
    if not documents.exists():
        yield CHAT_NO_CONTENT_MESSAGE
        return

    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.response_synthesizers import get_response_synthesizer
    from llama_index.core.retrievers import VectorIndexRetriever

    config = AIConfig()
    filters = _document_id_filters(
        str(pk) for pk in documents.values_list("pk", flat=True)
    )

    # Hold the shared read lock for the whole operation: the query engine
    # retrieves from the vector store again during synthesis, so the connection
    # must stay open (and the swap must not run) until the stream finishes.
    with read_store() as store:
        index = load_or_build_index(config, store)
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=CHAT_RETRIEVER_TOP_K,
            filters=filters,
        )

        # Slow query-embedding + vector search; no Django ORM access happens
        # during it, so release the pooled DB connection for its duration. See
        # #12976.
        with db_connection_released():
            top_nodes = retriever.retrieve(query_str)
        if not top_nodes:
            logger.warning("No nodes found for the given documents.")
            yield CHAT_NO_CONTENT_MESSAGE
            return

        client = AIClient()

        references = _get_document_references(documents, top_nodes)

        prompt_template = PromptTemplate(template=_build_chat_prompt(output_language))
        refine_template = PromptTemplate(template=_build_refine_prompt(output_language))
        response_synthesizer = get_response_synthesizer(
            llm=client.llm,
            prompt_helper=get_rag_prompt_helper(
                chunk_size=config.llm_embedding_chunk_size,
                context_size=config.llm_context_size,
            ),
            text_qa_template=prompt_template,
            refine_template=refine_template,
            streaming=True,
        )
        query_engine = RetrieverQueryEngine.from_args(
            retriever=retriever,
            llm=client.llm,
            response_synthesizer=response_synthesizer,
            streaming=True,
        )

        logger.debug("Document chat query: %s", query_str)
        # Release the pooled DB connection for the slow streaming LLM response
        # so it is not pinned for the whole stream; see paperless_ai.db and
        # #12976.
        with db_connection_released():
            response_stream = query_engine.query(query_str)
            for chunk in response_stream.response_gen:
                yield chunk
                sys.stdout.flush()

            if references:
                yield _format_chat_metadata_trailer(references)
