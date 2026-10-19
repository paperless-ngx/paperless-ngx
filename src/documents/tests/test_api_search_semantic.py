"""The opt-in ``semantic`` mode of the search endpoints: semantic (LLM index)
results merged into simple text search, scoped by the same permissions as
keyword search, and a clean fallback to keyword search when unavailable.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework import status

from documents.models import Document
from documents.models import DocumentType
from documents.search import get_backend
from paperless_ai import indexing
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory
from paperless_testing.fakes.embedding import ConceptEmbedding
from paperless_testing.permissions import grant_global

if TYPE_CHECKING:
    from pathlib import Path

    import pytest_mock
    from django.contrib.auth.models import User
    from pytest_django.fixtures import Settings
    from rest_framework.test import APIClient

    from paperless_testing.dirs import PaperlessDirs

pytestmark = [pytest.mark.django_db, pytest.mark.search]


class FailingEmbedding(ConceptEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        raise ConnectionError("embedding backend unreachable")


@pytest.fixture
def llm_index(
    paperless_dirs: PaperlessDirs,
    settings: Settings,
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    settings.AI_ENABLED = True
    settings.LLM_EMBEDDING_BACKEND = "ollama"
    settings.LLM_INDEX_DIR = tmp_path / "llm_index"
    settings.LLM_INDEX_LOCK = settings.LLM_INDEX_DIR / "index.lock"
    settings.LLM_INDEX_RWLOCK = settings.LLM_INDEX_DIR / "llmindex.rwlock.db"
    mocker.patch(
        "paperless_ai.indexing.get_embedding_model",
        return_value=ConceptEmbedding(),
    )


@pytest.fixture
def owner(db: None) -> User:
    return UserFactory(username="owner")


@pytest.fixture
def library(llm_index: None, owner: User) -> dict[str, Document]:
    """Documents for the query "holiday": a keyword-only match, a semantic-only
    match (a synonym), a match on both, an unrelated document, and a
    semantic-only match owned by a user the regular user can't see.
    """
    docs = {
        "keyword": DocumentFactory.create(
            title="Packing list",
            content="the holiday checklist",
            created=datetime.date(2024, 1, 1),
        ),
        "semantic": DocumentFactory.create(
            title="Spain",
            content="photos of our vacation in spain",
            created=datetime.date(2020, 1, 1),
        ),
        "both": DocumentFactory.create(
            title="Holiday booking",
            content="holiday trip booking confirmation",
            created=datetime.date(2022, 1, 1),
        ),
        "unrelated": DocumentFactory.create(
            title="Garage",
            content="automobile repair at the garage",
            created=datetime.date(2023, 1, 1),
        ),
        "private": DocumentFactory.create(
            title="Private",
            content="secret vacation trip plans",
            created=datetime.date(2021, 1, 1),
            owner=owner,
        ),
    }
    backend = get_backend()
    for doc in docs.values():
        backend.add_or_update(doc)
    indexing.update_llm_index(rebuild=True)
    return docs


@pytest.fixture
def viewer_client(user_client: APIClient, regular_user: User) -> APIClient:
    grant_global(regular_user, "view_document")
    return user_client


def _result_ids(response) -> list[int]:
    assert response.status_code == status.HTTP_200_OK, response.data
    return [doc["id"] for doc in response.data["results"]]


def _global_search_ids(response) -> list[int]:
    assert response.status_code == status.HTTP_200_OK, response.data
    return [doc["id"] for doc in response.data["documents"]]


def _semantic_ids(response) -> list[int]:
    assert response.status_code == status.HTTP_200_OK, response.data
    return [doc["id"] for doc in response.data["semantic_documents"]]


class TestSemanticDocumentSearch:
    def test_keyword_search_by_default(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        ids = _result_ids(admin_client.get("/api/documents/?text=holiday"))

        assert set(ids) == {library["keyword"].pk, library["both"].pk}

    def test_semantic_merges_semantic_matches(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        """
        GIVEN:
            - Documents matching "holiday" by keyword, by meaning, or both
        WHEN:
            - Searching with semantic=true
        THEN:
            - Semantic matches are added below the keyword matches
            - Documents too dissimilar to the query are not added
            - The best hit scores 1.0
        """
        response = admin_client.get("/api/documents/?text=holiday&semantic=true")
        ids = _result_ids(response)

        # Keyword matches first, then the semantic-only ones; the unrelated
        # document is below the minimum similarity
        assert set(ids[:2]) == {library["keyword"].pk, library["both"].pk}
        assert set(ids[2:]) == {library["semantic"].pk, library["private"].pk}
        assert response.data["count"] == 4
        hits = [doc["__search_hit__"] for doc in response.data["results"]]
        assert hits[0]["score"] == 1.0
        assert [hit["rank"] for hit in hits] == list(range(1, len(hits) + 1))
        # Keyword matches keep their highlights
        assert "holiday" in hits[0]["highlights"]

    def test_semantic_respects_permissions(
        self,
        viewer_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        """
        GIVEN:
            - A document the user can't view that matches the query by meaning
        WHEN:
            - The user searches with semantic=true
        THEN:
            - The document is never returned, nor counted
        """
        response = viewer_client.get("/api/documents/?text=holiday&semantic=true")
        ids = _result_ids(response)

        assert library["private"].pk not in ids
        assert library["semantic"].pk in ids
        assert response.data["count"] == len(ids)

    def test_semantic_respects_other_filters(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        doc_type = DocumentType.objects.create(name="Photos")
        library["semantic"].document_type = doc_type
        library["semantic"].save()

        ids = _result_ids(
            admin_client.get(
                f"/api/documents/?text=holiday&semantic=true&document_type__id={doc_type.pk}",
            ),
        )

        assert ids == [library["semantic"].pk]

    def test_semantic_with_filter_query(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        """
        GIVEN:
            - A text search combined with an advanced filter query
        WHEN:
            - Searching with semantic=true
        THEN:
            - Semantic matches must also match the filter query
        """
        ids = _result_ids(
            admin_client.get(
                "/api/documents/?text=holiday&semantic=true"
                "&query=created:[2019-01-01 to 2020-12-31]",
            ),
        )

        assert ids == [library["semantic"].pk]

    def test_semantic_with_field_ordering(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        response = admin_client.get(
            "/api/documents/?text=holiday&semantic=true&ordering=-created",
        )
        ids = _result_ids(response)

        created = {doc["id"]: doc["created"] for doc in response.data["results"]}
        assert library["semantic"].pk in ids
        assert [created[doc_id] for doc_id in ids] == sorted(
            created.values(),
            reverse=True,
        )

    def test_semantic_with_ascending_score_ordering(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        relevance_ids = _result_ids(
            admin_client.get("/api/documents/?text=holiday&semantic=true"),
        )
        ids = _result_ids(
            admin_client.get(
                "/api/documents/?text=holiday&semantic=true&ordering=score",
            ),
        )

        assert ids == list(reversed(relevance_ids))

    def test_semantic_ignored_for_advanced_query(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        ids = _result_ids(
            admin_client.get("/api/documents/?query=holiday&semantic=true"),
        )

        assert set(ids) == {library["keyword"].pk, library["both"].pk}

    def test_semantic_falls_back_when_llm_index_disabled(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
        settings: Settings,
    ) -> None:
        settings.AI_ENABLED = False

        ids = _result_ids(
            admin_client.get("/api/documents/?text=holiday&semantic=true"),
        )

        assert set(ids) == {library["keyword"].pk, library["both"].pk}

    def test_semantic_falls_back_when_index_missing(
        self,
        admin_client: APIClient,
        llm_index: None,
    ) -> None:
        doc = DocumentFactory.create(content="the holiday checklist")
        get_backend().add_or_update(doc)

        ids = _result_ids(
            admin_client.get("/api/documents/?text=holiday&semantic=true"),
        )

        assert ids == [doc.pk]

    def test_semantic_falls_back_when_embedding_fails(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "paperless_ai.indexing.get_embedding_model",
            return_value=FailingEmbedding(),
        )

        ids = _result_ids(
            admin_client.get("/api/documents/?text=holiday&semantic=true"),
        )

        assert set(ids) == {library["keyword"].pk, library["both"].pk}

    def test_bulk_edit_select_all_matches_semantic_results(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A semantic search result list
        WHEN:
            - Bulk editing with all=true and the same filters
        THEN:
            - The edit applies to exactly the listed documents
        """
        listed = _result_ids(
            admin_client.get("/api/documents/?text=holiday&semantic=true"),
        )
        set_document_type = mocker.patch(
            "documents.serialisers.bulk_edit.set_document_type",
            return_value="OK",
        )
        set_document_type.__name__ = "set_document_type"

        response = admin_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [],
                "all": True,
                "filters": {"text": "holiday", "semantic": True},
                "method": "set_document_type",
                "parameters": {"document_type": None},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        set_document_type.assert_called_once()
        assert sorted(set_document_type.call_args.args[0]) == sorted(listed)


class TestSemanticGlobalSearch:
    def test_keyword_search_by_default(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        response = admin_client.get("/api/search/?query=holiday")

        assert set(_global_search_ids(response)) == {
            library["keyword"].pk,
            library["both"].pk,
        }
        assert response.data["semantic_documents"] == []

    def test_semantic_matches_listed_apart(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        """
        GIVEN:
            - Documents matching "holiday" by keyword, by meaning, or both
        WHEN:
            - Searching globally with semantic=true
        THEN:
            - The documents list keeps only the keyword matches
            - The semantic-only matches are listed apart, without
              repeating a keyword match or anything below the min score
        """
        response = admin_client.get("/api/search/?query=holiday&semantic=true")

        assert set(_global_search_ids(response)) == {
            library["keyword"].pk,
            library["both"].pk,
        }
        assert set(_semantic_ids(response)) == {
            library["semantic"].pk,
            library["private"].pk,
        }
        assert response.data["total"] == 4

    def test_semantic_respects_permissions(
        self,
        viewer_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        response = viewer_client.get("/api/search/?query=holiday&semantic=true")

        assert _semantic_ids(response) == [library["semantic"].pk]

    def test_semantic_limited_to_five(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        for content in ("vacation photos", "trip receipts", "vacation rental", "trip"):
            DocumentFactory.create(content=content)
        indexing.update_llm_index(rebuild=True)

        response = admin_client.get("/api/search/?query=holiday&semantic=true")

        assert len(_semantic_ids(response)) == 5

    def test_semantic_ignored_for_db_only(
        self,
        admin_client: APIClient,
        library: dict[str, Document],
    ) -> None:
        response = admin_client.get(
            "/api/search/?query=holiday&semantic=true&db_only=true",
        )

        assert _global_search_ids(response) == [library["both"].pk]
        assert response.data["semantic_documents"] == []
