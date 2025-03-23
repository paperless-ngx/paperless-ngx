"""
Document embedding generation and storage in Redis for the Mistral OCR module.
"""

import logging
import os
from typing import Any

from langchain.docstore.document import Document
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_redis import RedisConfig
from langchain_redis import RedisVectorStore
from pydantic import SecretStr

logger = logging.getLogger("paperless.embedding")


class EmbeddingGenerator:
    """
    Class to generate embeddings from document text and store them in Redis.
    """

    def __init__(self):
        """Initialize the embedding generator with configuration."""
        self.redis_url = os.getenv(
            "PAPERLESS_REDIS_EMBEDDINGS_URL", "redis://docjarvis_redis:6378"
        )
        self.embedding_model = os.getenv("PAPERLESS_EMBEDDING_MODEL", "openai")
        self.openai_api_key = SecretStr(os.getenv("PAPERLESS_OPENAI_API_KEY", ""))
        self.mistral_api_key = SecretStr(os.getenv("PAPERLESS_MISTRAL_API_KEY", ""))
        self.chunk_size = int(os.getenv("PAPERLESS_EMBEDDING_CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("PAPERLESS_EMBEDDING_CHUNK_OVERLAP", "100"))
        self.use_semantic_chunking = (
            os.getenv("PAPERLESS_EMBEDDING_SEMANTIC_CHUNKING", "false").lower()
            == "true"
        )

        # Initialize the appropriate embedding model
        self._initialize_embedding_model()
        self._initialize_redis()

    def _initialize_redis(self):
        if not self.embeddings:
            logger.error(
                "Embeddings model not initialized. Skipping Redis initialization."
            )
            return

        redis_config = RedisConfig(
            redis_url=self.redis_url,
            index_name="document_embeddings",
        )
        self.vector_store = RedisVectorStore(self.embeddings, redis_config)

    def _initialize_embedding_model(self):
        """Initialize the embedding model based on configuration."""
        if self.embedding_model == "openai":
            if not self.openai_api_key:
                logger.warning(
                    "OpenAI API key not set. Embeddings will not work. "
                    "Set PAPERLESS_OPENAI_API_KEY environment variable."
                )
                self.embeddings = None
                return

            self.embeddings = OpenAIEmbeddings(
                api_key=self.openai_api_key, model="text-embedding-3-small"
            )

        elif self.embedding_model == "mistral":
            if not self.mistral_api_key:
                logger.warning(
                    "Mistral API key not set. Embeddings will not work. "
                    "Set PAPERLESS_MISTRAL_API_KEY environment variable."
                )
                self.embeddings = None
                return

            self.embeddings = MistralAIEmbeddings(
                api_key=self.mistral_api_key, model="mistral-embed"
            )

        else:
            logger.warning(
                f"Unknown embedding model: {self.embedding_model}. "
                "Valid options are 'openai' or 'mistral'."
            )
            self.embeddings = None

    def _create_text_splitter(self):
        """Create an appropriate text splitter based on configuration."""
        if self.use_semantic_chunking:
            # Define headers to split on for markdown text
            headers_to_split_on = [
                ("#", "header1"),
                ("##", "header2"),
                ("###", "header3"),
                ("####", "header4"),
            ]

            # Create the markdown splitter
            markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=headers_to_split_on
            )

            # Also create a character-based splitter as fallback for large chunks
            char_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""],
            )

            return markdown_splitter, char_splitter
        else:
            # Just use character-based splitting
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""],
            ), None

    def generate_and_store_embeddings(
        self, document_id: int, text: str, metadata: dict[str, Any] | None = None
    ):
        """
        Generate embeddings for the document text and store them in Redis.

        Args:
            document_id: The ID of the document
            text: The text content of the document
            metadata: Additional metadata about the document
        """
        if not self.embeddings:
            logger.warning(
                "Embeddings model not initialized. Skipping embedding generation."
            )
            return False

        if not text or not text.strip():
            logger.warning(
                f"Empty text for document {document_id}. Skipping embedding generation."
            )
            return False

        try:
            # Prepare document metadata
            doc_metadata = metadata or {}
            doc_metadata["document_id"] = document_id

            # Create text splitter based on configuration
            primary_splitter, secondary_splitter = self._create_text_splitter()

            # Split the text into chunks
            if self.use_semantic_chunking:
                # Use markdown-aware splitting first
                chunks = primary_splitter.split_text(text)

                # For any large chunks, further split them with the character splitter
                final_chunks = []
                for chunk in chunks:
                    if len(chunk.page_content) > self.chunk_size:
                        # Further split this chunk
                        smaller_chunks = secondary_splitter.split_text(
                            chunk.page_content
                        )
                        # Merge the metadata
                        for small_chunk in smaller_chunks:
                            final_chunks.append(
                                Document(
                                    page_content=small_chunk,
                                    metadata={**chunk.metadata, **doc_metadata},
                                )
                            )
                    else:
                        # Keep the chunk as is
                        chunk.metadata.update(doc_metadata)
                        final_chunks.append(chunk)
            else:
                # Use standard character-based splitting
                chunks = primary_splitter.split_text(text)
                final_chunks = [
                    Document(page_content=chunk, metadata=doc_metadata)
                    for chunk in chunks
                ]

            logger.info(f"Split document {document_id} into {len(final_chunks)} chunks")

            self.vector_store.add_documents(final_chunks)

            logger.info(
                f"Successfully stored embeddings for document {document_id} in Redis"
            )
            return True

        except Exception as e:
            logger.exception(
                f"Error generating embeddings for document {document_id}: {e}"
            )
            return False

    def delete_document_embeddings(self, document_id: int) -> bool:
        """
        Delete all embeddings for a document from Redis.

        Args:
            document_id: The ID of the document
        """
        try:
            self.vector_store.delete(ids=[str(document_id)])
            logger.info(
                f"Successfully deleted embeddings for document {document_id} from Redis"
            )
            return True

        except Exception as e:
            logger.exception(
                f"Error deleting embeddings for document {document_id}: {e}"
            )
            return False
