"""``field:*`` on a JSON field is user error, not an operator alert.

whoosh-compat classifies EXISTS_REQUIRES_FAST as MISCONFIGURED, and
_map_emit_error used to route every MISCONFIGURED diagnostic to an ERROR log.
But the kind is decided from the registry's own FieldSpec (kind plus fast)
without consulting the index schema, and field_descriptors() builds the JSON
fields non-fast deliberately, so nothing is misconfigured and no operator
action can clear the condition. Any authenticated user could otherwise emit
ERROR lines in a loop by repeating ``notes:*``.

SCHEMA_FIELD_MISSING, the other MISCONFIGURED kind, does compare the registry
against the live schema, so it stays an ERROR.
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
from documents.search._query import parse_user_query
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

pytestmark = pytest.mark.search

# Every spelling of "does this JSON field have a value" a user can type.
EXISTS_QUERIES = [
    "notes:*",
    "notes.note:*",
    "notes.user:*",
    "custom_fields:*",
    "custom_fields.name:*",
    "custom_fields.value:*",
]


@pytest.fixture(scope="module")
def query_index() -> tantivy.Index:
    idx = tantivy.Index(build_schema(), path=None)
    register_tokenizers(idx, "")
    return idx


class TestJsonExistsIsUserError:
    @pytest.mark.parametrize("query", EXISTS_QUERIES)
    def test_query_is_a_400_that_emits_no_error_log(
        self,
        query_index: tantivy.Index,
        caplog: pytest.LogCaptureFixture,
        query: str,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="paperless.search"):
            with pytest.raises(SearchQueryError) as excinfo:
                parse_user_query(query_index, query, UTC)
        assert query.split(":", maxsplit=1)[0] in str(excinfo.value)
        assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


class TestGenuineMisconfigurationStillLogs:
    def test_schema_field_missing_is_an_error_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The registry naming a field the index schema does not have is a
        real mismatch an operator can fix, so it keeps the alert."""
        kind = DiagnosticKind.SCHEMA_FIELD_MISSING
        error = QueryError(
            Diagnostic(
                kind=kind,
                cause=cause_for(kind),
                message="field 'asn' is not defined in the index schema",
                field=FieldRef("asn"),
                field_kind=FieldKind.U64,
            ),
        )
        with caplog.at_level(logging.ERROR, logger="paperless.search"):
            mapped = _map_emit_error(error)
        assert isinstance(mapped, SearchQueryError)
        records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(records) == 1
        assert kind.name in records[0].getMessage()
