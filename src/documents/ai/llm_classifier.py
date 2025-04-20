import json
import logging

from documents.ai.client import run_llm_query
from documents.models import Document

logger = logging.getLogger("paperless.ai.llm_classifier")


def get_ai_document_classification(document: Document) -> dict:
    """
    Returns classification suggestions for a given document using an LLM.
    Output schema matches the API's expected DocumentClassificationSuggestions format.
    """
    filename = document.filename or ""
    content = document.content or ""

    prompt = f"""
    You are a document classification assistant. Based on the content below, return a JSON object suggesting the following classification fields:
    - title: A descriptive title for the document
    - tags: A list of tags that describe the document (e.g. ["medical", "insurance"])
    - correspondent: Who sent or issued this document (e.g. "Kaiser Permanente")
    - document_types: The type or category (e.g. "invoice", "medical record", "statement")
    - storage_paths: Suggested storage folders (e.g. "Insurance/2024")
    - dates: Up to 3 dates in ISO format (YYYY-MM-DD) found in the document, relevant to its content

    Return only a valid JSON object. Do not add commentary.

    FILENAME: {filename}

    CONTENT:
    {content}
    """

    try:
        result = run_llm_query(prompt)
        suggestions = parse_llm_classification_response(result)
        return suggestions
    except Exception as e:
        logger.error(f"Error during LLM classification: {e}")
        return None


def parse_llm_classification_response(text: str) -> dict:
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
        return {}
