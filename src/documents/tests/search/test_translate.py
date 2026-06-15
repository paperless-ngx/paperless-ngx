from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

import pytest

from documents.search._dates import _precision_bounds

if TYPE_CHECKING:
    import tantivy
from documents.search._query import _FIELD_BOOSTS
from documents.search._query import DEFAULT_SEARCH_FIELDS
from documents.search._translate import NO_MATCH
from documents.search._translate import OPEN_HI
from documents.search._translate import OPEN_LO
from documents.search._translate import Comma
from documents.search._translate import FieldRange
from documents.search._translate import FieldValue
from documents.search._translate import FieldValueList
from documents.search._translate import Passthrough
from documents.search._translate import resolve_commas
from documents.search._translate import scan
from documents.search._translate import translate_query
from documents.search._translate import translate_range
from documents.search._translate import translate_scalar


@pytest.mark.search
class TestPrecisionBounds:
    @pytest.mark.parametrize(
        ("digits", "expected"),
        [
            ("2020", ((2020, 1, 1), (2021, 1, 1))),
            ("202003", ((2020, 3, 1), (2020, 4, 1))),
            ("202012", ((2020, 12, 1), (2021, 1, 1))),
            ("20200115", ((2020, 1, 15), (2020, 1, 16))),
            ("20201231", ((2020, 12, 31), (2021, 1, 1))),
        ],
    )
    def test_valid(self, digits, expected):
        lo, hi = _precision_bounds(digits)
        assert (lo.year, lo.month, lo.day) == expected[0]
        assert (hi.year, hi.month, hi.day) == expected[1]

    @pytest.mark.parametrize("digits", ["202023", "20200230", "20201301", "20", "abcd"])
    def test_invalid_returns_none(self, digits):
        assert _precision_bounds(digits) is None


@pytest.mark.search
class TestScan:
    def test_plain_words_are_passthrough(self):
        assert scan("bank statement") == [Passthrough("bank statement")]

    def test_field_value(self):
        assert scan("created:2020") == [FieldValue("created", "2020")]

    def test_field_value_in_boolean(self):
        toks = scan("created:2020 OR foo")
        assert toks == [
            FieldValue("created", "2020"),
            Passthrough(" OR foo"),
        ]

    def test_field_value_in_parens(self):
        toks = scan("(created:2020 OR foo)")
        assert toks == [
            Passthrough("("),
            FieldValue("created", "2020"),
            Passthrough(" OR foo)"),
        ]

    def test_quoted_value(self):
        assert scan('correspondent:"A B"') == [FieldValue("correspondent", '"A B"')]

    def test_field_range(self):
        assert scan("created:[2020 TO 2021]") == [
            FieldRange("created", "[", "2020", "2021", "]"),
        ]

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            pytest.param(
                "created:[2020 to]",
                FieldRange("created", "[", "2020", "", "]"),
                id="open_upper",
            ),
            pytest.param(
                "created:[to 2020]",
                FieldRange("created", "[", "", "2020", "]"),
                id="open_lower",
            ),
        ],
    )
    def test_open_range(self, query, expected):
        assert scan(query) == [expected]

    def test_comma_inside_range_not_split(self):
        # No depth-0 comma here; the whole thing is one range token.
        toks = scan("created:[2020 TO 2021]")
        assert len(toks) == 1

    # --- Edge-case / regression tests (scan must never raise) ---

    def test_url_is_passthrough(self):
        # "http" is not a known field; the whole URL must pass through verbatim.
        assert scan("http://example.com") == [Passthrough("http://example.com")]

    def test_unterminated_quote_is_passthrough(self):
        # title is a known field but the quoted value has no closing quote;
        # _consume_value returns None so the whole string falls into passthrough.
        assert scan('title:"abc') == [Passthrough('title:"abc')]

    def test_unterminated_bracket_is_passthrough(self):
        # created is a known field but the range bracket is never closed;
        # _consume_range returns None so the whole string falls into passthrough.
        assert scan("created:[2020") == [Passthrough("created:[2020")]

    def test_empty_value_at_end_is_passthrough(self):
        # created is a known field but there is no value after the colon
        # (_consume_value returns None for start >= n), so passthrough.
        assert scan("created:") == [Passthrough("created:")]

    def test_value_containing_colon(self):
        # The bare-word value reader stops at whitespace/paren, not at colon,
        # so "2020:30" is consumed as a single value token.
        assert scan("created:2020:30") == [FieldValue("created", "2020:30")]


@pytest.mark.search
class TestCommaResolution:
    def test_value_list_multi_value_field(self):
        toks = resolve_commas(scan("tag:foo,bar"))
        assert toks == [FieldValueList("tag", ("foo", "bar"))]

    def test_value_list_three(self):
        toks = resolve_commas(scan("tag_id:1,2,3"))
        assert toks == [FieldValueList("tag_id", ("1", "2", "3"))]

    def test_text_field_comma_is_literal(self):
        # correspondent is not multi-value: comma stays inside the value.
        toks = resolve_commas(scan("correspondent:foo,bar"))
        assert toks == [FieldValue("correspondent", "foo,bar")]

    def test_clause_separator_before_known_field(self):
        toks = resolve_commas(scan("tag:foo,type:bar"))
        assert toks == [FieldValue("tag", "foo"), Comma(), FieldValue("type", "bar")]

    def test_clause_separator_after_range(self):
        toks = resolve_commas(scan("created:[2020 TO 2021],added:[2022 TO 2023]"))
        assert toks == [
            FieldRange("created", "[", "2020", "2021", "]"),
            Comma(),
            FieldRange("added", "[", "2022", "2023", "]"),
        ]

    def test_clause_separator_after_quote(self):
        toks = resolve_commas(scan('correspondent:"A B",created:[2020 TO 2021]'))
        assert toks == [
            FieldValue("correspondent", '"A B"'),
            Comma(),
            FieldRange("created", "[", "2020", "2021", "]"),
        ]

    def test_url_comma_is_literal_passthrough(self):
        toks = resolve_commas(scan("http://example.com/a,b"))
        assert toks == [Passthrough("http://example.com/a,b")]

    def test_non_multi_value_comma_is_literal(self):
        # title is not in MULTI_VALUE_FIELDS: comma stays inside the value.
        toks = resolve_commas(scan("title:10,20"))
        assert toks == [FieldValue("title", "10,20")]

    def test_clause_separator_before_known_date_field(self):
        # The comma between a bare value and a known date field acts as a
        # clause separator; both sides survive as distinct tokens.
        toks = resolve_commas(scan("correspondent:foo,created:[2020 TO 2021]"))
        assert toks == [
            FieldValue("correspondent", "foo"),
            Comma(),
            FieldRange("created", "[", "2020", "2021", "]"),
        ]


@pytest.mark.search
class TestTranslateScalar:
    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            (
                "created",
                "2020",
                "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]",
            ),
            (
                "created",
                "202003",
                "created:[2020-03-01T00:00:00Z TO 2020-04-01T00:00:00Z]",
            ),
            (
                "created",
                "20200115",
                "created:[2020-01-15T00:00:00Z TO 2020-01-16T00:00:00Z]",
            ),
            (
                "created",
                "2020-01-15",
                "created:[2020-01-15T00:00:00Z TO 2020-01-16T00:00:00Z]",
            ),
            (
                "created",
                "2020-03",
                "created:[2020-03-01T00:00:00Z TO 2020-04-01T00:00:00Z]",
            ),
        ],
    )
    def test_partial_and_iso_dates(self, field: str, value: str, expected: str) -> None:
        assert translate_scalar(field, value, UTC) == expected

    def test_invalid_date_is_no_match(self) -> None:
        assert translate_scalar("created", "202023", UTC) == NO_MATCH

    def test_keyword_delegates(self) -> None:
        # keyword path produces a range; just assert it is a created range
        out = translate_scalar("created", "today", UTC)
        assert out.startswith("created:[") and out.endswith("]")

    def test_14digit_compact_datetime(self) -> None:
        out = translate_scalar("created", "20240115120000", UTC)
        assert "20240115120000" not in out
        assert out.startswith("created:")
        assert out == "created:[2024-01-15T12:00:00Z TO 2024-01-15T12:00:00Z]"

    def test_14digit_invalid_month_is_no_match(self) -> None:
        assert translate_scalar("created", "20231300120000", UTC) == NO_MATCH


@pytest.mark.search
class TestTranslateRange:
    @pytest.mark.parametrize(
        ("lo", "hi", "expected"),
        [
            ("2005", "2009", "created:[2005-01-01T00:00:00Z TO 2010-01-01T00:00:00Z]"),
            (
                "202001",
                "202006",
                "created:[2020-01-01T00:00:00Z TO 2020-07-01T00:00:00Z]",
            ),
            (
                "20200101",
                "20201231",
                "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]",
            ),
            (
                "2020-01-01",
                "2020-12-31",
                "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]",
            ),
        ],
    )
    def test_absolute_ranges(self, lo, hi, expected):
        assert translate_range("created", lo, hi, UTC) == expected

    def test_reversed_swaps(self):
        assert translate_range("created", "2009", "2005", UTC) == (
            "created:[2005-01-01T00:00:00Z TO 2010-01-01T00:00:00Z]"
        )

    def test_open_upper(self):
        out = translate_range("created", "2020", "", UTC)
        assert out == f"created:[2020-01-01T00:00:00Z TO {OPEN_HI}]"

    def test_open_lower(self):
        out = translate_range("created", "", "2020", UTC)
        assert out == f"created:[{OPEN_LO} TO 2021-01-01T00:00:00Z]"

    def test_invalid_bound_is_no_match(self):
        assert translate_range("created", "202023", "2025", UTC) == NO_MATCH


@pytest.mark.search
class TestTranslateQuery:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (
                "created:2020",
                "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]",
            ),
            ("tag:foo,bar", "tag:foo AND tag:bar"),
            # 'type' is a user-facing alias rewritten to 'document_type' (the real schema field)
            ("tag:foo,type:bar", "tag:foo AND document_type:bar"),
            (
                "created:[2020 TO 2021],added:[2022 TO 2023]",
                "created:[2020-01-01T00:00:00Z TO 2022-01-01T00:00:00Z]"
                " AND "
                "added:[2022-01-01T00:00:00Z TO 2024-01-01T00:00:00Z]",
            ),
            # correspondent is not multi-value: comma stays literal inside the value
            ("correspondent:foo,bar", "correspondent:foo,bar"),
        ],
    )
    def test_golden(self, raw: str, expected: str) -> None:
        assert translate_query(raw, UTC) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "created:2020",
            "created:202003",
            "created:[20200101 TO 20201231]",
            "created:[2020-01-01 TO 2020-12-31]",
            "created:[2020 to]",
            "created:[to 2020]",
            "title:x,created:[2020 TO 2021]",
            "created:2020 OR foo",
            "(created:2020 OR invoice)",
            "tag:foo,type:bar",
            "created:202023",
            "bank statement",
        ],
    )
    def test_parse_acceptance(self, index: tantivy.Index, raw: str) -> None:
        translated = translate_query(raw, UTC)
        # Must not raise:
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
