from __future__ import annotations

import logging
from pathlib import Path

from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.dispatch import receiver

from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_mistralai.embeddings import MistralAIEmbeddings
from langchain_redis import RedisConfig
from langchain_redis import RedisVectorStore
from langchain_core.rate_limiters import InMemoryRateLimiter


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
                logger.warning("PAPERLESS_OPENAI_API_KEY is not set. Embeddings will not work.")
                raise ValueError("PAPERLESS_OPENAI_API_KEY is not set")
            self.embedding_model = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY, model=settings.EMBEDDING_MODEL)
        elif settings.EMBEDDING_PROVIDER == "mistralai":
            if not settings.MISTRAL_API_KEY:
                logger.warning("PAPERLESS_MISTRAL_API_KEY is not set. Embeddings will not work.")
                raise ValueError("PAPERLESS_MISTRAL_API_KEY is not set")
            # rate_limiter = InMemoryRateLimiter(requests_per_second=1)
            self.embedding_model = MistralAIEmbeddings(api_key=settings.MISTRAL_API_KEY, model=settings.EMBEDDING_MODEL)
        else:
            raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}")

        self.splitter = SemanticChunker(self.embedding_model)

        if not settings.EMBEDDING_REDIS_URL:
            logger.warning("PAPERLESS_EMBEDDING_REDIS_URL is not set. Embeddings will not work.")
            raise ValueError("PAPERLESS_EMBEDDING_REDIS_URL is not set")
        redis_config = RedisConfig(
            redis_url=settings.EMBEDDING_REDIS_URL,
            index_name="document_embeddings",
        )
        self.vector_store = RedisVectorStore(self.embedding_model, redis_config)

    def embedd_document(self, document: Document) -> bool:
        if document.content is None:
            logger.warning(f"Document '{document.title}' has no content. Skipping embedding generation.")
            return False
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
                }
                for i in range(len(chunks))
            ]
        except Exception as e:
            logger.error(f"Error generating metadatas for document '{document.title}': {e}")
            return False
        try:
            logger.debug(f"Adding {len(chunks)} chunks to vector store for document '{document.title}'")
            self.vector_store.add_texts(chunks, metadatas=metadatas)
        except Exception as e:
            logger.error(f"Error adding texts to vector store for document '{document.title}': {e}")
            return False
        logger.info(f"Successfully generated and stored embeddings for document '{document.title}'")
        return True

    def delete_embeddings(self, document_ids) -> bool:
        from redisvl.query.filter import Tag
        from redisvl.query import FilterQuery
        # Redis query index for all entries with the document_id in the metadatas
        keys_to_delete = []
        for document_id in document_ids:
            try:
                filter_condition = Tag("document_id") == str(document_id)
                query_results = self.vector_store.index.query(FilterQuery(filter_expression=filter_condition))
                if query_results:
                    # Extract document keys from query results
                    for result in query_results:
                        if isinstance(result, dict) and "id" in result:
                            keys_to_delete.append(result["id"])
                    logger.info(f"Found {len(query_results)} entries to delete for document_id {document_id}")
                else:
                    logger.warning(f"No entries found for document_id {document_id}")
            except Exception as e:
                logger.error(f"Error querying vector store for document_id {document_id}: {e}")

        if keys_to_delete:
            try:
                self.vector_store.delete(keys_to_delete)
                logger.info(f"Successfully deleted {len(keys_to_delete)} entries from vector store")
                return True
            except Exception as e:
                logger.error(f"Error deleting entries from vector store: {e}")
                return False
        else:
            logger.warning("No entries found to delete")
            return True
