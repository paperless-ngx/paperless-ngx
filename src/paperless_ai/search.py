"""Semantic document search over the LLM vector index.

Backs the opt-in ``semantic`` mode of the document search endpoints: the
query is embedded and matched against the same index that powers document
chat and AI suggestions, and the result is merged with the Tantivy keyword
ranking via weighted reciprocal rank fusion.
"""

import logging
from collections.abc import Iterable
from collections.abc import Sequence

from django.db.models import QuerySet

from documents.models import Document
from paperless.config import AIConfig
from paperless_ai.db import db_connection_released
from paperless_ai.embedding import get_configured_model_name
from paperless_ai.indexing import document_id_filters
from paperless_ai.indexing import load_or_build_index
from paperless_ai.indexing import read_store
from paperless_ai.indexing import truncate_embedding_query

logger = logging.getLogger("paperless_ai.search")

# The most documents a semantic query contributes to a result list. Fewer
# are returned when not that many reach the configured minimum similarity
# (PAPERLESS_AI_LLM_SEMANTIC_SEARCH_MIN_SCORE).
SEMANTIC_SEARCH_MAX_DOCUMENTS = 25

# Chunks retrieved per query. A document is usually split into several
# chunks, so over-fetch to still fill SEMANTIC_SEARCH_MAX_DOCUMENTS once the
# chunks are collapsed to their documents.
_SEMANTIC_SEARCH_TOP_K = SEMANTIC_SEARCH_MAX_DOCUMENTS * 4

# The most visible document ids passed to the vector store as an IN filter.
# Above this the whole index is searched and the results post-filtered
# instead, well clear of the store's own bound-parameter guard
# (_MAX_IN_VALUES in paperless_ai/vector_store.py).
_VECTOR_FILTER_MAX_IDS = 10_000

# The k constant of reciprocal rank fusion, as proposed by Cormack et al.
# (2009). Larger values flatten the advantage of the top ranks.
RRF_K = 60

# Weights of the keyword and semantic rankings in hybrid_ranking(). With the
# semantic ranking at half the keyword weight, the best semantic-only match
# (0.5 / (RRF_K + 1)) never outranks a keyword match within the first
# RRF_K + 2 keyword results (1 / (RRF_K + rank)), so exact matches stay on
# top while semantic agreement still reorders them.
KEYWORD_WEIGHT = 1.0
SEMANTIC_WEIGHT = 0.5


def semantic_search_ids(
    query: str,
    documents: QuerySet[Document],
    *,
    limit: int = SEMANTIC_SEARCH_MAX_DOCUMENTS,
) -> list[int] | None:
    """Return the ids of the documents in ``documents`` most similar to
    ``query``, best first.

    ``documents`` scopes the search and must already be permission-filtered
    for the requesting user: no id outside it is ever returned. Documents
    less similar than ``PAPERLESS_AI_LLM_SEMANTIC_SEARCH_MIN_SCORE`` (cosine
    similarity of their best chunk) are left out.

    Returns None when semantic search is unavailable (the LLM index is
    disabled, not built yet, built with a different embedding model, or the
    embedding backend fails), so callers can fall back to keyword search.
    """
    config = AIConfig()
    if not config.llm_index_enabled:
        return None

    visible_ids = list(
        documents.order_by()
        .values_list("pk", flat=True)
        .distinct()[: _VECTOR_FILTER_MAX_IDS + 1],
    )
    if not visible_ids:
        return []
    filters = (
        document_id_filters(visible_ids)
        if len(visible_ids) <= _VECTOR_FILTER_MAX_IDS
        else None
    )

    from llama_index.core.retrievers import VectorIndexRetriever

    try:
        with read_store() as store:
            if not store.table_exists():
                logger.debug("Semantic search skipped: LLM index not built yet.")
                return None
            if store.config_mismatch(get_configured_model_name(config)):
                logger.warning(
                    "Semantic search skipped: the LLM index was built with a "
                    "different embedding model. Rebuild the index to enable it.",
                )
                return None
            index = load_or_build_index(config, store)
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=_SEMANTIC_SEARCH_TOP_K,
                filters=filters,
            )
            # The query embedding is a slow external request with no ORM
            # access during it; release the pooled DB connection. See #12976.
            with db_connection_released():
                nodes = retriever.retrieve(
                    truncate_embedding_query(
                        query,
                        chunk_size=config.llm_embedding_chunk_size,
                    ),
                )
    except Exception as e:
        logger.warning(
            "Semantic search failed, falling back to keyword search: %s",
            e,
        )
        return None

    # Nodes are chunks, best first: score each document by its best chunk
    best_scores: dict[int, float] = {}
    for node in nodes:
        try:
            document_id = int(node.metadata["document_id"])
        except (KeyError, TypeError, ValueError):  # pragma: no cover
            continue
        best_scores.setdefault(document_id, node.score or 0.0)
    min_score = config.llm_semantic_search_min_score
    candidate_ids = [
        doc_id for doc_id, score in best_scores.items() if score >= min_score
    ]
    logger.debug(
        "Semantic search kept %d of %d documents at min score %s: %s",
        len(candidate_ids),
        len(best_scores),
        min_score,
        ", ".join(f"{doc_id}={score:.3f}" for doc_id, score in best_scores.items()),
    )

    # Re-check against the caller's queryset: an unfiltered search over a
    # large library may return any indexed document, and permissions can
    # change between the ids being read and the search running.
    allowed_ids = set(
        documents.filter(pk__in=candidate_ids).values_list("pk", flat=True),
    )
    return [doc_id for doc_id in candidate_ids if doc_id in allowed_ids][:limit]


def hybrid_ranking(
    keyword_ids: Iterable[int],
    semantic_ids: Iterable[int],
) -> list[tuple[int, float]]:
    """Merge keyword and semantic search results, keyword matches weighted
    above semantic ones (see KEYWORD_WEIGHT and SEMANTIC_WEIGHT).
    """
    return reciprocal_rank_fusion(
        keyword_ids,
        semantic_ids,
        weights=(KEYWORD_WEIGHT, SEMANTIC_WEIGHT),
    )


def reciprocal_rank_fusion(
    *rankings: Iterable[int],
    weights: Sequence[float] | None = None,
    k: int = RRF_K,
) -> list[tuple[int, float]]:
    """Merge ranked id lists into one ranking via reciprocal rank fusion.

    Each id scores ``sum(weight / (k + rank))`` over the rankings it appears
    in, every weight 1.0 unless ``weights`` gives one per ranking. Returns
    ``(id, score)`` pairs best first, with scores normalised so the best is
    1.0. Ties keep the order the ids were first seen in, so earlier rankings
    win them.
    """
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("Expected one weight per ranking")
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    if not scores:
        return []
    best = max(scores.values())
    return [
        (doc_id, score / best)
        for doc_id, score in sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
