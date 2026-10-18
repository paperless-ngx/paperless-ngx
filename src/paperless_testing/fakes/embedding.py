"""A deterministic stand-in for an embedding model."""

from __future__ import annotations

import re

from llama_index.core.base.embeddings.base import BaseEmbedding

# Each concept is one embedding dimension, so words within a concept count
# as synonyms: "vacation" embeds close to "holiday" while sharing no keyword.
_CONCEPTS: tuple[frozenset[str], ...] = (
    frozenset({"holiday", "vacation", "trip"}),
    frozenset({"car", "automobile", "vehicle"}),
    frozenset({"invoice", "bill", "payment"}),
    frozenset({"insurance", "policy", "coverage"}),
)


def _embed(text: str) -> list[float]:
    words = re.findall(r"\w+", text.lower())
    vector = [float(sum(word in concept for word in words)) for concept in _CONCEPTS]
    # A small constant dimension keeps the vector non-zero for text naming no
    # concept, which sqlite-vec cannot compute a cosine distance for.
    return [*vector, 0.01]


class ConceptEmbedding(BaseEmbedding):
    """Embeds text by counting words per concept (see _CONCEPTS), so cosine
    similarity tracks shared concepts and tests can predict a semantic
    ranking without a real model.
    """

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return _embed(query)

    def _get_query_embedding(self, query: str) -> list[float]:
        return _embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return _embed(text)
