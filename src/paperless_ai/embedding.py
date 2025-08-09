import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from django.conf import settings
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

from documents.models import Document
from documents.models import Note
from paperless.config import AIConfig
from paperless.models import LLMEmbeddingBackend


def get_embedding_model() -> BaseEmbedding:
    config = AIConfig()

    match config.llm_embedding_backend:
        case LLMEmbeddingBackend.OPENAI:
            return OpenAIEmbedding(
                model=config.llm_embedding_model or "text-embedding-3-small",
                api_key=config.llm_api_key,
            )
        case LLMEmbeddingBackend.HUGGINGFACE:
            return HuggingFaceEmbedding(
                model_name=config.llm_embedding_model
                or "sentence-transformers/all-MiniLM-L6-v2",
            )
        case _:
            raise ValueError(
                f"Unsupported embedding backend: {config.llm_embedding_backend}",
            )


def get_embedding_dim() -> int:
    """
    Loads embedding dimension from meta.json if available, otherwise infers it
    from a dummy embedding and stores it for future use.
    """
    config = AIConfig()
    model = config.llm_embedding_model or (
        "text-embedding-3-small"
        if config.llm_embedding_backend == "openai"
        else "sentence-transformers/all-MiniLM-L6-v2"
    )

    meta_path: Path = settings.LLM_INDEX_DIR / "meta.json"
    if meta_path.exists():
        with meta_path.open() as f:
            meta = json.load(f)
        if meta.get("embedding_model") != model:
            raise RuntimeError(
                f"Embedding model changed from {meta.get('embedding_model')} to {model}. "
                "You must rebuild the index.",
            )
        return meta["dim"]

    embedding_model = get_embedding_model()
    test_embed = embedding_model.get_text_embedding("test")
    dim = len(test_embed)

    with meta_path.open("w") as f:
        json.dump({"embedding_model": model, "dim": dim}, f)

    return dim


def build_llm_index_text(doc: Document) -> str:
    lines = [
        f"Title: {doc.title}",
        f"Filename: {doc.filename}",
        f"Created: {doc.created}",
        f"Added: {doc.added}",
        f"Modified: {doc.modified}",
        f"Tags: {', '.join(tag.name for tag in doc.tags.all())}",
        f"Document Type: {doc.document_type.name if doc.document_type else ''}",
        f"Correspondent: {doc.correspondent.name if doc.correspondent else ''}",
        f"Storage Path: {doc.storage_path.name if doc.storage_path else ''}",
        f"Archive Serial Number: {doc.archive_serial_number or ''}",
        f"Notes: {','.join([str(c.note) for c in Note.objects.filter(document=doc)])}",
    ]

    for instance in doc.custom_fields.all():
        lines.append(f"Custom Field - {instance.field.name}: {instance}")

    lines.append("\nContent:\n")
    lines.append(doc.content or "")

    return "\n".join(lines)
