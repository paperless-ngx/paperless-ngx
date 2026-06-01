import json
import re
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from pathlib import Path

    from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from documents.models import Note
from paperless.config import AIConfig
from paperless.models import LLMEmbeddingBackend
from paperless.network import PinnedHostAsyncHTTPTransport
from paperless.network import PinnedHostHTTPTransport
from paperless.network import create_pinned_async_httpx_client
from paperless.network import create_pinned_httpx_client
from paperless.network import validate_outbound_http_url

OCR_LEADER_REGEX = re.compile(r"[._\-\u00b7]{4,}")
HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[ \t\u00a0]+")


def get_embedding_model() -> "BaseEmbedding":
    config = AIConfig()

    match config.llm_embedding_backend:
        case LLMEmbeddingBackend.OPENAI_LIKE:
            from llama_index.embeddings.openai_like import OpenAILikeEmbedding

            endpoint = config.llm_embedding_endpoint or config.llm_endpoint or None
            http_client = None
            async_http_client = None
            if endpoint:
                http_client = create_pinned_httpx_client(
                    endpoint,
                    allow_internal=config.llm_allow_internal_endpoints,
                )
                async_http_client = create_pinned_async_httpx_client(
                    endpoint,
                    allow_internal=config.llm_allow_internal_endpoints,
                )
            return OpenAILikeEmbedding(
                model_name=config.llm_embedding_model or "text-embedding-3-small",
                api_key=config.llm_api_key,
                api_base=endpoint,
                http_client=http_client,
                async_http_client=async_http_client,
            )
        case LLMEmbeddingBackend.HUGGINGFACE:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            return HuggingFaceEmbedding(
                model_name=config.llm_embedding_model
                or "sentence-transformers/all-MiniLM-L6-v2",
                cache_folder=str(settings.DATA_DIR / "hf_cache"),
            )
        case LLMEmbeddingBackend.OLLAMA:
            from llama_index.embeddings.ollama import OllamaEmbedding
            from ollama import AsyncClient
            from ollama import Client

            endpoint = (
                config.llm_embedding_endpoint
                or config.llm_endpoint
                or "http://localhost:11434"
            )
            validate_outbound_http_url(
                endpoint,
                allow_internal=config.llm_allow_internal_endpoints,
            )
            embedding = OllamaEmbedding(
                model_name=config.llm_embedding_model or "embeddinggemma",
                base_url=endpoint,
                ollama_additional_kwargs={"num_ctx": config.llm_context_size},
            )
            embedding._client = Client(
                host=endpoint,
                transport=PinnedHostHTTPTransport(
                    allow_internal=config.llm_allow_internal_endpoints,
                ),
            )
            embedding._async_client = AsyncClient(
                host=endpoint,
                transport=PinnedHostAsyncHTTPTransport(
                    allow_internal=config.llm_allow_internal_endpoints,
                ),
            )
            return embedding
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
    default_model = {
        LLMEmbeddingBackend.OPENAI_LIKE: "text-embedding-3-small",
        LLMEmbeddingBackend.HUGGINGFACE: "sentence-transformers/all-MiniLM-L6-v2",
        LLMEmbeddingBackend.OLLAMA: "embeddinggemma",
    }.get(
        config.llm_embedding_backend,
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    model = config.llm_embedding_model or default_model

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


def _normalize_llm_index_text(text: str) -> str:
    text = OCR_LEADER_REGEX.sub(" ", text)
    return HORIZONTAL_WHITESPACE_REGEX.sub(" ", text)


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

    return _normalize_llm_index_text("\n".join(lines))
