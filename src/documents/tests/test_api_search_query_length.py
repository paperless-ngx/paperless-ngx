"""The query-length cap in ``_get_tantivy_query_and_mode``.

whoosh-compat's fieldname tagger is O(n^2) in plain word characters, so an
unbounded ``query`` (SearchMode.QUERY) string is a CPU-exhaustion vector
against a single request handler. The GET search endpoint is incidentally
bounded by the web server's header limit, but the POST selection-filter
path (bulk edit, bulk download) is not -- that is the real vector, so it
must be pinned here too, not just the GET path.

The cap is enforced once, in the shared helper both entry points call, so
these tests exercise the real endpoints rather than the helper directly:
a construct that looks right in isolation has repeatedly behaved
differently end to end on this branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from rest_framework import status

from documents.tests.factories import DocumentFactory
from documents.views import _MAX_QUERY_LENGTH

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


class TestGetSearchEndpointEnforcesTheCap:
    def test_query_one_over_the_cap_is_a_400(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The GET search endpoint
        WHEN:
            - A query one character over `_MAX_QUERY_LENGTH` is submitted
        THEN:
            - The response is a 400 naming both the actual length and the
              cap
        """
        query = "a" * (_MAX_QUERY_LENGTH + 1)

        response = admin_client.get("/api/documents/", {"query": query})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        message = str(response.data["query"])
        assert str(_MAX_QUERY_LENGTH) in message
        assert str(_MAX_QUERY_LENGTH + 1) in message

    def test_query_at_exactly_the_cap_is_accepted(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The GET search endpoint
        WHEN:
            - A query exactly `_MAX_QUERY_LENGTH` characters long is
              submitted
        THEN:
            - The response is a 200 (the cap is inclusive, not exclusive)
        """
        query = "a" * _MAX_QUERY_LENGTH

        response = admin_client.get("/api/documents/", {"query": query})

        assert response.status_code == status.HTTP_200_OK

    def test_an_ordinary_query_is_unaffected(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The GET search endpoint and an indexed document
        WHEN:
            - An ordinary, well-under-the-cap query is submitted
        THEN:
            - The cap has no effect on a normal search: the matching
              document is returned
        """
        response = admin_client.get("/api/documents/", {"query": "invoice"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1


class TestPostSelectionPathsEnforceTheCap:
    """The bulk-edit and bulk-download selection filters share the same
    helper the GET search path uses. This is the path that actually
    matters: it is not bounded by a web server's header-length limit the
    way the GET path incidentally is."""

    def test_bulk_edit_query_one_over_the_cap_is_a_400(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The bulk-edit selection-filter endpoint
        WHEN:
            - Its `filters.query` is one character over `_MAX_QUERY_LENGTH`
        THEN:
            - The response is a 400 naming both the actual length and the
              cap
        """
        query = "a" * (_MAX_QUERY_LENGTH + 1)

        response = admin_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": query},
                "method": "set_document_type",
                "parameters": {"document_type": None},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        message = str(response.data["query"])
        assert str(_MAX_QUERY_LENGTH) in message
        assert str(_MAX_QUERY_LENGTH + 1) in message

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_bulk_edit_query_at_exactly_the_cap_is_accepted(
        self,
        bulk_update_task_mock: mock.MagicMock,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The bulk-edit selection-filter endpoint
        WHEN:
            - Its `filters.query` is exactly `_MAX_QUERY_LENGTH` characters
              long
        THEN:
            - The cap check accepts it and the request reaches the real
              bulk-edit method (its Celery dispatch is mocked out here,
              same as every other bulk-edit test, since nothing here is
              testing that method itself)
        """
        query = "a" * _MAX_QUERY_LENGTH

        response = admin_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": query},
                "method": "set_document_type",
                "parameters": {"document_type": None},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_bulk_download_query_one_over_the_cap_is_a_400(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - The bulk-download selection-filter endpoint
        WHEN:
            - Its `filters.query` is one character over `_MAX_QUERY_LENGTH`
        THEN:
            - The response is a 400 naming both the actual length and the
              cap
        """
        query = "a" * (_MAX_QUERY_LENGTH + 1)

        response = admin_client.post(
            "/api/documents/bulk_download/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": query},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        message = str(response.data["query"])
        assert str(_MAX_QUERY_LENGTH) in message
        assert str(_MAX_QUERY_LENGTH + 1) in message


class TestGlobalSearchEnforcesTheCapToo:
    """GlobalSearchView calls the backend directly, not through the shared helper.

    It hardcodes SearchMode.TEXT, which is linear rather than quadratic, so it
    was never the CPU-exhaustion vector. It is capped anyway so that "every
    user query string reaching the backend passes a length check" is an
    invariant rather than a claim with an exception: the view already bounds
    the query from below, and a later change letting it select a mode would
    otherwise reopen the hole silently.
    """

    def test_query_one_over_the_cap_is_a_400(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - GlobalSearchView, which calls the backend directly in
              SearchMode.TEXT rather than through the shared cap-checking
              helper
        WHEN:
            - Its query is one character over `_MAX_QUERY_LENGTH`
        THEN:
            - The response is still a 400, keeping "every user query
              string reaching the backend passes a length check" an
              invariant with no exception, even though TEXT mode is
              linear and was never itself the CPU-exhaustion vector
        """
        response = admin_client.get(
            "/api/search/",
            {"query": "a" * (_MAX_QUERY_LENGTH + 1)},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_query_at_exactly_the_cap_is_accepted(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        """
        GIVEN:
            - GlobalSearchView
        WHEN:
            - Its query is exactly `_MAX_QUERY_LENGTH` characters long
        THEN:
            - The response is a 200 (the cap is inclusive, not exclusive)
        """
        response = admin_client.get(
            "/api/search/",
            {"query": "a" * _MAX_QUERY_LENGTH},
        )
        assert response.status_code == status.HTTP_200_OK
