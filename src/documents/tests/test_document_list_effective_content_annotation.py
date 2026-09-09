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
        """
        GIVEN:
            - A view bound to a request carrying the given query params
        WHEN:
            - Checking whether the effective_content annotation is needed
        THEN:
            - It is needed only for requests that actually filter on it
        """
        view = DocumentViewSet()
        view.request = SimpleNamespace(query_params=params)

        assert view._needs_effective_content_annotation() is expected


class TestNeedsEffectiveContentPrefetch:
    """
    DocumentViewSet._needs_effective_content_prefetch() decides whether the
    single-version content prefetch is worth attaching. It has to read the
    `fields` param exactly the way get_serializer() does, or a request whose
    response includes content ends up without the prefetch and pays
    get_effective_content()'s per-instance fallback instead.
    """

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            pytest.param({}, True, id="no-fields-param-keeps-every-field"),
            pytest.param({"fields": ""}, True, id="blank-fields-keeps-every-field"),
            pytest.param(
                {"fields": "id,content"},
                True,
                id="content-among-requested-fields",
            ),
            pytest.param({"fields": "content"}, True, id="content-only"),
            pytest.param({"fields": "id"}, False, id="content-not-requested"),
            pytest.param(
                {"fields": "id,title"},
                False,
                id="several-fields-without-content",
            ),
        ],
    )
    def test_detects_whether_content_can_reach_the_response(
        self,
        params: dict[str, str],
        expected: bool,  # noqa: FBT001
    ) -> None:
        """
        GIVEN:
            - A view bound to a request carrying the given query params
        WHEN:
            - Checking whether the content prefetch is needed
        THEN:
            - It is needed exactly when get_serializer() would emit content,
              which treats a blank `fields` the same as an absent one
        """
        view = DocumentViewSet()
        view.request = SimpleNamespace(query_params=params)

        assert view._needs_effective_content_prefetch() is expected


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
        """
        GIVEN:
            - A root document whose latest version has different content
        WHEN:
            - Listing documents with no search/content-filter param
        THEN:
            - The response still reflects the latest version's content
            - The database never evaluates effective_content per row
        """
        root = DocumentFactory(content="old-root-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="new-version-content",
        )

        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get("/api/documents/?fields=id,content")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {"id": root.id, "content": "new-version-content"},
        ]
        assert not any(
            "effective_content" in query["sql"] for query in ctx.captured_queries
        )

    @pytest.mark.parametrize(
        "fields_param",
        [
            pytest.param("", id="blank-fields"),
            pytest.param("id,content", id="content-requested"),
        ],
    )
    def test_content_resolves_without_a_query_per_document(
        self,
        admin_client: APIClient,
        fields_param: str,
    ) -> None:
        """
        GIVEN:
            - One versioned root document, then two more
        WHEN:
            - Listing documents with a `fields` param that keeps content
        THEN:
            - Every root's content resolves to its latest version's
            - The query count does not grow with the number of documents,
              i.e. a blank `fields` does not skip the prefetch and fall back
              to loading each root's deferred version content
        """
        first = DocumentFactory(content="first-root-content")
        DocumentFactory(
            root_document=first,
            version_index=1,
            content="first-version-content",
        )

        with CaptureQueriesContext(connection) as one_document:
            response = admin_client.get(f"/api/documents/?fields={fields_param}")

        assert response.status_code == status.HTTP_200_OK
        assert [r["content"] for r in response.data["results"]] == [
            "first-version-content",
        ]

        for index in range(2):
            root = DocumentFactory(content=f"root-content-{index}")
            DocumentFactory(
                root_document=root,
                version_index=1,
                content=f"version-content-{index}",
            )
        with CaptureQueriesContext(connection) as three_documents:
            response = admin_client.get(f"/api/documents/?fields={fields_param}")

        assert response.status_code == status.HTTP_200_OK
        assert sorted(r["content"] for r in response.data["results"]) == [
            "first-version-content",
            "version-content-0",
            "version-content-1",
        ]
        assert len(three_documents.captured_queries) == len(
            one_document.captured_queries,
        )

    def test_list_without_content_field_skips_prefetch_and_omits_content(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A versioned root document
        WHEN:
            - Listing documents without asking for content
        THEN:
            - Content is neither serialized nor resolved
            - Nothing pays for the prefetch or the per-instance fallback
        """
        root = DocumentFactory(content="root-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="version-content",
        )

        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get("/api/documents/?fields=id")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [{"id": root.id}]
        assert _get_effective_content_fallback_queries(ctx) == []
        # Only the list query itself reads a content column: no extra query
        # for the skipped prefetch, none for a per-instance fallback
        content_queries = [
            query
            for query in ctx.captured_queries
            if '"documents_document"."content"' in query["sql"]
        ]
        assert len(content_queries) == 1

    def test_latest_version_content_prefetch_carries_only_the_newest_version(
        self,
    ) -> None:
        """
        GIVEN:
            - A root document with two versions
        WHEN:
            - Fetching the root through latest_version_content_prefetch()
        THEN:
            - The prefetch carries only the single newest version, not every
              historical version's content (the whole point of not reusing
              the metadata-only "versions" prefetch for this)
        """
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

        fetched_root = (
            Document.objects.filter(pk=root.pk)
            .prefetch_related(
                latest_version_content_prefetch(),
            )
            .get()
        )

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
        """
        GIVEN:
            - A document the ORM never annotated or prefetched for
        WHEN:
            - Asking whether its effective content is already resolved
        THEN:
            - It is not, so the serializer must leave it alone
        """
        document = DocumentFactory.build()

        assert has_prefetched_effective_content(document) is False

    def test_true_with_effective_content_annotation(self) -> None:
        """
        GIVEN:
            - A document carrying the queryset's effective_content annotation
        WHEN:
            - Asking whether its effective content is already resolved
        THEN:
            - It is, straight off the annotation
        """
        document = DocumentFactory.build()
        document.effective_content = "resolved"

        assert has_prefetched_effective_content(document) is True

    def test_true_with_lean_prefetch_attr_even_when_empty(self) -> None:
        """
        GIVEN:
            - A document the lean content prefetch ran for, finding no versions
        WHEN:
            - Asking whether its effective content is already resolved
        THEN:
            - It is: an empty prefetch is an answer, not a missing one
        """
        document = DocumentFactory.build()
        setattr(document, LATEST_VERSION_CONTENT_PREFETCH_ATTR, [])

        assert has_prefetched_effective_content(document) is True

    def test_true_with_metadata_versions_prefetch_cache(self) -> None:
        """
        GIVEN:
            - A document carrying only the metadata "versions" prefetch
        WHEN:
            - Asking whether its effective content is already resolved
        THEN:
            - It is, via get_effective_content()'s prefetch-cache branch
        """
        document = DocumentFactory.build()
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
class TestTrashAndGlobalSearchEffectiveContentIsNeverPerInstance:
    """
    TrashView and GlobalSearchView serialize Document instances with
    DocumentSerializer too, but build their querysets independently of
    DocumentViewSet.get_queryset(). TrashView doesn't display content at all,
    so it keeps the document's own unresolved content; GlobalSearchView
    annotates effective_content itself, so it shows the latest version's.
    Neither should ever fall back to a per-instance query.
    """

    def test_trash_list_shows_unresolved_content_with_no_extra_query(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A trashed root document whose own content differs from what a
              version would have had (also trashed, deletion cascades)
        WHEN:
            - Listing trash
        THEN:
            - The response shows the document's own content
            - Nothing ever queries for versions to resolve it
        """
        root = DocumentFactory(content="own-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="version-content",
        )
        root.delete()

        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get("/api/trash/")

        assert response.status_code == status.HTTP_200_OK
        [result] = [r for r in response.data["results"] if r["id"] == root.id]
        assert result["content"] == "own-content"
        assert _get_effective_content_fallback_queries(ctx) == []

    def test_global_search_db_only_shows_latest_version_content_with_no_extra_query(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A root document, findable by title, whose own content differs
              from its latest version's
        WHEN:
            - Using the global search endpoint's db_only mode
        THEN:
            - The response shows the latest version's content, resolved by
              GlobalSearchView's own effective_content annotation
            - There is no per-instance fallback query
        """
        root = DocumentFactory(title="findme", content="own-content")
        DocumentFactory(
            root_document=root,
            version_index=1,
            content="version-content",
        )

        with CaptureQueriesContext(connection) as ctx:
            response = admin_client.get(
                "/api/search/?query=findme&db_only=true",
            )

        assert response.status_code == status.HTTP_200_OK
        [result] = [d for d in response.data["documents"] if d["id"] == root.id]
        assert result["content"] == "version-content"
        assert _get_effective_content_fallback_queries(ctx) == []
