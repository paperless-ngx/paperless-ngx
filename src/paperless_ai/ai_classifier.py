import json
import logging

from django.contrib.auth.models import User
from llama_index.core.base.llms.types import CompletionResponse

from documents.models import Document
from documents.permissions import get_objects_for_user_owner_aware
from paperless.config import AIConfig
from paperless_ai.client import AIClient
from paperless_ai.indexing import query_similar_documents

logger = logging.getLogger("paperless_ai.rag_classifier")


def build_prompt_without_rag(document: Document) -> str:
    filename = document.filename or ""
    content = document.content or ""

    prompt = f"""
    You are an assistant that extracts structured information from documents.
    Only respond with the JSON object as described below.
    Never ask for further information, additional content or ask questions. Never include any other text.
    Suggested tags and document types must be strictly based on the content of the document.
    Do not change the field names or the JSON structure, only provide the values. Use double quotes and proper JSON syntax.
    Each field must be a list of plain strings.

    The JSON object must contain the following fields:
    - title: A short, descriptive title
    - tags: A list of simple tags like ["insurance", "medical", "receipts"]
    - correspondents: A list of names or organizations mentioned in the document
    - document_types: The type/category of the document (e.g. "invoice", "medical record")
    - storage_paths: Suggested folder paths (e.g. "Medical/Insurance")
    - dates: List up to 3 relevant dates in YYYY-MM-DD format

    The format of the JSON object is as follows:
    {{
        "title": "xxxxx",
        "tags": ["xxxx", "xxxx"],
        "correspondents": ["xxxx", "xxxx"],
        "document_types": ["xxxx", "xxxx"],
        "storage_paths": ["xxxx", "xxxx"],
        "dates": ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"],
    }}
    ---

    FILENAME:
    {filename}

    CONTENT:
    {content[:8000]}
    """

    return prompt


def build_prompt_with_rag(document: Document, user: User | None = None) -> str:
    context = get_context_for_document(document, user)
    prompt = build_prompt_without_rag(document)

    prompt += f"""

    CONTEXT FROM SIMILAR DOCUMENTS:
    {context[:4000]}
    """

    return prompt


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
        text = similar.content or ""
        title = similar.title or similar.filename or "Untitled"
        context_blocks.append(f"TITLE: {title}\n{text}")
    return "\n\n".join(context_blocks)


def parse_ai_response(response: CompletionResponse) -> dict:
    try:
        raw = json.loads(response.text)
        return {
            "title": raw.get("title"),
            "tags": raw.get("tags", []),
            "correspondents": raw.get("correspondents", []),
            "document_types": raw.get("document_types", []),
            "storage_paths": raw.get("storage_paths", []),
            "dates": raw.get("dates", []),
        }
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in AI response")
        return {}


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

    try:
        client = AIClient()
        result = client.run_llm_query(prompt)
        return parse_ai_response(result)
    except Exception as e:
        logger.exception("Failed AI classification")
        raise e
