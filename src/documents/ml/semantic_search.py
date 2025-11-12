"""
Semantic Search for IntelliDocs-ngx.

Provides search by meaning rather than just keyword matching.
Uses sentence embeddings to understand the semantic content of documents.

Examples:
- Query: "tax documents from 2023"
  Finds: Documents about taxes, returns, deductions from 2023
  
- Query: "medical bills"
  Finds: Invoices from hospitals, clinics, prescriptions, insurance claims
  
- Query: "employment contract"
  Finds: Job offers, agreements, NDAs, work contracts
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util

from documents.ml.model_cache import ModelCacheManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger("paperless.ml.semantic_search")


class SemanticSearch:
    """
    Semantic search using sentence embeddings.
    
    Creates vector representations of documents and queries,
    then finds similar documents using cosine similarity.
    
    This provides much better search results than keyword matching:
    - Understands synonyms (invoice = bill)
    - Understands context (medical + bill = healthcare invoice)
    - Finds related concepts (tax = IRS, deduction, return)
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str | None = None,
        use_cache: bool = True,
    ):
        """
        Initialize semantic search.
        
        Args:
            model_name: Sentence transformer model
                       Default: all-MiniLM-L6-v2 (80MB, fast, good quality)
                       Alternatives:
                       - paraphrase-multilingual-MiniLM-L12-v2 (multilingual)
                       - all-mpnet-base-v2 (420MB, highest quality)
                       - all-MiniLM-L12-v2 (120MB, balanced)
            cache_dir: Directory to cache model
            use_cache: Whether to use model cache (default: True)
        """
        logger.info(
            f"Initializing SemanticSearch with model: {model_name} "
            f"(caching: {use_cache})"
        )

        self.model_name = model_name
        self.use_cache = use_cache
        self.cache_manager = ModelCacheManager.get_instance(
            disk_cache_dir=cache_dir,
        ) if use_cache else None
        
        # Cache key for this model
        cache_key = f"semantic_search_{model_name}"
        
        if self.use_cache and self.cache_manager:
            # Load model from cache
            def loader():
                return SentenceTransformer(model_name, cache_folder=cache_dir)
            
            self.model = self.cache_manager.get_or_load_model(cache_key, loader)
            
            # Try to load embeddings from disk
            embeddings = self.cache_manager.load_embeddings_from_disk("document_embeddings")
            self.document_embeddings = embeddings if embeddings else {}
            self.document_metadata = {}
        else:
            # Load without caching
            self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
            self.document_embeddings = {}
            self.document_metadata = {}

        logger.info("SemanticSearch initialized successfully")

    def index_document(
        self,
        document_id: int,
        text: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Index a document for semantic search.
        
        Creates an embedding vector for the document and stores it.
        
        Args:
            document_id: Document ID
            text: Document text content
            metadata: Optional metadata (title, date, tags, etc.)
        """
        logger.debug(f"Indexing document {document_id}")

        # Create embedding
        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        # Store embedding and metadata
        self.document_embeddings[document_id] = embedding
        self.document_metadata[document_id] = metadata or {}

    def index_documents_batch(
        self,
        documents: list[tuple[int, str, dict | None]],
        batch_size: int = 32,
    ) -> None:
        """
        Index multiple documents efficiently.
        
        Args:
            documents: List of (document_id, text, metadata) tuples
            batch_size: Batch size for encoding
        """
        logger.info(f"Batch indexing {len(documents)} documents")

        # Process in batches for efficiency
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            # Extract texts and IDs
            doc_ids = [doc[0] for doc in batch]
            texts = [doc[1] for doc in batch]
            metadatas = [doc[2] or {} for doc in batch]

            # Create embeddings for batch
            embeddings = self.model.encode(
                texts,
                convert_to_tensor=True,
                show_progress_bar=False,
                batch_size=batch_size,
            )

            # Store embeddings and metadata
            for doc_id, embedding, metadata in zip(doc_ids, embeddings, metadatas):
                self.document_embeddings[doc_id] = embedding
                self.document_metadata[doc_id] = metadata

        logger.info(f"Indexed {len(documents)} documents successfully")
        
        # Save embeddings to disk cache if enabled
        if self.use_cache and self.cache_manager:
            self.cache_manager.save_embeddings_to_disk(
                "document_embeddings",
                self.document_embeddings,
            )

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[int, float]]:
        """
        Search documents by semantic similarity.
        
        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            list: List of (document_id, similarity_score) tuples
                  Sorted by similarity (highest first)
        """
        if not self.document_embeddings:
            logger.warning("No documents indexed")
            return []

        logger.info(f"Searching for: '{query}' (top_k={top_k})")

        # Create query embedding
        query_embedding = self.model.encode(
            query,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        # Calculate similarities with all documents
        similarities = []
        for doc_id, doc_embedding in self.document_embeddings.items():
            similarity = util.cos_sim(query_embedding, doc_embedding).item()

            # Only include if above minimum score
            if similarity >= min_score:
                similarities.append((doc_id, similarity))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        results = similarities[:top_k]

        logger.info(f"Found {len(results)} results")
        return results

    def search_with_metadata(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict]:
        """
        Search and return results with metadata.
        
        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            list: List of result dictionaries
                  [
                      {
                          'document_id': 123,
                          'score': 0.85,
                          'metadata': {...}
                      },
                      ...
                  ]
        """
        # Get basic results
        results = self.search(query, top_k, min_score)

        # Add metadata
        results_with_metadata = []
        for doc_id, score in results:
            results_with_metadata.append(
                {
                    "document_id": doc_id,
                    "score": score,
                    "metadata": self.document_metadata.get(doc_id, {}),
                },
            )

        return results_with_metadata

    def find_similar_documents(
        self,
        document_id: int,
        top_k: int = 10,
        min_score: float = 0.3,
    ) -> list[tuple[int, float]]:
        """
        Find documents similar to a given document.
        
        Useful for "Find similar" functionality.
        
        Args:
            document_id: Document ID to find similar documents for
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            list: List of (document_id, similarity_score) tuples
                  Excludes the source document
        """
        if document_id not in self.document_embeddings:
            logger.warning(f"Document {document_id} not indexed")
            return []

        logger.info(f"Finding documents similar to {document_id}")

        # Get source document embedding
        source_embedding = self.document_embeddings[document_id]

        # Calculate similarities with all other documents
        similarities = []
        for doc_id, doc_embedding in self.document_embeddings.items():
            # Skip the source document itself
            if doc_id == document_id:
                continue

            similarity = util.cos_sim(source_embedding, doc_embedding).item()

            # Only include if above minimum score
            if similarity >= min_score:
                similarities.append((doc_id, similarity))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        results = similarities[:top_k]

        logger.info(f"Found {len(results)} similar documents")
        return results

    def remove_document(self, document_id: int) -> bool:
        """
        Remove a document from the index.
        
        Args:
            document_id: Document ID to remove
            
        Returns:
            bool: True if document was removed, False if not found
        """
        if document_id in self.document_embeddings:
            del self.document_embeddings[document_id]
            del self.document_metadata[document_id]
            logger.debug(f"Removed document {document_id} from index")
            return True

        return False

    def clear_index(self) -> None:
        """Clear all indexed documents."""
        self.document_embeddings.clear()
        self.document_metadata.clear()
        logger.info("Cleared all indexed documents")

    def get_index_size(self) -> int:
        """
        Get number of indexed documents.
        
        Returns:
            int: Number of documents in index
        """
        return len(self.document_embeddings)

    def save_index(self, filepath: str) -> None:
        """
        Save index to disk.
        
        Args:
            filepath: Path to save index
        """
        logger.info(f"Saving index to {filepath}")

        index_data = {
            "model_name": self.model_name,
            "embeddings": {
                str(k): v.cpu().numpy() for k, v in self.document_embeddings.items()
            },
            "metadata": self.document_metadata,
        }

        torch.save(index_data, filepath)
        logger.info("Index saved successfully")

    def load_index(self, filepath: str) -> None:
        """
        Load index from disk.
        
        Args:
            filepath: Path to load index from
        """
        logger.info(f"Loading index from {filepath}")

        index_data = torch.load(filepath)

        # Verify model compatibility
        if index_data.get("model_name") != self.model_name:
            logger.warning(
                f"Loaded index was created with model {index_data.get('model_name')}, "
                f"but current model is {self.model_name}",
            )

        # Load embeddings
        self.document_embeddings = {
            int(k): torch.from_numpy(v) for k, v in index_data["embeddings"].items()
        }

        # Load metadata
        self.document_metadata = index_data["metadata"]

        logger.info(f"Loaded {len(self.document_embeddings)} documents from index")

    def get_model_info(self) -> dict:
        """
        Get information about the model and index.
        
        Returns:
            dict: Model and index information
        """
        return {
            "model_name": self.model_name,
            "indexed_documents": len(self.document_embeddings),
            "embedding_dimension": (
                self.model.get_sentence_embedding_dimension()
            ),
        }
