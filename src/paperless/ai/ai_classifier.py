import json
import logging

from documents.models import Document
from paperless.ai.client import AIClient
from paperless.ai.rag import get_context_for_document
from paperless.config import AIConfig

logger = logging.getLogger("paperless.ai.rag_classifier")


def build_prompt_without_rag(document: Document) -> str:
    filename = document.filename or ""
    content = document.content or ""

    prompt = f"""
    You are an assistant that extracts structured information from documents.
    Only respond with the JSON object as described below.
    Never ask for further information, additional content or ask questions. Never include any other text.
    Suggested tags and document types must be strictly based on the content of the document.
    Do not change the field names or the JSON structure, only provide the values. Use double quotes and proper JSON syntax.

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
    {content[:8000]}  # Trim to safe size
    """

    return prompt


def build_prompt_with_rag(document: Document) -> str:
    context = get_context_for_document(document)
    content = document.content or ""
    filename = document.filename or ""

    prompt = f"""
    You are a helpful assistant that extracts structured information from documents.
    You have access to similar documents as context to help improve suggestions.

    Only output valid JSON in the format below. No additional explanations.

    The JSON object must contain:
    - title: A short, human-readable, descriptive title based on the content
    - tags: A list of relevant topics
    - correspondents: People or organizations involved
    - document_types: Type or category of the document
    - storage_paths: Suggested folder paths
    - dates: Up to 3 relevant dates in YYYY-MM-DD

    Here is the document:
    FILENAME:
    {filename}

    CONTENT:
    {content[:4000]}

    CONTEXT FROM SIMILAR DOCUMENTS:
    {context[:4000]}
    """

    return prompt


def parse_ai_response(text: str) -> dict:
    try:
        raw = json.loads(text)
        return {
            "title": raw.get("title"),
            "tags": raw.get("tags", []),
            "correspondents": raw.get("correspondents", []),
            "document_types": raw.get("document_types", []),
            "storage_paths": raw.get("storage_paths", []),
            "dates": raw.get("dates", []),
        }
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in RAG response")
        return {}


def get_ai_document_classification(document: Document) -> dict:
    ai_config = AIConfig()

    prompt = (
        build_prompt_with_rag(document)
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
