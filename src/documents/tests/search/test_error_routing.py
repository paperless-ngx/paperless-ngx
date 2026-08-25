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
        """A library defect must surface as a 500 monitoring can see, not a
        400 blaming the user."""
        error = QueryError(_diagnostic(kind))
        with pytest.raises(QueryError) as excinfo:
            _map_emit_error(error)
        assert excinfo.value is error

    def test_misconfigured_cause_is_logged_and_becomes_a_400(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        kind = DiagnosticKind.SCHEMA_FIELD_MISSING
        with caplog.at_level(logging.ERROR, logger="paperless.search"):
            error = _map_emit_error(
                QueryError(_diagnostic(kind, field=FieldRef("asn"))),
            )
        assert isinstance(error, SearchQueryError)
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
        """A query tantivy cannot run is the user's to fix; it must not page
        an operator the way a registry/schema mismatch does.

        EXISTS_REQUIRES_FAST is nominally MISCONFIGURED but belongs here: it
        is decided from the registry's own FieldSpec, so it never reports a
        disagreement anyone could resolve."""
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
            DiagnosticKind.SCHEMA_FIELD_MISSING,
        ],
    )
    def test_user_facing_message_never_echoes_library_prose(
        self,
        kind: DiagnosticKind,
    ) -> None:
        error = _map_emit_error(QueryError(_diagnostic(kind)))
        assert _LIBRARY_PROSE not in str(error)

    @pytest.mark.parametrize(
        "kind",
        [
            DiagnosticKind.TEXT_RANGE,
            DiagnosticKind.PATTERN_TOO_COMPLEX,
            DiagnosticKind.EXISTS_REQUIRES_FAST,
            DiagnosticKind.SCHEMA_FIELD_MISSING,
        ],
    )
    def test_user_facing_message_names_the_field(
        self,
        kind: DiagnosticKind,
    ) -> None:
        """FieldRef.__str__ yields the canonical dotted name, including a
        JSON subpath, so every user-reachable emit kind can name it."""
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
        error = _single_diagnostic_to_error(
            _diagnostic(kind, field=FieldRef("asn"), field_kind=field_kind),
        )
        message = str(error)
        assert _LIBRARY_PROSE not in message
        assert "asn" in message
        assert field_kind.name.lower() in message

    def test_single_char_bracket_range_names_the_field_and_the_value(self) -> None:
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
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "title:[a to b]", UTC)
        assert "title" in str(excinfo.value)

    def test_wildcard_on_a_numeric_field_is_a_400_naming_the_field(
        self,
        query_index: tantivy.Index,
    ) -> None:
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "asn:12*", UTC)
        assert "asn" in str(excinfo.value)

    def test_single_char_bracket_range_is_a_400_naming_field_and_value(
        self,
        query_index: tantivy.Index,
    ) -> None:
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
        """The one case with no query text that reaches it: emit() reporting
        a defect in itself must not be converted to a user-facing 400."""
        import documents.search._query as query_mod

        def raise_internal(*args: object, **kwargs: object) -> None:
            raise QueryError(_diagnostic(DiagnosticKind.BACKEND_REJECTED))

        monkeypatch.setattr(query_mod, "tantivy_emit", raise_internal)
        with pytest.raises(QueryError):
            parse_user_query(query_index, "invoice", UTC)
