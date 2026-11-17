import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db import connections
from django.db.models import QuerySet

from documents.models import Document
from paperless.config import AIConfig
from paperless_ai.client import AIClient
from paperless_ai.db import db_connection_released
from paperless_ai.indexing import document_id_filters
from paperless_ai.indexing import exclude_document_ids_filter
from paperless_ai.indexing import get_rag_prompt_helper
from paperless_ai.indexing import load_or_build_index
from paperless_ai.indexing import read_store
from paperless_ai.prompts.context import ChatQaPromptContext
from paperless_ai.prompts.context import ChatRefinePromptContext
from paperless_ai.prompts.render import render_prompt

if TYPE_CHECKING:
    from llama_index.core.response_synthesizers import BaseSynthesizer
    from llama_index.core.schema import NodeWithScore

logger = logging.getLogger("paperless_ai.chat")

CHAT_METADATA_DELIMITER = "\n\n__PAPERLESS_CHAT_METADATA__"
CHAT_ERROR_MESSAGE = "Sorry, something went wrong while generating a response."
CHAT_NO_CONTENT_MESSAGE = "Sorry, I couldn't find any content to answer your question."
CHAT_RETRIEVER_TOP_K = 5
MAX_CHAT_REFERENCES = CHAT_RETRIEVER_TOP_K


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


def _permitted_documents_filter(store, permitted_ids: set[int]):
    """Scope retrieval to ``permitted_ids`` using whichever of an inclusion or
    exclusion list is shorter, since a long inclusion list is much slower for
    the vector store than a long exclusion list."""
    denied_ids = store.indexed_document_ids() - permitted_ids
    if len(permitted_ids) <= len(denied_ids):
        return document_id_filters(str(pk) for pk in permitted_ids)
    return exclude_document_ids_filter(str(pk) for pk in denied_ids)


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


async def stream_chat_with_documents(
    query_str: str,
    documents: QuerySet[Document],
    *,
    unrestricted: bool = False,
    output_language: str | None = None,
) -> AsyncIterator[str]:
    try:
        async for chunk in _stream_chat_with_documents(
            query_str,
            documents,
            unrestricted=unrestricted,
            output_language=output_language,
        ):
            yield chunk
    except Exception as e:
        logger.exception("Failed to stream document chat response: %s", e)
        yield CHAT_ERROR_MESSAGE


async def _stream_chat_with_documents(
    query_str: str,
    documents: QuerySet[Document],
    *,
    unrestricted: bool = False,
    output_language: str | None = None,
) -> AsyncIterator[str]:
    prepared = await sync_to_async(_prepare_chat)(
        query_str,
        documents,
        unrestricted=unrestricted,
        output_language=output_language,
    )
    if prepared is None:
        yield CHAT_NO_CONTENT_MESSAGE
        return
    response_synthesizer, top_nodes, references = prepared

    logger.debug("Document chat query: %s", query_str)
    response_stream = await response_synthesizer.asynthesize(query_str, top_nodes)
    async for chunk in response_stream.async_response_gen():
        yield chunk

    if references:
        yield _format_chat_metadata_trailer(references)


def _prepare_chat(
    query_str: str,
    documents: QuerySet[Document],
    *,
    unrestricted: bool,
    output_language: str | None,
) -> tuple["BaseSynthesizer", list["NodeWithScore"], list[dict[str, int | str]]] | None:
    """Everything before the answer streams, all of it blocking: ORM queries,
    the index read lock and its thread-bound sqlite connection, the query
    embedding, and building the LLM client. Returns None when there is no
    content to answer from.
    """
    if not documents.exists():
        return None

    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.response_synthesizers import get_response_synthesizer
    from llama_index.core.retrievers import VectorIndexRetriever

    config = AIConfig()
    permitted_ids: set[int] | None = None
    if unrestricted:
        # Exclude trashed ids (usually few) rather than send every permitted
        # id on each query. Trashed documents stay indexed until permanent
        # deletion (post_delete, not trash), so must be excluded explicitly.
        trashed_ids = Document.deleted_objects.values_list("pk", flat=True)
        filters = exclude_document_ids_filter(str(pk) for pk in trashed_ids)
    else:
        permitted_ids = set(documents.values_list("pk", flat=True))

    # Hold the shared read lock only while reading the index, so the compaction
    # swap cannot replace the database file while this connection is open.
    with read_store() as store:
        if permitted_ids is not None:
            filters = _permitted_documents_filter(store, permitted_ids)
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

    if permitted_ids is not None:
        # An exclusion filter fails open for a document indexed after the
        # permitted set was read, so drop anything not explicitly permitted.
        top_nodes = [
            node
            for node in top_nodes
            if int(node.metadata["document_id"]) in permitted_ids
        ]

    if not top_nodes:
        logger.warning("No nodes found for the given documents.")
        return None

    references = _get_document_references(documents, top_nodes)

    client = AIClient()
    response_synthesizer = get_response_synthesizer(
        llm=client.llm,
        prompt_helper=get_rag_prompt_helper(
            chunk_size=config.llm_embedding_chunk_size,
            context_size=config.llm_context_size,
        ),
        text_qa_template=PromptTemplate(template=_build_chat_prompt(output_language)),
        refine_template=PromptTemplate(
            template=_build_refine_prompt(output_language),
        ),
        streaming=True,
    )

    # No ORM access happens while the answer streams, so hand the pooled DB
    # connection back now rather than pin it for the whole stream. See #12976.
    connections.close_all()

    return response_synthesizer, top_nodes, references
