import re
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from llama_index.core.base.embeddings.base import BaseEmbedding

from documents.models import Document
from paperless.config import AIConfig
from paperless.models import LLMEmbeddingBackend
from paperless.network import PinnedHostAsyncHTTPTransport
from paperless.network import PinnedHostHTTPTransport
from paperless.network import create_pinned_async_httpx_client
from paperless.network import create_pinned_httpx_client
from paperless.network import validate_outbound_http_url
from paperless_ai.client import PLACEHOLDER_API_KEY

OCR_LEADER_REGEX = re.compile(r"[._\-\u00b7]{4,}")
HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[ \t\u00a0]+")

# build_llm_index_header(): the longest header, in characters. It is embedded
# with every chunk, so it must leave the chunk's own text the room it needs in
# small-context embedding models.
LLM_INDEX_HEADER_MAX_LENGTH = 300


def get_embedding_model(config: AIConfig) -> "BaseEmbedding":
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
                    timeout=config.llm_request_timeout,
                )
                async_http_client = create_pinned_async_httpx_client(
                    endpoint,
                    allow_internal=config.llm_allow_internal_endpoints,
                    timeout=config.llm_request_timeout,
                )
            return OpenAILikeEmbedding(
                model_name=config.llm_embedding_model or "text-embedding-3-small",
                api_key=config.llm_embedding_api_key
                or config.llm_api_key
                or PLACEHOLDER_API_KEY,
                api_base=endpoint,
                timeout=config.llm_request_timeout,
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
                timeout=config.llm_request_timeout,
                transport=PinnedHostHTTPTransport(
                    allow_internal=config.llm_allow_internal_endpoints,
                ),
            )
            embedding._async_client = AsyncClient(
                host=endpoint,
                timeout=config.llm_request_timeout,
                transport=PinnedHostAsyncHTTPTransport(
                    allow_internal=config.llm_allow_internal_endpoints,
                ),
            )
            return embedding
        case _:
            raise ValueError(
                f"Unsupported embedding backend: {config.llm_embedding_backend}",
            )


_DEFAULT_MODEL_NAMES = {
    LLMEmbeddingBackend.OPENAI_LIKE: "text-embedding-3-small",
    LLMEmbeddingBackend.HUGGINGFACE: "sentence-transformers/all-MiniLM-L6-v2",
    LLMEmbeddingBackend.OLLAMA: "embeddinggemma",
}


def get_configured_model_name(config: AIConfig) -> str:
    """Return the canonical name of the currently configured embedding model."""
    # dict.get(key, default) overload resolution fails for TextChoices keys in some
    # type checkers; use `or` fallback to avoid the ambiguity.
    default = (
        _DEFAULT_MODEL_NAMES.get(
            config.llm_embedding_backend,
        )
        or "sentence-transformers/all-MiniLM-L6-v2"
    )
    return config.llm_embedding_model or default


def _normalize_llm_index_text(text: str) -> str:
    text = OCR_LEADER_REGEX.sub(" ", text)
    return HORIZONTAL_WHITESPACE_REGEX.sub(" ", text)


def build_llm_index_header(
    *,
    title: str | None,
    document_type: str | None,
    correspondent: str | None,
    tags: list[str],
) -> str:
    """A compact line naming a document, embedded with each of its chunks
    when PAPERLESS_AI_LLM_INDEX_EMBED_METADATA is enabled: curated titles,
    types, correspondents and tags are often a better semantic signal than
    the (OCR) content alone.
    """
    parts = [
        title,
        f"Type: {document_type}" if document_type else None,
        f"From: {correspondent}" if correspondent else None,
        f"Tags: {', '.join(tags)}" if tags else None,
    ]
    header = _normalize_llm_index_text(" · ".join(part for part in parts if part))
    header = " ".join(header.split())
    if len(header) > LLM_INDEX_HEADER_MAX_LENGTH:
        header = header[: LLM_INDEX_HEADER_MAX_LENGTH - 1].rstrip() + "…"
    return header


def build_llm_index_text(doc: Document) -> str:
    # Short structured fields (filename, storage path, ASN, title, tags, ...) live
    # in node.metadata: excluded from embeddings, shown to the LLM via metadata
    # prepend. Notes and Custom Fields stay in the body: Notes can be long free
    # text, Custom Fields are dynamic in count and best kept in the embedding.
    lines = [
        f"Notes: {','.join([str(c.note) for c in doc.notes.all()])}",
    ]

    for instance in doc.custom_fields.all():
        lines.append(f"Custom Field - {instance.field.name}: {instance}")

    lines.append("\nContent:\n")
    lines.append(doc.get_effective_content() or "")

    return _normalize_llm_index_text("\n".join(lines))
