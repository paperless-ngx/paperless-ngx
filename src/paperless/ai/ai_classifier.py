import json
import logging

from documents.models import Document
from paperless.ai.client import AIClient

logger = logging.getLogger("paperless.ai.ai_classifier")


def get_ai_document_classification(document: Document) -> dict:
    """
    Returns classification suggestions for a given document using an LLM.
    Output schema matches the API's expected DocumentClassificationSuggestions format.
    """
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

    try:
        client = AIClient()
        result = client.run_llm_query(prompt)
        suggestions = parse_ai_classification_response(result)
        return suggestions or {}
    except Exception:
        logger.exception("Error during LLM classification: %s", exc_info=True)
        return {}


def parse_ai_classification_response(text: str) -> dict:
    """
    Parses LLM output and ensures it conforms to expected schema.
    """
    try:
        raw = json.loads(text)
        return {
            "title": raw.get("title"),
            "tags": raw.get("tags", []),
            "correspondents": [raw["correspondents"]]
            if isinstance(raw.get("correspondents"), str)
            else raw.get("correspondents", []),
            "document_types": [raw["document_types"]]
            if isinstance(raw.get("document_types"), str)
            else raw.get("document_types", []),
            "storage_paths": raw.get("storage_paths", []),
            "dates": [d for d in raw.get("dates", []) if d],
        }
    except json.JSONDecodeError:
        # fallback: try to extract JSON manually?
        logger.exception(
            "Failed to parse LLM classification response: %s",
            text,
            exc_info=True,
        )
        return {}
