"""The search list endpoint's exception handling: what becomes a 400 and
what a library defect surfaces as instead.

Companion to documents/tests/search/test_error_routing.py, which pins the
Cause -> SearchQueryError/QueryError routing inside documents/search/_query.py.
These tests pin the layer above it: DocumentViewSet.list's own except clauses,
which decide what an already-routed error becomes on the wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from whoosh_compat.errors import Cause
from whoosh_compat.errors import Diagnostic
from whoosh_compat.errors import DiagnosticKind
from whoosh_compat.errors import QueryError

from documents.search import SearchQueryError
from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from documents.models import Document

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_search_index")]


@pytest.fixture
def indexed_document() -> Document:
    from documents.search import get_backend

    doc = DocumentFactory.create(title="quarterly invoice", content="acme corp")
    get_backend().add_or_update(doc)
    return doc


class TestSearchQueryErrorStillBecomesA400:
    def test_search_query_error_becomes_a_400_naming_the_field(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_search_query_error(*args: object, **kwargs: object) -> object:
            raise SearchQueryError("bad value for field 'added'")

        monkeypatch.setattr(
            backend_mod,
            "parse_user_query",
            raise_search_query_error,
        )

        response = admin_client.get("/api/documents/?query=anything")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "added" in str(response.data["query"])


class TestLibraryDefectsPropagate:
    """The exact regression this task exists to fix: an unexpected or
    INTERNAL-cause library error must not be relabeled a 400."""

    def test_unexpected_exception_is_not_converted_to_a_400(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_zero_division(*args: object, **kwargs: object) -> object:
            raise ZeroDivisionError("synthetic bug, unrelated to search grammar")

        monkeypatch.setattr(
            backend_mod,
            "parse_user_query",
            raise_zero_division,
        )

        with pytest.raises(ZeroDivisionError):
            admin_client.get("/api/documents/?query=anything")

    def test_internal_cause_query_error_is_not_converted_to_a_400(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        """Forces the one library-internal failure mode reachable from a real
        query: emit() reporting a defect in itself (Cause.INTERNAL) after a
        real query string went through the real parse and routing pipeline.

        ``tantivy_emit`` (the whoosh-compat emitter) is monkeypatched rather
        than ``parse_user_query`` itself, so everything upstream of it --
        the pre-parse rewrites, ``wc.parse()``, and ``_map_emit_error``'s own
        Cause routing in documents/search/_query.py -- runs for real; only
        the final emit call is forced to report the defect.
        """
        import documents.search._query as query_mod

        def raise_internal(*args: object, **kwargs: object) -> object:
            raise QueryError(
                Diagnostic(
                    kind=DiagnosticKind.BACKEND_REJECTED,
                    cause=Cause.INTERNAL,
                    message="synthetic whoosh-compat emitter defect",
                ),
            )

        monkeypatch.setattr(query_mod, "tantivy_emit", raise_internal)

        with pytest.raises(QueryError):
            admin_client.get("/api/documents/?query=invoice")


class TestSelectionPathsAgreeWithSearch:
    """DocumentSelectionMixin backs bulk edit, bulk download, and a
    more_like_id selection filter. It catches only SearchQueryError -- the
    same contract the search list endpoint enforces above -- so all three
    must map SearchQueryError to a 400 and let anything else surface."""

    def test_bulk_edit_maps_search_query_error_to_a_400(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_search_query_error(*args: object, **kwargs: object) -> object:
            raise SearchQueryError("bad value for field 'added'")

        monkeypatch.setattr(
            backend_mod,
            "parse_user_query",
            raise_search_query_error,
        )

        response = admin_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": "anything"},
                "method": "set_document_type",
                "parameters": {"document_type": None},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "added" in str(response.data["query"])

    def test_bulk_edit_lets_an_unexpected_exception_surface(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_zero_division(*args: object, **kwargs: object) -> object:
            raise ZeroDivisionError("synthetic bug, unrelated to search grammar")

        monkeypatch.setattr(
            backend_mod,
            "parse_user_query",
            raise_zero_division,
        )

        with pytest.raises(ZeroDivisionError):
            admin_client.post(
                "/api/documents/bulk_edit/",
                {
                    "documents": [],
                    "all": True,
                    "filters": {"query": "anything"},
                    "method": "set_document_type",
                    "parameters": {"document_type": None},
                },
                format="json",
            )

    def test_bulk_download_maps_search_query_error_to_a_400(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_search_query_error(*args: object, **kwargs: object) -> object:
            raise SearchQueryError("bad value for field 'added'")

        monkeypatch.setattr(
            backend_mod,
            "parse_user_query",
            raise_search_query_error,
        )

        response = admin_client.post(
            "/api/documents/bulk_download/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": "anything"},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "added" in str(response.data["query"])

    def test_more_like_id_selection_filter_maps_search_query_error_to_a_400(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_search_query_error(*args: object, **kwargs: object) -> object:
            raise SearchQueryError("similar-document lookup is unavailable")

        monkeypatch.setattr(
            backend_mod.TantivyBackend,
            "more_like_this_ids",
            raise_search_query_error,
        )

        response = admin_client.post(
            "/api/documents/bulk_download/",
            {
                "documents": [],
                "all": True,
                "filters": {"more_like_id": indexed_document.pk},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_more_like_id_selection_filter_lets_an_unexpected_exception_surface(
        self,
        admin_client: APIClient,
        monkeypatch: pytest.MonkeyPatch,
        indexed_document: Document,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_zero_division(*args: object, **kwargs: object) -> object:
            raise ZeroDivisionError("synthetic bug, unrelated to similarity lookup")

        monkeypatch.setattr(
            backend_mod.TantivyBackend,
            "more_like_this_ids",
            raise_zero_division,
        )

        with pytest.raises(ZeroDivisionError):
            admin_client.post(
                "/api/documents/bulk_download/",
                {
                    "documents": [],
                    "all": True,
                    "filters": {"more_like_id": indexed_document.pk},
                },
                format="json",
            )
