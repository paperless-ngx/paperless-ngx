"""Regression coverage for the unguarded TEXT-mode highlight query.

parse_simple_text_highlight_query re-parses simple-search tokens through
Tantivy's query-string parser to build a SnippetGenerator-compatible query.
Simple-search tokens keep arbitrary punctuation (quotes, colons, brackets,
slashes), so any token carrying Tantivy query grammar raised an unguarded
ValueError. The search itself had already succeeded by the time this ran:
only the highlight step failed, and with the DocumentViewSet.list
exception handler narrowed elsewhere on this branch, that ValueError now
reaches the client as a bare 500 rather than a 400.

Covers three angles:
  - the query builder itself: quoting each token as its own escaped phrase
    should let it parse instead of raising, for every failure mode a plain-
    text query can trigger (syntax error, unknown field, unsupported regex).
  - highlight_hits: even when a token still can't be expressed as a
    highlight query, the guard must fall back to a query that still
    produces usable highlight HTML, not silently empty ones.
  - the real API endpoint: pinning the previously-500 status to 200.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tantivy
from rest_framework import status

from documents.search._backend import SearchMode
from documents.search._query import parse_simple_text_highlight_query
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers
from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

# Each spelling below trips a different Tantivy parser failure mode:
#   'a"b'     -> Syntax Error (unterminated quote)
#   foo:bar   -> unknown field
#   (a        -> Syntax Error (unbalanced group)
#   [a        -> Syntax Error (unbalanced range)
#   /a/       -> Unsupported query (regex queries disallowed)
_MALFORMED_QUERIES = [
    pytest.param('a"b', id="unterminated_quote"),
    pytest.param("foo:bar", id="unknown_field"),
    pytest.param("(a", id="unbalanced_group"),
    pytest.param("[a", id="unbalanced_range"),
    pytest.param("/a/", id="unsupported_regex"),
]


@pytest.fixture(scope="module")
def query_index() -> tantivy.Index:
    """An in-memory, unstemmed index for parse-only tests."""
    schema = build_schema()
    idx = tantivy.Index(schema, path=None)
    register_tokenizers(idx, "")
    return idx


class TestParseSimpleTextHighlightQueryDoesNotRaise:
    """The query builder itself must tolerate Tantivy syntax in its tokens."""

    @pytest.mark.parametrize("raw_query", _MALFORMED_QUERIES)
    def test_malformed_token_does_not_raise(
        self,
        query_index: tantivy.Index,
        raw_query: str,
    ) -> None:
        assert isinstance(
            parse_simple_text_highlight_query(query_index, raw_query),
            tantivy.Query,
        )


class TestHighlightHitsProducesUsableHighlights:
    """highlight_hits must keep producing real <b>-wrapped snippet HTML for
    these queries, not merely avoid raising."""

    @pytest.mark.parametrize(
        "raw_query",
        [*_MALFORMED_QUERIES, pytest.param("plain text", id="plain_text_sanity")],
    )
    def test_highlight_still_contains_matched_text(
        self,
        backend: TantivyBackend,
        raw_query: str,
    ) -> None:
        doc = DocumentFactory.create(
            title="probe",
            content=f"needle content containing {raw_query} literally here",
        )
        backend.add_or_update(doc)

        hits = backend.highlight_hits(
            raw_query,
            [doc.pk],
            search_mode=SearchMode.TEXT,
        )

        assert len(hits) == 1
        highlights = hits[0]["highlights"]
        assert "content" in highlights, (
            f"Expected a content highlight for {raw_query!r}, got: {highlights!r}"
        )
        assert "<b>" in highlights["content"], (
            f"Highlight for {raw_query!r} carries no matched-term markup: "
            f"{highlights['content']!r}"
        )


class TestHighlightGuardDiscriminatesOnValueError:
    """The guard added to highlight_hits must catch exactly ValueError, the
    same shape as the sibling notes_text guard, and let anything else
    through -- so a real library defect is never mistaken for a harmless
    syntax error."""

    def test_non_value_error_is_not_swallowed(
        self,
        backend: TantivyBackend,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import documents.search._backend as backend_mod

        def raise_runtime_error(*args: object, **kwargs: object) -> object:
            raise RuntimeError("synthetic bug, unrelated to query syntax")

        monkeypatch.setattr(
            backend_mod,
            "parse_simple_text_highlight_query",
            raise_runtime_error,
        )

        doc = DocumentFactory.create(title="probe", content="anything here")
        backend.add_or_update(doc)

        with pytest.raises(RuntimeError):
            backend.highlight_hits(
                "anything",
                [doc.pk],
                search_mode=SearchMode.TEXT,
            )


@pytest.mark.usefixtures("_search_index")
class TestApiNoLongerReturns500:
    """Pins the actual regression: a matching TEXT-mode search whose query
    string carries Tantivy syntax must return results, not a server error."""

    @pytest.mark.parametrize("raw_query", _MALFORMED_QUERIES)
    def test_malformed_text_query_returns_200(
        self,
        admin_client: APIClient,
        raw_query: str,
    ) -> None:
        from documents.search import get_backend

        doc = DocumentFactory.create(
            title="probe",
            content=f"needle content containing {raw_query} literally here",
        )
        get_backend().add_or_update(doc)

        response = admin_client.get(f"/api/documents/?text={raw_query}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_plain_text_query_still_returns_200(
        self,
        admin_client: APIClient,
    ) -> None:
        """Sanity check: the guard must not mask a total failure of the
        ordinary highlight path."""
        from documents.search import get_backend

        doc = DocumentFactory.create(
            title="probe",
            content="needle content containing plain text literally here",
        )
        get_backend().add_or_update(doc)

        response = admin_client.get("/api/documents/?text=plain text")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
