import logging
from pathlib import Path

import pytest
import pytest_mock
from pytest_django.fixtures import Settings

from documents.models import Document
from paperless_ai import indexing
from paperless_ai import search
from paperless_testing.factories import DocumentFactory
from paperless_testing.fakes.embedding import ConceptEmbedding


class FailingEmbedding(ConceptEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        raise ConnectionError("embedding backend unreachable")


@pytest.fixture
def llm_index_enabled(settings: Settings, temp_llm_index_dir: Path) -> None:
    settings.AI_ENABLED = True
    settings.LLM_EMBEDDING_BACKEND = "ollama"


@pytest.fixture
def no_min_score(settings: Settings) -> None:
    """Keep every neighbour, however distant, to test scoping on its own."""
    settings.LLM_SEMANTIC_SEARCH_MIN_SCORE = 0


@pytest.fixture
def concept_embedding(mocker: pytest_mock.MockerFixture) -> ConceptEmbedding:
    model = ConceptEmbedding()
    mocker.patch("paperless_ai.indexing.get_embedding_model", return_value=model)
    return model


@pytest.fixture
def library(db: None) -> dict[str, Document]:
    return {
        "holiday": DocumentFactory.create(content="photos of our vacation in spain"),
        "car": DocumentFactory.create(content="automobile repair at the garage"),
        "invoice": DocumentFactory.create(content="electricity bill for march"),
    }


@pytest.fixture
def indexed_library(
    llm_index_enabled: None,
    concept_embedding: ConceptEmbedding,
    library: dict[str, Document],
) -> dict[str, Document]:
    indexing.update_llm_index(rebuild=True)
    return library


@pytest.mark.django_db
class TestSemanticSearchIds:
    def test_ranks_documents_by_similarity(
        self,
        indexed_library: dict[str, Document],
    ) -> None:
        """
        GIVEN:
            - An LLM index of documents about different concepts
        WHEN:
            - Searching for a synonym of one document's concept
        THEN:
            - That document is found, although it shares no keyword
            - Documents about other concepts fall below the minimum score
        """
        ids = search.semantic_search_ids("holiday trip", Document.objects.all())

        assert ids == [indexed_library["holiday"].pk]

    def test_min_score_is_configurable(
        self,
        indexed_library: dict[str, Document],
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - An LLM index of documents about different concepts
        WHEN:
            - Searching with no minimum score, then with one above any match
        THEN:
            - Every document is returned best first, then none is
        """
        settings.LLM_SEMANTIC_SEARCH_MIN_SCORE = 0
        ids = search.semantic_search_ids("holiday trip", Document.objects.all())

        assert ids is not None
        assert ids[0] == indexed_library["holiday"].pk
        assert set(ids) == {doc.pk for doc in indexed_library.values()}

        settings.LLM_SEMANTIC_SEARCH_MIN_SCORE = 1
        assert search.semantic_search_ids("holiday trip", Document.objects.all()) == []

    def test_never_returns_documents_outside_queryset(
        self,
        indexed_library: dict[str, Document],
        no_min_score: None,
    ) -> None:
        """
        GIVEN:
            - An LLM index containing the best match for a query
        WHEN:
            - Searching within a queryset excluding that document
        THEN:
            - The document is not returned, the others still are
        """
        hidden = indexed_library["holiday"]

        ids = search.semantic_search_ids(
            "holiday trip",
            Document.objects.exclude(pk=hidden.pk),
        )

        assert ids is not None
        assert hidden.pk not in ids
        assert len(ids) == 2

    def test_post_filters_when_too_many_documents_for_vector_filter(
        self,
        indexed_library: dict[str, Document],
        no_min_score: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - A queryset larger than the vector store IN-filter limit
        WHEN:
            - Searching within it
        THEN:
            - The whole index is searched, and results outside the
              queryset are still dropped
        """
        monkeypatch.setattr(search, "_VECTOR_FILTER_MAX_IDS", 1)
        hidden = indexed_library["holiday"]

        ids = search.semantic_search_ids(
            "holiday trip",
            Document.objects.exclude(pk=hidden.pk),
        )

        assert ids is not None
        assert hidden.pk not in ids
        assert len(ids) == 2

    def test_respects_limit(
        self,
        indexed_library: dict[str, Document],
        no_min_score: None,
    ) -> None:
        ids = search.semantic_search_ids(
            "holiday trip",
            Document.objects.all(),
            limit=1,
        )

        assert ids == [indexed_library["holiday"].pk]

    def test_empty_queryset_returns_no_ids(
        self,
        indexed_library: dict[str, Document],
    ) -> None:
        assert search.semantic_search_ids("holiday", Document.objects.none()) == []

    def test_unavailable_when_llm_index_disabled(
        self,
        indexed_library: dict[str, Document],
        settings: Settings,
    ) -> None:
        settings.AI_ENABLED = False

        assert search.semantic_search_ids("holiday", Document.objects.all()) is None

    def test_unavailable_when_index_not_built(
        self,
        llm_index_enabled: None,
        concept_embedding: ConceptEmbedding,
        library: dict[str, Document],
    ) -> None:
        assert search.semantic_search_ids("holiday", Document.objects.all()) is None

    def test_unavailable_when_index_built_with_other_model(
        self,
        indexed_library: dict[str, Document],
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - An LLM index built with one embedding model
        WHEN:
            - The configured embedding model changes before a rebuild
        THEN:
            - Semantic search is unavailable rather than comparing
              embeddings of different models
        """
        settings.LLM_EMBEDDING_MODEL = "another-model"

        assert search.semantic_search_ids("holiday", Document.objects.all()) is None

    def test_unavailable_when_embedding_fails(
        self,
        indexed_library: dict[str, Document],
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A built LLM index
        WHEN:
            - The embedding backend fails to embed the query
        THEN:
            - Semantic search is unavailable instead of raising, and the
              failure is logged
        """
        mocker.patch(
            "paperless_ai.indexing.get_embedding_model",
            return_value=FailingEmbedding(),
        )

        with caplog.at_level(logging.WARNING, logger="paperless_ai.search"):
            ids = search.semantic_search_ids("holiday", Document.objects.all())

        assert ids is None
        assert "embedding backend unreachable" in caplog.text


@pytest.mark.django_db
class TestSemanticSearchEmbeddedMetadata:
    @pytest.fixture
    def titled_document(self, db: None) -> Document:
        # The title names the concept, the (garbled OCR) content does not
        return DocumentFactory.create(
            title="Vacation booking",
            content="xq7 vqcatlon b00king",
        )

    def test_title_found_only_with_embedded_metadata(
        self,
        llm_index_enabled: None,
        concept_embedding: ConceptEmbedding,
        titled_document: Document,
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - A document whose title, but not content, matches a query
        WHEN:
            - Indexing it without, then with, embedded metadata headers
        THEN:
            - Semantic search finds it only with the headers
        """
        indexing.update_llm_index(rebuild=True)
        assert search.semantic_search_ids("holiday", Document.objects.all()) == []

        settings.LLM_INDEX_EMBED_METADATA = True
        # Not rebuilt yet: the index no longer matches the configuration
        assert search.semantic_search_ids("holiday", Document.objects.all()) is None

        indexing.update_llm_index(rebuild=True)
        assert search.semantic_search_ids("holiday", Document.objects.all()) == [
            titled_document.pk,
        ]


class TestReciprocalRankFusion:
    def test_documents_in_both_rankings_rank_first(self) -> None:
        fused = search.reciprocal_rank_fusion([1, 2, 3], [3, 4])

        assert [doc_id for doc_id, _ in fused] == [3, 1, 2, 4]

    def test_scores_are_normalised_to_the_best(self) -> None:
        fused = search.reciprocal_rank_fusion([1, 2], k=60)

        assert fused == [(1, 1.0), (2, pytest.approx(61 / 62))]

    def test_ties_keep_earlier_ranking_first(self) -> None:
        fused = search.reciprocal_rank_fusion([1], [2])

        assert fused == [(1, 1.0), (2, 1.0)]

    def test_no_rankings(self) -> None:
        assert search.reciprocal_rank_fusion() == []
        assert search.reciprocal_rank_fusion([], []) == []

    def test_weights_scale_each_ranking(self) -> None:
        fused = search.reciprocal_rank_fusion([1], [2], weights=(1.0, 0.5))

        assert fused == [(1, 1.0), (2, pytest.approx(0.5))]

    def test_requires_one_weight_per_ranking(self) -> None:
        with pytest.raises(ValueError, match="one weight per ranking"):
            search.reciprocal_rank_fusion([1], [2], weights=(1.0,))


class TestHybridRanking:
    def test_keyword_matches_stay_above_semantic_only_matches(self) -> None:
        """
        GIVEN:
            - The first RRF_K + 2 keyword results and a different best
              semantic result
        WHEN:
            - Merging them
        THEN:
            - Every one of those keyword results ranks above the
              semantic-only result
        """
        keyword_ids = list(range(1, search.RRF_K + 3))

        fused_ids = [doc_id for doc_id, _ in search.hybrid_ranking(keyword_ids, [0])]

        assert fused_ids == [*keyword_ids, 0]

    def test_semantic_only_matches_outrank_weak_keyword_matches(self) -> None:
        keyword_ids = list(range(1, search.RRF_K + 4))

        fused_ids = [doc_id for doc_id, _ in search.hybrid_ranking(keyword_ids, [0])]

        assert fused_ids.index(0) == search.RRF_K + 2

    def test_semantic_agreement_reorders_keyword_matches(self) -> None:
        fused_ids = [doc_id for doc_id, _ in search.hybrid_ranking([1, 2, 3], [3])]

        assert fused_ids == [3, 1, 2]
