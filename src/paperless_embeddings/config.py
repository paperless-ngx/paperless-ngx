import dataclasses
import os

from pydantic import SecretStr

from paperless.config import OutputTypeConfig


@dataclasses.dataclass
class PaperlessEmbeddingsConfig(OutputTypeConfig):
    """
    Configuration for the Mistral OCR API
    """

    mistralai_api_key: SecretStr = dataclasses.field(init=False)
    embeddings_enabled: bool = dataclasses.field(init=False)
    embedding_model: str = dataclasses.field(init=False)
    openai_api_key: SecretStr = dataclasses.field(init=False)
    embedding_chunk_size: int = dataclasses.field(init=False)
    embedding_chunk_overlap: int = dataclasses.field(init=False)
    embedding_semantic_chunking: bool = dataclasses.field(init=False)
    redis_embeddings_url: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()

        # Use environment variables or settings with defaults
        self.mistralai_api_key = SecretStr(os.getenv("PAPERLESS_MISTRAL_API_KEY", ""))
        self.embeddings_enabled = (
            os.getenv("PAPERLESS_EMBEDDINGS_ENABLED", "true").lower() == "true"
        )
        self.embedding_model = os.getenv("PAPERLESS_EMBEDDING_MODEL", "openai")
        self.openai_api_key = SecretStr(os.getenv("PAPERLESS_OPENAI_API_KEY", ""))
        self.embedding_chunk_size = int(
            os.getenv("PAPERLESS_EMBEDDING_CHUNK_SIZE", "1000")
        )
        self.embedding_chunk_overlap = int(
            os.getenv("PAPERLESS_EMBEDDING_CHUNK_OVERLAP", "100")
        )
        self.embedding_semantic_chunking = (
            os.getenv("PAPERLESS_EMBEDDING_SEMANTIC_CHUNKING", "false").lower()
            == "true"
        )
        self.redis_embeddings_url = os.getenv(
            "PAPERLESS_REDIS_EMBEDDINGS_URL", "redis://docjarvis_redis:6378"
        )
