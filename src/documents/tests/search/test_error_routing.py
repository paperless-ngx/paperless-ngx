"""Diagnostics route by Cause, and user-facing messages are host-owned.

whoosh-compat documents ``Diagnostic.message`` as developer output with no
stability guarantee, so it must never reach an HTTP response body.
"""

from __future__ import annotations

import logging
from datetime import UTC

import pytest
import tantivy
from whoosh_compat.errors import Diagnostic
from whoosh_compat.errors import DiagnosticKind
from whoosh_compat.errors import QueryError
from whoosh_compat.errors import cause_for
from whoosh_compat.fields import FieldKind
from whoosh_compat.fields import FieldRef

from documents.search._errors import SearchQueryError
from documents.search._query import _map_emit_error
from documents.search._query import _single_diagnostic_to_error
from documents.search._query import parse_user_query
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

pytestmark = pytest.mark.search

_LIBRARY_PROSE = "INTERNAL LIBRARY WORDING WITH raw tantivy detail"


@pytest.fixture(scope="module")
def query_index() -> tantivy.Index:
    """An in-memory, unstemmed index; these tests only parse, never index."""
    idx = tantivy.Index(build_schema(), path=None)
    register_tokenizers(idx, "")
    return idx


def _diagnostic(
    kind: DiagnosticKind,
    *,
    field: FieldRef | None = FieldRef("title"),
    field_kind: FieldKind | None = FieldKind.TEXT,
) -> Diagnostic:
    """A Diagnostic shaped like the emitter's, with the library's own
    kind -> cause mapping rather than a hand-picked cause."""
    return Diagnostic(
        kind=kind,
        cause=cause_for(kind),
        message=_LIBRARY_PROSE,
        field=field,
        field_kind=field_kind,
    )


class TestEmitErrorRouting:
    """Every Cause gets a distinguishable treatment, not just "a 400"."""

    @pytest.mark.parametrize(
        "kind",
        [
            DiagnosticKind.BACKEND_REJECTED,
            DiagnosticKind.AST_INVALID_SHAPE,
            DiagnosticKind.AST_UNKNOWN_FIELD,
        ],
    )
    def test_internal_cause_is_not_converted(self, kind: DiagnosticKind) -> None:
        """
        GIVEN:
            - A QueryError wrapping a Diagnostic whose Cause is INTERNAL
              (BACKEND_REJECTED/AST_INVALID_SHAPE/AST_UNKNOWN_FIELD)
        WHEN:
            - _map_emit_error processes it
        THEN:
            - The original QueryError propagates unchanged, so it surfaces
              as a 500 monitoring can see, never a 400 blaming the user
        """
        error = QueryError(_diagnostic(kind))
        with pytest.raises(QueryError) as excinfo:
            _map_emit_error(error)
        assert excinfo.value is error

    def test_misconfigured_cause_is_logged_and_reraised(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A QueryError for SCHEMA_FIELD_MISSING naming field "asn"
        WHEN:
            - _map_emit_error processes it
        THEN:
            - Exactly one ERROR log record is emitted naming the field and
              the diagnostic kind, and the original QueryError propagates
              unchanged: a registry/schema disagreement is transient (the
              exact same query succeeds once the index is rebuilt), so it
              surfaces as a 500 an operator can see rather than a 400
              telling the client their query is permanently invalid
        """
        kind = DiagnosticKind.SCHEMA_FIELD_MISSING
        error = QueryError(_diagnostic(kind, field=FieldRef("asn")))
        with (
            caplog.at_level(logging.ERROR, logger="paperless.search"),
            pytest.raises(QueryError) as excinfo,
        ):
            _map_emit_error(error)
        assert excinfo.value is error
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "asn" in errors[0].getMessage()
        assert kind.name in errors[0].getMessage()

    @pytest.mark.parametrize(
        "kind",
        [
            DiagnosticKind.TEXT_RANGE,
            DiagnosticKind.PATTERN_TOO_COMPLEX,
            DiagnosticKind.EXISTS_REQUIRES_FAST,
        ],
    )
    def test_unsupported_cause_is_a_400_with_no_operator_log(
        self,
        kind: DiagnosticKind,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A QueryError for a query tantivy cannot run
              (TEXT_RANGE/PATTERN_TOO_COMPLEX/EXISTS_REQUIRES_FAST)
        WHEN:
            - _map_emit_error processes it
        THEN:
            - It becomes a SearchQueryError with no log record at WARNING
              or above; a query tantivy cannot run is the user's to fix,
              not an operator alert. EXISTS_REQUIRES_FAST is nominally
              MISCONFIGURED but belongs here: it is decided from the
              registry's own FieldSpec, so it never reports a disagreement
              anyone could resolve
        """
        with caplog.at_level(logging.WARNING, logger="paperless.search"):
            error = _map_emit_error(QueryError(_diagnostic(kind)))
        assert isinstance(error, SearchQueryError)
        assert caplog.records == []

    @pytest.mark.parametrize(
        "kind",
        [
            DiagnosticKind.TEXT_RANGE,
            DiagnosticKind.PATTERN_TOO_COMPLEX,
            DiagnosticKind.EXISTS_REQUIRES_FAST,
        ],
    )
    def test_user_facing_message_never_echoes_library_prose(
        self,
        kind: DiagnosticKind,
    ) -> None:
        """
        GIVEN:
            - A QueryError carrying whoosh-compat's own developer-facing
              message text (SCHEMA_FIELD_MISSING excluded: it is now
              re-raised rather than converted, so it never produces a
              user-facing message at all, see
              test_misconfigured_cause_is_logged_and_reraised)
        WHEN:
            - _map_emit_error processes it
        THEN:
            - The resulting error's string never contains that library
              prose
        """
        error = _map_emit_error(QueryError(_diagnostic(kind)))
        assert _LIBRARY_PROSE not in str(error)

    @pytest.mark.parametrize(
        "kind",
        [
            DiagnosticKind.TEXT_RANGE,
            DiagnosticKind.PATTERN_TOO_COMPLEX,
            DiagnosticKind.EXISTS_REQUIRES_FAST,
        ],
    )
    def test_user_facing_message_names_the_field(
        self,
        kind: DiagnosticKind,
    ) -> None:
        """
        GIVEN:
            - A QueryError for a JSON subpath field (custom_fields.value)
        WHEN:
            - _map_emit_error processes it
        THEN:
            - The resulting error names the field using its canonical
              dotted form, including the subpath (FieldRef.__str__ yields
              this dotted name, so every user-reachable emit kind can name
              it)
        """
        diagnostic = _diagnostic(
            kind,
            field=FieldRef("custom_fields", "value"),
            field_kind=FieldKind.JSON,
        )
        error = _map_emit_error(QueryError(diagnostic))
        assert "custom_fields.value" in str(error)


class TestParseDiagnosticMessages:
    """Parse-time diagnostics are host-worded too, off field_kind."""

    def test_too_deep_is_a_400_without_library_prose(self) -> None:
        """
        GIVEN:
            - A parse-time Diagnostic for TOO_DEEP with no field
        WHEN:
            - _single_diagnostic_to_error processes it
        THEN:
            - It becomes a SearchQueryError with no library prose in its
              message
        """
        error = _single_diagnostic_to_error(
            _diagnostic(DiagnosticKind.TOO_DEEP, field=None, field_kind=None),
        )
        assert isinstance(error, SearchQueryError)
        assert _LIBRARY_PROSE not in str(error)

    @pytest.mark.parametrize(
        ("kind", "field_kind"),
        [
            (DiagnosticKind.PATTERN_ON_NUMERIC, FieldKind.U64),
            (DiagnosticKind.PATTERN_ON_BOOLEAN_EXISTS, FieldKind.BOOLEAN_EXISTS),
            (DiagnosticKind.PATTERN_ON_SUBPATH, FieldKind.JSON),
        ],
    )
    def test_pattern_on_kinds_name_the_field_and_its_kind(
        self,
        kind: DiagnosticKind,
        field_kind: FieldKind,
    ) -> None:
        """
        GIVEN:
            - A parse-time Diagnostic for a pattern used against a kind
              that cannot take one
              (PATTERN_ON_NUMERIC/PATTERN_ON_BOOLEAN_EXISTS/PATTERN_ON_SUBPATH)
        WHEN:
            - _single_diagnostic_to_error processes it
        THEN:
            - The message names both the field and its kind, with no
              library prose
        """
        error = _single_diagnostic_to_error(
            _diagnostic(kind, field=FieldRef("asn"), field_kind=field_kind),
        )
        message = str(error)
        assert _LIBRARY_PROSE not in message
        assert "asn" in message
        assert field_kind.name.lower() in message

    def test_single_char_bracket_range_names_the_field_and_the_value(self) -> None:
        """
        GIVEN:
            - A SINGLE_CHAR_BRACKET_RANGE diagnostic for "title" with
              raw_value "200[1-9]"
        WHEN:
            - _single_diagnostic_to_error processes it
        THEN:
            - The resulting SearchQueryError names both the field and the
              offending value, with no library prose
        """
        diagnostic = Diagnostic(
            kind=DiagnosticKind.SINGLE_CHAR_BRACKET_RANGE,
            cause=cause_for(DiagnosticKind.SINGLE_CHAR_BRACKET_RANGE),
            message=_LIBRARY_PROSE,
            field=FieldRef("title"),
            field_kind=FieldKind.TEXT,
            raw_value="200[1-9]",
        )
        error = _single_diagnostic_to_error(diagnostic)
        message = str(error)
        assert isinstance(error, SearchQueryError)
        assert _LIBRARY_PROSE not in message
        assert "title" in message
        assert "200[1-9]" in message


class TestRealQueriesRouteCorrectly:
    """The routing table against diagnostics emit() really produces."""

    def test_text_range_is_a_400_naming_the_field(
        self,
        query_index: tantivy.Index,
    ) -> None:
        """
        GIVEN:
            - A real query index
        WHEN:
            - parse_user_query is called with a text-range query
              ("title:[a to b]")
        THEN:
            - It raises SearchQueryError naming "title"
        """
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "title:[a to b]", UTC)
        assert "title" in str(excinfo.value)

    def test_wildcard_on_a_numeric_field_is_a_400_naming_the_field(
        self,
        query_index: tantivy.Index,
    ) -> None:
        """
        GIVEN:
            - A real query index
        WHEN:
            - parse_user_query is called with a wildcard on a numeric
              field ("asn:12*")
        THEN:
            - It raises SearchQueryError naming "asn"
        """
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "asn:12*", UTC)
        assert "asn" in str(excinfo.value)

    def test_single_char_bracket_range_is_a_400_naming_field_and_value(
        self,
        query_index: tantivy.Index,
    ) -> None:
        """
        GIVEN:
            - A real query index
        WHEN:
            - parse_user_query is called with "title:200[1-9]"
        THEN:
            - It raises SearchQueryError naming both "title" and
              "200[1-9]"
        """
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "title:200[1-9]", UTC)
        message = str(excinfo.value)
        assert "title" in message
        assert "200[1-9]" in message

    def test_internal_diagnostic_escapes_as_a_query_error(
        self,
        query_index: tantivy.Index,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - tantivy_emit monkeypatched to raise a QueryError with an
              INTERNAL-cause diagnostic (BACKEND_REJECTED), the one case
              with no query text of its own involved
        WHEN:
            - parse_user_query runs a normal query ("invoice")
        THEN:
            - The QueryError propagates unconverted; emit() reporting a
              defect in itself must not become a user-facing 400
        """
        import documents.search._query as query_mod

        def raise_internal(*args: object, **kwargs: object) -> None:
            raise QueryError(_diagnostic(DiagnosticKind.BACKEND_REJECTED))

        monkeypatch.setattr(query_mod, "tantivy_emit", raise_internal)
        with pytest.raises(QueryError):
            parse_user_query(query_index, "invoice", UTC)
