import logging

from django.contrib.auth.models import User

from documents.models import Document
from documents.permissions import get_objects_for_user_owner_aware
from paperless.config import AIConfig
from paperless_ai.client import AIClient
from paperless_ai.indexing import query_similar_documents
from paperless_ai.indexing import truncate_content

logger = logging.getLogger("paperless_ai.rag_classifier")


def build_prompt_without_rag(document: Document) -> str:
    filename = document.filename or ""
    content = truncate_content(document.content[:4000] or "")

    return f"""
    You are a document classification assistant.

    Analyze the following document and extract the following information:
    - A short descriptive title
    - Tags that reflect the content
    - Names of people or organizations mentioned
    - The type or category of the document
    - Suggested folder paths for storing the document
    - Up to 3 relevant dates in YYYY-MM-DD format

    Filename:
    {filename}

    Content:
    {content}
    """.strip()


def build_prompt_with_rag(document: Document, user: User | None = None) -> str:
    base_prompt = build_prompt_without_rag(document)
    context = truncate_content(get_context_for_document(document, user))

    return f"""{base_prompt}

    Additional context from similar documents:
    {context}
    """.strip()


def get_context_for_document(
    doc: Document,
    user: User | None = None,
    max_docs: int = 5,
) -> str:
    visible_documents = (
        get_objects_for_user_owner_aware(
            user,
            "view_document",
            Document,
        )
        if user
        else None
    )
    similar_docs = query_similar_documents(
        document=doc,
        document_ids=[document.pk for document in visible_documents]
        if visible_documents
        else None,
    )[:max_docs]
    context_blocks = []
    for similar in similar_docs:
        text = similar.content[:1000] or ""
        title = similar.title or similar.filename or "Untitled"
        context_blocks.append(f"TITLE: {title}\n{text}")
    return "\n\n".join(context_blocks)


def parse_ai_response(raw: dict) -> dict:
    return {
        "title": raw.get("title", ""),
        "tags": raw.get("tags", []),
        "correspondents": raw.get("correspondents", []),
        "document_types": raw.get("document_types", []),
        "storage_paths": raw.get("storage_paths", []),
        "dates": raw.get("dates", []),
    }


def get_ai_document_classification(
    document: Document,
    user: User | None = None,
) -> dict:
    ai_config = AIConfig()

    prompt = (
        build_prompt_with_rag(document, user)
        if ai_config.llm_embedding_backend
        else build_prompt_without_rag(document)
    )

    client = AIClient()
    result = client.run_llm_query(prompt)
    return parse_ai_response(result)
