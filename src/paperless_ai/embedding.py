import re
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
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
                api_key=config.llm_api_key,
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


def build_llm_index_text(doc: Document) -> str:
    # Short structured fields (filename, storage path, ASN, title, tags, ...) live
    # in node.metadata: excluded from embeddings, shown to the LLM via metadata
    # prepend. Notes and Custom Fields stay in the body: Notes can be long free
    # text, Custom Fields are dynamic in count and best kept in the embedding.
    lines = [
        f"Notes: {','.join([str(c.note) for c in Note.objects.filter(document=doc)])}",
    ]

    for instance in doc.custom_fields.all():
        lines.append(f"Custom Field - {instance.field.name}: {instance}")

    lines.append("\nContent:\n")
    lines.append(doc.content or "")

    return _normalize_llm_index_text("\n".join(lines))
