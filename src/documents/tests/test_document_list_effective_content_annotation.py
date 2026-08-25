from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from documents.tests.factories import DocumentFactory
from documents.views import DocumentViewSet

if TYPE_CHECKING:
    from rest_framework.test import APIClient


class TestNeedsEffectiveContentAnnotation:
    """
    DocumentViewSet._needs_effective_content_annotation() decides whether
    the effective_content correlated subquery is worth attaching to the
    queryset at all -- see TestDocumentListEffectiveContentAnnotation below
    for why. This only checks that decision's own logic (a plain query-param
    membership test), not that Django/DRF's filtering machinery works.
    """

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({}, False),
            ({"ordering": "-added"}, False),
            ({"tags__id__in": "1,2"}, False),
            ({"search": "foo"}, True),
            ({"title_content": "foo"}, True),
            ({"content__istartswith": "foo"}, True),
            ({"content__iendswith": "foo"}, True),
            ({"content__icontains": "foo"}, True),
            ({"content__iexact": "foo"}, True),
        ],
    )
    def test_detects_content_filter_params(
        self,
        params: dict[str, str],
        expected: bool,  # noqa: FBT001
    ) -> None:
        # GIVEN a view bound to a request carrying the given query params
        view = DocumentViewSet()
        view.request = SimpleNamespace(query_params=params)

        # WHEN checking whether the effective_content annotation is needed
        # THEN it's needed only for requests that actually filter on it
        assert view._needs_effective_content_annotation() is expected


@pytest.mark.django_db
class TestDocumentListEffectiveContentAnnotation:
    """
    DocumentViewSet.get_queryset() only attaches the effective_content
    correlated subquery when a request actually filters on it. Attaching it
    unconditionally re-executes it once per candidate row before the page's
    LIMIT is applied -- fine on SQLite/Postgres, but pathological on
    MariaDB's default cardinality estimation for the root_document_id
    self-join once candidate counts get large (see the root_document_id /
    effective_content perf investigation).
    """

    def test_list_without_content_filter_skips_annotation_but_returns_latest_content(
        self,
        admin_client: APIClient,
    ) -> None:
        # GIVEN a root document whose latest version has different content
        root = DocumentFactory(content="old-root-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="new-version-content",
        )

        # WHEN listing documents with no search/content-filter param
        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get("/api/documents/?fields=id,content")

        # THEN the response still reflects the latest version's content...
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {"id": root.id, "content": "new-version-content"},
        ]
        # ...without the database ever evaluating effective_content per row
        assert not any(
            "effective_content" in query["sql"] for query in ctx.captured_queries
        )
