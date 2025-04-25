from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

from documents.models import Document
from documents.models import Note
from paperless.config import AIConfig

EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


def get_embedding_model():
    config = AIConfig()

    match config.llm_embedding_backend:
        case "openai":
            return OpenAIEmbedding(
                model=config.llm_embedding_model or "text-embedding-3-small",
                api_key=config.llm_api_key,
            )
        case "local":
            return HuggingFaceEmbedding(
                model_name=config.llm_embedding_model
                or "sentence-transformers/all-MiniLM-L6-v2",
            )
        case _:
            raise ValueError(
                f"Unsupported embedding backend: {config.llm_embedding_backend}",
            )


def get_embedding_dim() -> int:
    config = AIConfig()
    model = config.llm_embedding_model or (
        "text-embedding-3-small"
        if config.llm_embedding_backend == "openai"
        else "sentence-transformers/all-MiniLM-L6-v2"
    )
    if model not in EMBEDDING_DIMENSIONS:
        raise ValueError(f"Unknown embedding model: {model}")
    return EMBEDDING_DIMENSIONS[model]


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
