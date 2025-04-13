from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from langchain_core.documents import Document as LangchainDocument
from langchain_experimental.text_splitter import SemanticChunker
from langchain_mistralai.embeddings import MistralAIEmbeddings
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_redis import RedisConfig
from langchain_redis import RedisVectorStore

if TYPE_CHECKING:
    from datetime import datetime

    from documents.models import Document

logger = logging.getLogger("paperless.embeddings")


class DocumentEmbeddings:
    embedding_model: OpenAIEmbeddings | MistralAIEmbeddings
    splitter: SemanticChunker
    vector_store: RedisVectorStore

    def __init__(self) -> None:
        # last time a document changed and therefore training might be required
        self.last_doc_change_time: datetime | None = None

        if settings.EMBEDDING_PROVIDER == "openai":
            if not settings.OPENAI_API_KEY:
                logger.warning(
                    "PAPERLESS_OPENAI_API_KEY is not set. Embeddings will not work."
                )
                raise ValueError("PAPERLESS_OPENAI_API_KEY is not set")
            self.embedding_model = OpenAIEmbeddings(
                api_key=settings.OPENAI_API_KEY, model=settings.EMBEDDING_MODEL
            )
        elif settings.EMBEDDING_PROVIDER == "mistralai":
            if not settings.MISTRAL_API_KEY:
                logger.warning(
                    "PAPERLESS_MISTRAL_API_KEY is not set. Embeddings will not work."
                )
                raise ValueError("PAPERLESS_MISTRAL_API_KEY is not set")
            # rate_limiter = InMemoryRateLimiter(requests_per_second=1)
            self.embedding_model = MistralAIEmbeddings(
                api_key=settings.MISTRAL_API_KEY, model=settings.EMBEDDING_MODEL
            )
        else:
            raise ValueError(
                f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}"
            )

        self.splitter = SemanticChunker(self.embedding_model, min_chunk_size=2000)

        if not settings.EMBEDDING_REDIS_URL:
            logger.warning(
                "PAPERLESS_EMBEDDING_REDIS_URL is not set. Embeddings will not work."
            )
            raise ValueError("PAPERLESS_EMBEDDING_REDIS_URL is not set")
        redis_config = RedisConfig(
            redis_url=settings.EMBEDDING_REDIS_URL,
            index_name="document_embeddings",
        )
        self.vector_store = RedisVectorStore(self.embedding_model, redis_config)

    def embedd_document(self, document: Document) -> bool:
        if document.content is None:
            logger.warning(
                f"Document '{document.title}' has no content. Skipping embedding generation."
            )
            return False

        # First delete existing embeddings if they exist
        if document.embedding_index_ids:
            self.delete_embeddings(document.embedding_index_ids)
            document.embedding_index_ids = []
            document.save(update_fields=["embedding_index_ids"])
        try:
            chunks = self.splitter.split_text(document.content)
        except Exception as e:
            logger.error(f"Error splitting document '{document.title}': {e}")
            return False
        try:
            metadatas = [
                {
                    "document_id": document.pk,
                    "document_title": document.title,
                    "chunk_index": i,
                    "n_chunks": len(chunks),
                }
                for i in range(len(chunks))
            ]
        except Exception as e:
            logger.error(
                f"Error generating metadatas for document '{document.title}': {e}"
            )
            return False
        try:
            logger.debug(
                f"Adding {len(chunks)} chunks to vector store for document '{document.title}'"
            )
            # index_ids = self.vector_store.add_texts(chunks, metadatas=metadatas)
            index_ids = self.vector_store.add_documents(
                [
                    LangchainDocument(page_content=chunk, metadata=metadata)
                    for chunk, metadata in zip(chunks, metadatas)
                ]
            )
            document.embedding_index_ids = index_ids
            document.save(update_fields=("embedding_index_ids",))
        except Exception as e:
            logger.error(
                f"Error adding texts to vector store for document '{document.title}': {e}"
            )
            return False
        logger.info(
            f"Successfully generated and stored embeddings for document '{document.title}'"
        )
        return True

    def delete_embeddings(self, embedding_index_ids: list[str]):
        if embedding_index_ids:
            try:
                count = self.vector_store.index.drop_keys(embedding_index_ids)
                if count == len(embedding_index_ids):
                    logger.info(
                        f"Successfully deleted {count} entries from vector store"
                    )
                else:
                    logger.warning(
                        f"Only {count} entries were deleted from vector store ({len(embedding_index_ids)} were given)"
                    )
            except Exception as e:
                logger.error(f"Error deleting entries from vector store: {e}")
        else:
            logger.warning("No embedding index ids given to delete!")
