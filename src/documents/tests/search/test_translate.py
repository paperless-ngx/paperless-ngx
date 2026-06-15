from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
import time_machine

from documents.search._dates import _precision_bounds

if TYPE_CHECKING:
    import tantivy
from documents.search._query import _FIELD_BOOSTS
from documents.search._query import DEFAULT_SEARCH_FIELDS
from documents.search._translate import OPEN_HI
from documents.search._translate import OPEN_LO
from documents.search._translate import Comma
from documents.search._translate import FieldRange
from documents.search._translate import FieldValue
from documents.search._translate import FieldValueList
from documents.search._translate import InvalidDateQuery
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

    def test_comma_followed_by_unconsumable_value_stops(self):
        # A comma followed by whitespace is neither a value-list continuation nor a
        # clause separator: the value stops and the comma stays as passthrough.
        assert scan("tag:foo, bar") == [
            FieldValue("tag", "foo"),
            Passthrough(", bar"),
        ]

    def test_bracket_without_to_is_open_upper_bound(self):
        # A bracketed value with no TO falls back to (value, "") -> open upper bound.
        assert scan("created:[2020]") == [
            FieldRange("created", "[", "2020", "", "]"),
        ]

    def test_known_field_name_midword_is_passthrough(self):
        # A known field name embedded mid-word is not a field token (the
        # word-boundary guard); the whole run stays passthrough.
        assert scan("xtag:foo") == [Passthrough("xtag:foo")]


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

    def test_invalid_date_raises(self) -> None:
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_scalar("created", "202023", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "202023"

    def test_keyword_delegates(self) -> None:
        # keyword path produces a range; just assert it is a created range
        out = translate_scalar("created", "today", UTC)
        assert out.startswith("created:[") and out.endswith("]")

    def test_14digit_compact_datetime(self) -> None:
        out = translate_scalar("created", "20240115120000", UTC)
        assert "20240115120000" not in out
        assert out.startswith("created:")
        assert out == "created:[2024-01-15T12:00:00Z TO 2024-01-15T12:00:00Z]"

    def test_14digit_invalid_month_raises(self) -> None:
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_scalar("created", "20231300120000", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "20231300120000"

    def test_unrecognized_value_raises(self) -> None:
        # A value that is not a keyword, digits, ISO date, or compact timestamp
        # raises rather than producing invalid Tantivy syntax or silently matching
        # nothing.
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_scalar("created", "garbage", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "garbage"


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

    def test_invalid_bound_raises(self):
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_range("created", "202023", "2025", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "202023"

    def test_invalid_high_bound_raises(self):
        # Low bound parses, high bound does not -> raise on the high bound.
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_range("created", "2020", "garbage", UTC)
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "garbage"


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
            "bank statement",
        ],
    )
    def test_parse_acceptance(self, index: tantivy.Index, raw: str) -> None:
        translated = translate_query(raw, UTC)
        # Must not raise:
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)


@pytest.mark.search
class TestFieldAliasing:
    """Whoosh->Tantivy field-name aliasing (type/path -> document_type/storage_path)."""

    def test_type_alias(self) -> None:
        assert translate_query("type:invoice", UTC) == "document_type:invoice"

    def test_path_alias(self) -> None:
        assert translate_query("path:/foo/bar", UTC) == "storage_path:/foo/bar"

    def test_type_id_alias(self) -> None:
        assert translate_query("type_id:5", UTC) == "document_type_id:5"

    def test_path_id_alias(self) -> None:
        assert translate_query("path_id:7", UTC) == "storage_path_id:7"

    def test_clause_separator_plus_alias(self) -> None:
        # Comma between known fields acts as AND separator; alias still applied.
        assert (
            translate_query("tag:foo,type:bar", UTC) == "tag:foo AND document_type:bar"
        )

    def test_type_range_alias(self) -> None:
        # type is not a date field; range passes through verbatim with alias applied.
        assert (
            translate_query("type:[2020 TO 2021]", UTC)
            == "document_type:[2020 TO 2021]"
        )

    def test_parse_acceptance_type(self, index: tantivy.Index) -> None:
        # Translated output must be accepted by the real Tantivy parser.
        translated = translate_query("type:invoice", UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)

    def test_parse_acceptance_path(self, index: tantivy.Index) -> None:
        translated = translate_query("path:foo", UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)


# Freeze time so relative-date tests are deterministic.
_FROZEN_NOW = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)


@pytest.mark.search
class TestRelativeRanges:
    """Relative date-range tokens resolved against a frozen clock."""

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_minus_7_days_to_now(self) -> None:
        assert translate_query("added:[-7 days to now]", UTC) == (
            "added:[2026-03-21T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_minus_1_week_to_now(self) -> None:
        assert translate_query("added:[-1 week to now]", UTC) == (
            "added:[2026-03-21T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_minus_1_month_to_now(self) -> None:
        assert translate_query("created:[-1 month to now]", UTC) == (
            "created:[2026-02-28T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_minus_1_year_to_now(self) -> None:
        assert translate_query("modified:[-1 year to now]", UTC) == (
            "modified:[2025-03-28T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_minus_3_hours_to_now(self) -> None:
        assert translate_query("added:[-3 hours to now]", UTC) == (
            "added:[2026-03-28T09:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_uppercase_units(self) -> None:
        assert translate_query("added:[-1 WEEK TO NOW]", UTC) == (
            "added:[2026-03-21T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_now_minus_7d_compact(self) -> None:
        assert translate_query("added:[now-7d TO now]", UTC) == (
            "added:[2026-03-21T12:00:00Z TO 2026-03-28T12:00:00Z]"
        )

    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_reversed_range_swapped(self) -> None:
        # now+1h TO now-1h is reversed; translate_range swaps -> lo=now-1h, hi=now+1h
        assert translate_query("added:[now+1h TO now-1h]", UTC) == (
            "added:[2026-03-28T11:00:00Z TO 2026-03-28T13:00:00Z]"
        )

    @pytest.mark.parametrize(
        "raw",
        [
            "added:[-7 days to now]",
            "added:[-1 week to now]",
            "created:[-1 month to now]",
            "modified:[-1 year to now]",
            "added:[-3 hours to now]",
            "added:[now-7d TO now]",
            "added:[now+1h TO now-1h]",
        ],
    )
    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_parse_acceptance(self, index: tantivy.Index, raw: str) -> None:
        translated = translate_query(raw, UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)


@pytest.mark.search
class TestOperatorNormalization:
    """Post-render operator normalization in translate_query."""

    def test_spaced_dash_removed(self) -> None:
        assert (
            translate_query("H52.1 - Kurzsichtigkeit", UTC) == "H52.1 Kurzsichtigkeit"
        )

    def test_spaced_dash_simple(self) -> None:
        assert translate_query("bar - baz", UTC) == "bar baz"

    def test_trailing_operator_stripped(self) -> None:
        assert translate_query("foo -", UTC) == "foo"

    def test_date_range_preserved(self) -> None:
        out = translate_query("created:[2020 TO 2021]", UTC)
        # Must not corrupt the ISO range
        assert out == "created:[2020-01-01T00:00:00Z TO 2022-01-01T00:00:00Z]"

    def test_date_scalar_with_or(self) -> None:
        out = translate_query("created:2020 OR foo", UTC)
        # The created scalar becomes a range; " OR foo" passes through verbatim.
        assert out.startswith("created:[")
        assert "OR foo" in out

    def test_parse_acceptance_spaced_dash(self, index: tantivy.Index) -> None:
        translated = translate_query("H52.1 - Kurzsichtigkeit", UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)

    def test_parse_acceptance_trailing_op(self, index: tantivy.Index) -> None:
        translated = translate_query("foo -", UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)


@pytest.mark.search
class TestMultiWordDateKeywords:
    """scan() must consume multi-word date keywords as a single value."""

    def test_scan_previous_week_as_single_token(self) -> None:
        # "created:previous week" must produce one FieldValue with value "previous week",
        # not FieldValue("created","previous") + Passthrough(" week").
        toks = scan("created:previous week")
        assert toks == [FieldValue("created", "previous week")]

    def test_scan_this_month_as_single_token(self) -> None:
        toks = scan("added:this month")
        assert toks == [FieldValue("added", "this month")]

    def test_scan_previous_month_as_single_token(self) -> None:
        toks = scan("created:previous month")
        assert toks == [FieldValue("created", "previous month")]

    def test_scan_this_year_as_single_token(self) -> None:
        toks = scan("added:this year")
        assert toks == [FieldValue("added", "this year")]

    def test_scan_previous_year_as_single_token(self) -> None:
        toks = scan("created:previous year")
        assert toks == [FieldValue("created", "previous year")]

    def test_scan_previous_quarter_as_single_token(self) -> None:
        toks = scan("created:previous quarter")
        assert toks == [FieldValue("created", "previous quarter")]

    def test_quoted_multi_word_keyword_still_works(self) -> None:
        # The quoted form must continue to work as before.
        toks = scan('created:"previous week"')
        assert toks == [FieldValue("created", '"previous week"')]

    def test_non_date_field_not_affected(self) -> None:
        # "previous" stops at the space for non-date fields; " week" passes through.
        toks = scan("correspondent:previous week")
        assert toks == [
            FieldValue("correspondent", "previous"),
            Passthrough(" week"),
        ]


@pytest.mark.search
class TestKeywordDateResolution:
    """Relative date keywords resolve to exact ISO ranges against a frozen clock.

    Frozen at 2026-03-28 12:00 UTC (a Saturday in Q1) so the week, month,
    quarter and year rollovers are all exercised by a single anchor.
    """

    # created is a DateField: bounds are UTC midnight, no timezone offset.
    @pytest.mark.parametrize(
        ("keyword", "expected"),
        [
            pytest.param(
                "today",
                "created:[2026-03-28T00:00:00Z TO 2026-03-29T00:00:00Z]",
                id="today",
            ),
            pytest.param(
                "yesterday",
                "created:[2026-03-27T00:00:00Z TO 2026-03-28T00:00:00Z]",
                id="yesterday",
            ),
            pytest.param(
                "previous week",
                "created:[2026-03-16T00:00:00Z TO 2026-03-23T00:00:00Z]",
                id="previous-week",
            ),
            pytest.param(
                "this month",
                "created:[2026-03-01T00:00:00Z TO 2026-04-01T00:00:00Z]",
                id="this-month",
            ),
            pytest.param(
                "previous month",
                "created:[2026-02-01T00:00:00Z TO 2026-03-01T00:00:00Z]",
                id="previous-month",
            ),
            pytest.param(
                "this year",
                "created:[2026-01-01T00:00:00Z TO 2027-01-01T00:00:00Z]",
                id="this-year",
            ),
            pytest.param(
                "previous year",
                "created:[2025-01-01T00:00:00Z TO 2026-01-01T00:00:00Z]",
                id="previous-year",
            ),
            pytest.param(
                "previous quarter",
                "created:[2025-10-01T00:00:00Z TO 2026-01-01T00:00:00Z]",
                id="previous-quarter",
            ),
        ],
    )
    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_date_only_field_keyword_ranges(
        self,
        keyword: str,
        expected: str,
    ) -> None:
        assert translate_query(f"created:{keyword}", UTC) == expected

    # added is a DateTimeField: local-tz midnight converted to UTC. Tokyo
    # (+09:00, no DST) shifts each midnight boundary back to 15:00Z the day
    # before, so this also exercises the local-midnight offset path.
    @pytest.mark.parametrize(
        ("keyword", "expected"),
        [
            pytest.param(
                "today",
                "added:[2026-03-27T15:00:00Z TO 2026-03-28T15:00:00Z]",
                id="today",
            ),
            pytest.param(
                "yesterday",
                "added:[2026-03-26T15:00:00Z TO 2026-03-27T15:00:00Z]",
                id="yesterday",
            ),
            pytest.param(
                "previous week",
                "added:[2026-03-15T15:00:00Z TO 2026-03-22T15:00:00Z]",
                id="previous-week",
            ),
            pytest.param(
                "this month",
                "added:[2026-02-28T15:00:00Z TO 2026-03-31T15:00:00Z]",
                id="this-month",
            ),
            pytest.param(
                "previous month",
                "added:[2026-01-31T15:00:00Z TO 2026-02-28T15:00:00Z]",
                id="previous-month",
            ),
            pytest.param(
                "this year",
                "added:[2025-12-31T15:00:00Z TO 2026-12-31T15:00:00Z]",
                id="this-year",
            ),
            pytest.param(
                "previous year",
                "added:[2024-12-31T15:00:00Z TO 2025-12-31T15:00:00Z]",
                id="previous-year",
            ),
            pytest.param(
                "previous quarter",
                "added:[2025-09-30T15:00:00Z TO 2025-12-31T15:00:00Z]",
                id="previous-quarter",
            ),
        ],
    )
    @time_machine.travel(_FROZEN_NOW, tick=False)
    def test_datetime_field_keyword_ranges_local_tz(
        self,
        keyword: str,
        expected: str,
    ) -> None:
        assert translate_query(f"added:{keyword}", ZoneInfo("Asia/Tokyo")) == expected


@pytest.mark.search
class TestISODatetimeBounds:
    """Full ISO datetime tokens in range bounds must be parsed directly."""

    def test_translate_range_iso_bounds_passthrough(self) -> None:
        # Already-ISO datetime bounds must pass through as-is (exact instant).
        result = translate_range(
            "created",
            "2020-01-01T00:00:00Z",
            "2021-01-01T00:00:00Z",
            UTC,
        )
        assert result == "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]"

    def test_translate_query_iso_range_preserved(self) -> None:
        q = "created:[2026-01-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
        assert translate_query(q, UTC) == q

    def test_translate_query_comma_separated_iso_ranges(self) -> None:
        q = (
            "created:[2026-01-01T00:00:00Z TO 2026-06-01T00:00:00Z],"
            "added:[2026-05-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
        )
        result = translate_query(q, UTC)
        assert result == (
            "created:[2026-01-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
            " AND "
            "added:[2026-05-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
        )

    def test_invalid_iso_datetime_raises(self) -> None:
        # A token with "T" that is not valid ISO datetime -> raise.
        with pytest.raises(InvalidDateQuery) as exc_info:
            translate_range(
                "created",
                "2020-01-01T99:00:00Z",
                "2021-01-01T00:00:00Z",
                UTC,
            )
        assert exc_info.value.field == "created"
        assert exc_info.value.value == "2020-01-01T99:00:00Z"

    def test_parse_acceptance_iso_bounds(self, index: tantivy.Index) -> None:
        q = "created:[2026-01-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
        translated = translate_query(q, UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)

    def test_parse_acceptance_comma_iso_ranges(self, index: tantivy.Index) -> None:
        q = (
            "created:[2026-01-01T00:00:00Z TO 2026-06-01T00:00:00Z],"
            "added:[2026-05-01T00:00:00Z TO 2026-06-01T00:00:00Z]"
        )
        translated = translate_query(q, UTC)
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
