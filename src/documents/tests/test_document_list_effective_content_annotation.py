from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from documents.models import Document
from documents.tests.factories import DocumentFactory
from documents.versioning import LATEST_VERSION_CONTENT_PREFETCH_ATTR
from documents.versioning import has_prefetched_effective_content
from documents.versioning import latest_version_content_prefetch
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
            ({"search": ""}, False),
            ({"search": "   "}, False),
            ({"content__icontains": ""}, False),
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

    def test_latest_version_content_prefetch_carries_only_the_newest_version(
        self,
    ) -> None:
        # GIVEN a root document with two versions
        root = DocumentFactory(content="root-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="older-version-content",
        )
        DocumentFactory(
            root_document=root,
            version_index=2,
            content="newest-version-content",
        )

        # WHEN fetching the root through latest_version_content_prefetch()
        fetched_root = (
            Document.objects.filter(pk=root.pk)
            .prefetch_related(
                latest_version_content_prefetch(),
            )
            .get()
        )

        # THEN the prefetch carries only the single newest version, not
        # every historical version's content (the whole point of not
        # reusing the metadata-only "versions" prefetch for this)
        latest = getattr(fetched_root, LATEST_VERSION_CONTENT_PREFETCH_ATTR)
        assert [v.content for v in latest] == ["newest-version-content"]


class TestHasPrefetchedEffectiveContent:
    """
    DocumentSerializer.to_representation() only calls get_effective_content()
    when has_prefetched_effective_content() says it's cheap -- otherwise a
    caller that never set up an annotation or prefetch (TrashView,
    GlobalSearchView, which build their own querysets and don't display
    content at all) would pay for a per-instance query nobody asked for.
    """

    def test_false_with_no_annotation_or_prefetch(self) -> None:
        document = Document()
        assert has_prefetched_effective_content(document) is False

    def test_true_with_effective_content_annotation(self) -> None:
        document = Document()
        document.effective_content = "resolved"
        assert has_prefetched_effective_content(document) is True

    def test_true_with_lean_prefetch_attr_even_when_empty(self) -> None:
        document = Document()
        setattr(document, LATEST_VERSION_CONTENT_PREFETCH_ATTR, [])
        assert has_prefetched_effective_content(document) is True

    def test_true_with_metadata_versions_prefetch_cache(self) -> None:
        document = Document()
        document._prefetched_objects_cache = {"versions": []}
        assert has_prefetched_effective_content(document) is True


def _get_effective_content_fallback_queries(
    ctx: CaptureQueriesContext,
) -> list[dict[str, str]]:
    """
    Document.get_effective_content()'s per-instance fallback (no annotation,
    no prefetch) is a `.values_list("content", flat=True).first()` query --
    a SELECT of just the content column. Distinct from get_versions()'s own,
    unrelated per-instance metadata query (id/checksum/added/etc, no
    content) run to build the "versions" response field, which isn't part
    of what this test file covers.
    """
    return [
        q
        for q in ctx.captured_queries
        if q["sql"].startswith('SELECT "documents_document"."content" FROM')
    ]


@pytest.mark.django_db
class TestTrashAndGlobalSearchDoNotResolveEffectiveContent:
    """
    TrashView and GlobalSearchView serialize Document instances with
    DocumentSerializer too, but build their querysets independently of
    DocumentViewSet.get_queryset() -- and neither actually displays
    document content. They should keep showing the document's own,
    unresolved content with no extra query, exactly as before
    effective_content resolution existed.
    """

    def test_trash_list_shows_unresolved_content_with_no_extra_query(
        self,
        admin_client: APIClient,
    ) -> None:
        # GIVEN a trashed root document whose own content differs from what
        # a (also trashed, since deletion cascades) version would have had
        root = DocumentFactory(content="own-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="version-content",
        )
        root.delete()

        # WHEN listing trash
        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get("/api/trash/")

        # THEN the response shows the document's own content...
        assert response.status_code == status.HTTP_200_OK
        [result] = [r for r in response.data["results"] if r["id"] == root.id]
        assert result["content"] == "own-content"
        # ...without ever querying for versions to resolve it
        assert _get_effective_content_fallback_queries(ctx) == []

    def test_global_search_db_only_shows_unresolved_content_with_no_extra_query(
        self,
        admin_client: APIClient,
    ) -> None:
        # GIVEN a root document, findable by title, whose own content
        # differs from its latest version's
        root = DocumentFactory(title="findme", content="own-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="version-content",
        )

        # WHEN using the global search endpoint's db_only mode
        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get(
                "/api/search/?query=findme&db_only=true",
            )

        # THEN the response shows the document's own content...
        assert response.status_code == status.HTTP_200_OK
        [result] = [d for d in response.data["documents"] if d["id"] == root.id]
        assert result["content"] == "own-content"
        # ...without ever querying for versions to resolve it
        assert _get_effective_content_fallback_queries(ctx) == []
