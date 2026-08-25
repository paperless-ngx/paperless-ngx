from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import tantivy
import time_machine

from documents.search._backend import build_permission_filter
from documents.search._errors import InvalidDateQuery
from documents.search._errors import InvalidNumberQuery
from documents.search._errors import MultipleSearchQueryErrors
from documents.search._errors import SearchQueryError
from documents.search._query import parse_simple_text_highlight_query
from documents.search._query import parse_user_query
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

pytestmark = pytest.mark.search


@pytest.fixture(scope="module")
def query_index() -> tantivy.Index:
    """An in-memory, unstemmed index shared read-only across this module's
    parse-only tests (none of them index documents)."""
    schema = build_schema()
    idx = tantivy.Index(schema, path=None)
    register_tokenizers(idx, "")
    return idx


@pytest.fixture(scope="module")
def populated_index() -> tantivy.Index:
    """An index holding one document, so a query matching nothing is
    distinguishable from one matching everything."""
    idx = tantivy.Index(build_schema(), path=None)
    register_tokenizers(idx, "")
    writer = idx.writer()
    doc = tantivy.Document()
    doc.add_unsigned("id", 1)
    doc.add_text("content", "needle in indexed content")
    writer.add_document(doc)
    writer.commit()
    idx.reload()
    return idx


def _highlight_hit_count(index: tantivy.Index, raw_query: str) -> int:
    query = parse_simple_text_highlight_query(index, raw_query)
    return index.searcher().search(query, limit=1).count


class TestParseUserQuery:
    """parse_user_query runs the full preprocessing pipeline."""

    def test_returns_tantivy_query(self, query_index: tantivy.Index) -> None:
        assert isinstance(parse_user_query(query_index, "invoice", UTC), tantivy.Query)

    @pytest.mark.parametrize(
        "raw_query",
        [
            pytest.param("invoice", id="plain_text"),
            pytest.param("created:today", id="date_keyword"),
            pytest.param("created:[2005 to 2009]", id="whoosh_date_range"),
            pytest.param('added:"previous month"', id="quoted_date_phrase"),
            pytest.param("title:202[0-1]*", id="bracket_class_wildcard"),
        ],
    )
    def test_fuzzy_mode_does_not_raise(
        self,
        query_index: tantivy.Index,
        settings,
        raw_query: str,
    ) -> None:
        # These are all valid whoosh grammar that tantivy's own query parser
        # (used only by the fuzzy blend clause) cannot parse; the fuzzy
        # clause must degrade gracefully instead of raising and failing the
        # whole query. See _try_parse_fuzzy_query.
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.5
        assert isinstance(parse_user_query(query_index, raw_query, UTC), tantivy.Query)

    def test_date_keyword_resolves_without_raising(
        self,
        query_index: tantivy.Index,
    ) -> None:
        # whoosh-compat's DateParserPlugin resolves "today" against the AST
        # directly (no string rewrite to an ISO range happens anywhere in
        # this pipeline); the emitted tantivy query must still build cleanly.
        with time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False):
            q = parse_user_query(query_index, "created:today", UTC)
        assert isinstance(q, tantivy.Query)

    @pytest.mark.parametrize(
        "raw_query",
        [
            pytest.param("h52.1 - kurzsichtigkeit", id="icd_code_dash_description"),
            pytest.param("H52.1 - asd", id="icd_code_uppercase"),
            pytest.param("h52.1 -", id="trailing_minus"),
            pytest.param(". -", id="dot_trailing_minus"),
            pytest.param("h52. -", id="partial_code_trailing_minus"),
            pytest.param(".12 -", id="dot_number_trailing_minus"),
            pytest.param("h52.1 - ku", id="partial_word_after_dash"),
        ],
    )
    def test_spaced_dash_queries_do_not_raise(
        self,
        query_index: tantivy.Index,
        raw_query: str,
    ) -> None:
        assert isinstance(parse_user_query(query_index, raw_query, UTC), tantivy.Query)

    def test_invalid_date_propagates_not_swallowed(
        self,
        query_index: tantivy.Index,
    ) -> None:
        # parse_user_query never falls back to the raw query string on a parse
        # error — a bad date diagnostic from whoosh-compat always maps to an
        # InvalidDateQuery and must propagate, so the view can return a 400
        # instead of silently parsing the raw (invalid) date.
        with pytest.raises(InvalidDateQuery) as exc_info:
            parse_user_query(query_index, "created:202023", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "202023"

    def test_invalid_number_raises_invalid_number_query(
        self,
        query_index: tantivy.Index,
    ) -> None:
        with pytest.raises(InvalidNumberQuery) as exc_info:
            parse_user_query(query_index, "asn:notanumber", UTC)
        assert exc_info.value.field == "asn"
        assert exc_info.value.value == "notanumber"

    def test_multiple_bad_fields_raise_multiple_search_query_errors(
        self,
        query_index: tantivy.Index,
    ) -> None:
        with pytest.raises(MultipleSearchQueryErrors) as exc_info:
            parse_user_query(
                query_index,
                "created:notadate AND asn:notanumber",
                UTC,
            )
        assert len(exc_info.value.errors) == 2
        kinds = {type(e) for e in exc_info.value.errors}
        assert kinds == {InvalidDateQuery, InvalidNumberQuery}

    def test_unregistered_id_field_folds_to_literal_text_not_error(
        self,
        query_index: tantivy.Index,
    ) -> None:
        # tag_id is intentionally excluded from the FieldRegistry — whoosh-compat
        # parity leniency folds it into literal text, not a diagnostic/400.
        # A result-level assertion that this fold actually matches nothing
        # against real documents lives in
        # test_acceptance.py::TestUnregisteredIdFieldFoldsToLiteralText.
        q = parse_user_query(query_index, "tag_id:5", UTC)
        assert isinstance(q, tantivy.Query)


class TestParseSimpleTextHighlightQuery:
    """parse_simple_text_highlight_query must not raise on natural-language queries."""

    @pytest.mark.parametrize(
        "raw_query",
        [
            pytest.param("h52.1 - kurzsichtigkeit", id="icd_code_dash_description"),
            pytest.param("H52.1 - asd", id="icd_code_uppercase"),
            pytest.param("h52.1 -", id="trailing_minus"),
            pytest.param(". -", id="dot_trailing_minus"),
            pytest.param(".12 -", id="dot_number_trailing_minus"),
            pytest.param("f84.0 - v.a. autismusspektrumstorung", id="complex_icd_dash"),
        ],
    )
    def test_spaced_dash_queries_do_not_raise(
        self,
        query_index: tantivy.Index,
        raw_query: str,
    ) -> None:
        assert isinstance(
            parse_simple_text_highlight_query(query_index, raw_query),
            tantivy.Query,
        )

    def test_a_real_token_matches_the_corpus(
        self,
        populated_index: tantivy.Index,
    ) -> None:
        """Without this, an empty corpus would make the two assertions below
        pass for a query that matches every document."""
        assert _highlight_hit_count(populated_index, "needle") == 1

    def test_empty_query_matches_no_document(
        self,
        populated_index: tantivy.Index,
    ) -> None:
        assert _highlight_hit_count(populated_index, "") == 0

    def test_all_operators_query_matches_no_document(
        self,
        populated_index: tantivy.Index,
    ) -> None:
        assert _highlight_hit_count(populated_index, "- +") == 0


class TestPermissionFilter:
    """
    build_permission_filter tests use an in-memory index - no DB access needed.

    Users are constructed as unsaved model instances (django_user_model(pk=N))
    so no database round-trip occurs; only .pk is read by build_permission_filter.
    """

    @pytest.fixture
    def perm_index(self) -> tantivy.Index:
        schema = build_schema()
        idx = tantivy.Index(schema, path=None)
        register_tokenizers(idx, "")
        return idx

    def _add_doc(
        self,
        idx: tantivy.Index,
        doc_id: int,
        owner_id: int | None = None,
        viewer_ids: tuple[int, ...] = (),
    ) -> None:
        writer = idx.writer()
        doc = tantivy.Document()
        doc.add_unsigned("id", doc_id)
        # Only add owner_id field if the document has an owner
        if owner_id is not None:
            doc.add_unsigned("owner_id", owner_id)
        for vid in viewer_ids:
            doc.add_unsigned("viewer_id", vid)
        writer.add_document(doc)
        writer.commit()
        idx.reload()

    def test_perm_no_owner_visible_to_any_user(
        self,
        perm_index: tantivy.Index,
        django_user_model: type[AbstractBaseUser],
    ) -> None:
        """Documents with no owner must be visible to every user."""
        self._add_doc(perm_index, doc_id=1, owner_id=None)
        user = django_user_model(pk=99)
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_owned_by_user_is_visible(
        self,
        perm_index: tantivy.Index,
        django_user_model: type[AbstractBaseUser],
    ) -> None:
        """A document owned by the requesting user must be visible."""
        self._add_doc(perm_index, doc_id=2, owner_id=42)
        user = django_user_model(pk=42)
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_owned_by_other_not_visible(
        self,
        perm_index: tantivy.Index,
        django_user_model: type[AbstractBaseUser],
    ) -> None:
        """A document owned by a different user must not be visible."""
        self._add_doc(perm_index, doc_id=3, owner_id=42)
        user = django_user_model(pk=99)
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 0

    def test_perm_shared_viewer_is_visible(
        self,
        perm_index: tantivy.Index,
        django_user_model: type[AbstractBaseUser],
    ) -> None:
        """A document explicitly shared with a user must be visible to that user."""
        self._add_doc(perm_index, doc_id=4, owner_id=42, viewer_ids=(99,))
        user = django_user_model(pk=99)
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_only_owned_docs_hidden_from_others(
        self,
        perm_index: tantivy.Index,
        django_user_model: type[AbstractBaseUser],
    ) -> None:
        """Only unowned documents appear when the user owns none of them."""
        self._add_doc(perm_index, doc_id=5, owner_id=10)  # owned by 10
        self._add_doc(perm_index, doc_id=6, owner_id=None)  # unowned
        user = django_user_model(pk=20)
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1  # only unowned


class TestSearchQueryErrors:
    def test_invalid_date_query_is_a_search_query_error(self) -> None:
        err = InvalidDateQuery("created", "notadate")
        assert isinstance(err, SearchQueryError)
        assert err.field == "created"
        assert err.value == "notadate"
        assert "created" in str(err)
        assert "notadate" in str(err)

    def test_invalid_number_query_is_a_search_query_error(self) -> None:
        err = InvalidNumberQuery("asn", "notanumber")
        assert isinstance(err, SearchQueryError)
        assert err.field == "asn"
        assert err.value == "notanumber"
        assert "asn" in str(err)
        assert "notanumber" in str(err)

    def test_multiple_search_query_errors_aggregates(self) -> None:
        sub_errors = [
            InvalidDateQuery("created", "notadate"),
            InvalidNumberQuery("asn", "notanumber"),
        ]
        err = MultipleSearchQueryErrors(sub_errors)
        assert isinstance(err, SearchQueryError)
        assert err.errors == tuple(sub_errors)
        assert "created" in str(err)
        assert "asn" in str(err)


class TestEmitErrorContract:
    """A QueryError from emit() surfaces as a SearchQueryError (HTTP 400).

    The Cause-based routing table itself is covered in test_error_routing.py.
    """

    def test_exists_requires_fast_gets_the_user_facing_rewrite(
        self,
        query_index: tantivy.Index,
    ) -> None:
        # whoosh-compat's own message advises a host-side fast=True config
        # change the user can't act on, so this checks OUR wording, not
        # whoosh-compat's (that's its own test suite's job now).
        with pytest.raises(SearchQueryError) as exc_info:
            parse_user_query(query_index, "notes.user:*", UTC)
        assert str(exc_info.value) == (
            "Existence searches (field:*) are not supported for field 'notes.user'."
        )
