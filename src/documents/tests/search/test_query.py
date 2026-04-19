from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from datetime import tzinfo
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
import tantivy
import time_machine

from documents.search._query import _date_only_range
from documents.search._query import _datetime_range
from documents.search._query import _rewrite_compact_date
from documents.search._query import build_permission_filter
from documents.search._query import normalize_query
from documents.search._query import parse_user_query
from documents.search._query import rewrite_natural_date_keywords
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

pytestmark = pytest.mark.search

EASTERN = ZoneInfo("America/New_York")  # UTC-5 / UTC-4 (DST)
AUCKLAND = ZoneInfo("Pacific/Auckland")  # UTC+13 in southern-hemisphere summer


def _range(result: str, field: str) -> tuple[str, str]:
    m = re.search(rf"{field}:\[(.+?) TO (.+?)\]", result)
    assert m, f"No range for {field!r} in: {result!r}"
    return m.group(1), m.group(2)


class TestCreatedDateField:
    """
    created is a Django DateField: indexed as midnight UTC of the local calendar
    date. No offset arithmetic needed - the local calendar date is what matters.
    """

    @pytest.mark.parametrize(
        ("tz", "expected_lo", "expected_hi"),
        [
            pytest.param(UTC, "2026-03-28T00:00:00Z", "2026-03-29T00:00:00Z", id="utc"),
            pytest.param(
                EASTERN,
                "2026-03-28T00:00:00Z",
                "2026-03-29T00:00:00Z",
                id="eastern_same_calendar_date",
            ),
        ],
    )
    @time_machine.travel(datetime(2026, 3, 28, 15, 30, tzinfo=UTC), tick=False)
    def test_today(self, tz: tzinfo, expected_lo: str, expected_hi: str) -> None:
        lo, hi = _range(rewrite_natural_date_keywords("created:today", tz), "created")
        assert lo == expected_lo
        assert hi == expected_hi

    @time_machine.travel(datetime(2026, 3, 28, 3, 0, tzinfo=UTC), tick=False)
    def test_today_auckland_ahead_of_utc(self) -> None:
        # UTC 03:00 -> Auckland (UTC+13) = 16:00 same date; local date = 2026-03-28
        lo, _ = _range(
            rewrite_natural_date_keywords("created:today", AUCKLAND),
            "created",
        )
        assert lo == "2026-03-28T00:00:00Z"

    @pytest.mark.parametrize(
        ("field", "keyword", "expected_lo", "expected_hi"),
        [
            pytest.param(
                "created",
                "yesterday",
                "2026-03-27T00:00:00Z",
                "2026-03-28T00:00:00Z",
                id="yesterday",
            ),
            pytest.param(
                "created",
                "previous week",
                "2026-03-16T00:00:00Z",
                "2026-03-23T00:00:00Z",
                id="previous_week",
            ),
            pytest.param(
                "created",
                "this month",
                "2026-03-01T00:00:00Z",
                "2026-04-01T00:00:00Z",
                id="this_month",
            ),
            pytest.param(
                "created",
                "previous month",
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
                id="previous_month",
            ),
            pytest.param(
                "created",
                "this year",
                "2026-01-01T00:00:00Z",
                "2027-01-01T00:00:00Z",
                id="this_year",
            ),
            pytest.param(
                "created",
                "previous year",
                "2025-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                id="previous_year",
            ),
        ],
    )
    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_date_keywords(
        self,
        field: str,
        keyword: str,
        expected_lo: str,
        expected_hi: str,
    ) -> None:
        # 2026-03-28 is Saturday; Mon-Sun week calculation built into expectations
        query = f"{field}:{keyword}"
        lo, hi = _range(rewrite_natural_date_keywords(query, UTC), field)
        assert lo == expected_lo
        assert hi == expected_hi

    @time_machine.travel(datetime(2026, 12, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_this_month_december_wraps_to_next_year(self) -> None:
        # December: next month must roll over to January 1 of next year
        lo, hi = _range(
            rewrite_natural_date_keywords("created:this month", UTC),
            "created",
        )
        assert lo == "2026-12-01T00:00:00Z"
        assert hi == "2027-01-01T00:00:00Z"

    @time_machine.travel(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_last_month_january_wraps_to_previous_year(self) -> None:
        # January: last month must roll back to December 1 of previous year
        lo, hi = _range(
            rewrite_natural_date_keywords("created:previous month", UTC),
            "created",
        )
        assert lo == "2025-12-01T00:00:00Z"
        assert hi == "2026-01-01T00:00:00Z"

    @time_machine.travel(datetime(2026, 7, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_previous_quarter(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords('created:"previous quarter"', UTC),
            "created",
        )
        assert lo == "2026-04-01T00:00:00Z"
        assert hi == "2026-07-01T00:00:00Z"

    def test_unknown_keyword_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown keyword"):
            _date_only_range("bogus_keyword", UTC)


class TestDateTimeFields:
    """
    added/modified store full UTC datetimes. Natural keywords must convert
    the local day boundaries to UTC - timezone offset arithmetic IS required.
    """

    @time_machine.travel(datetime(2026, 3, 28, 15, 30, tzinfo=UTC), tick=False)
    def test_added_today_eastern(self) -> None:
        # EDT = UTC-4; local midnight 2026-03-28 00:00 EDT = 2026-03-28 04:00 UTC
        lo, hi = _range(rewrite_natural_date_keywords("added:today", EASTERN), "added")
        assert lo == "2026-03-28T04:00:00Z"
        assert hi == "2026-03-29T04:00:00Z"

    @time_machine.travel(datetime(2026, 3, 29, 2, 0, tzinfo=UTC), tick=False)
    def test_added_today_auckland_midnight_crossing(self) -> None:
        # UTC 02:00 on 2026-03-29 -> Auckland (UTC+13) = 2026-03-29 15:00 local
        # Auckland midnight = UTC 2026-03-28 11:00
        lo, hi = _range(rewrite_natural_date_keywords("added:today", AUCKLAND), "added")
        assert lo == "2026-03-28T11:00:00Z"
        assert hi == "2026-03-29T11:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_modified_today_utc(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords("modified:today", UTC),
            "modified",
        )
        assert lo == "2026-03-28T00:00:00Z"
        assert hi == "2026-03-29T00:00:00Z"

    @pytest.mark.parametrize(
        ("keyword", "expected_lo", "expected_hi"),
        [
            pytest.param(
                "yesterday",
                "2026-03-27T00:00:00Z",
                "2026-03-28T00:00:00Z",
                id="yesterday",
            ),
            pytest.param(
                "previous week",
                "2026-03-16T00:00:00Z",
                "2026-03-23T00:00:00Z",
                id="previous_week",
            ),
            pytest.param(
                "this month",
                "2026-03-01T00:00:00Z",
                "2026-04-01T00:00:00Z",
                id="this_month",
            ),
            pytest.param(
                "previous month",
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
                id="previous_month",
            ),
            pytest.param(
                "this year",
                "2026-01-01T00:00:00Z",
                "2027-01-01T00:00:00Z",
                id="this_year",
            ),
            pytest.param(
                "previous year",
                "2025-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                id="previous_year",
            ),
        ],
    )
    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_datetime_keywords_utc(
        self,
        keyword: str,
        expected_lo: str,
        expected_hi: str,
    ) -> None:
        # 2026-03-28 is Saturday; weekday()==5 so Monday=2026-03-23
        lo, hi = _range(rewrite_natural_date_keywords(f"added:{keyword}", UTC), "added")
        assert lo == expected_lo
        assert hi == expected_hi

    @time_machine.travel(datetime(2026, 12, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_this_month_december_wraps_to_next_year(self) -> None:
        # December: next month wraps to January of next year
        lo, hi = _range(rewrite_natural_date_keywords("added:this month", UTC), "added")
        assert lo == "2026-12-01T00:00:00Z"
        assert hi == "2027-01-01T00:00:00Z"

    @time_machine.travel(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_last_month_january_wraps_to_previous_year(self) -> None:
        # January: last month wraps back to December of previous year
        lo, hi = _range(
            rewrite_natural_date_keywords("added:previous month", UTC),
            "added",
        )
        assert lo == "2025-12-01T00:00:00Z"
        assert hi == "2026-01-01T00:00:00Z"

    @pytest.mark.parametrize(
        ("query", "expected_lo", "expected_hi"),
        [
            pytest.param(
                'added:"previous quarter"',
                "2026-04-01T00:00:00Z",
                "2026-07-01T00:00:00Z",
                id="quoted_previous_quarter",
            ),
            pytest.param(
                "added:previous month",
                "2026-06-01T00:00:00Z",
                "2026-07-01T00:00:00Z",
                id="bare_previous_month",
            ),
            pytest.param(
                "added:this month",
                "2026-07-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                id="bare_this_month",
            ),
        ],
    )
    @time_machine.travel(datetime(2026, 7, 15, 12, 0, tzinfo=UTC), tick=False)
    def test_legacy_natural_language_aliases(
        self,
        query: str,
        expected_lo: str,
        expected_hi: str,
    ) -> None:
        lo, hi = _range(rewrite_natural_date_keywords(query, UTC), "added")
        assert lo == expected_lo
        assert hi == expected_hi

    def test_unknown_keyword_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown keyword"):
            _datetime_range("bogus_keyword", UTC)


class TestWhooshQueryRewriting:
    """All Whoosh query syntax variants must be rewritten to ISO 8601 before Tantivy parses them."""

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_compact_date_shim_rewrites_to_iso(self) -> None:
        result = rewrite_natural_date_keywords("created:20240115120000", UTC)
        assert "2024-01-15" in result
        assert "20240115120000" not in result

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_relative_range_shim_removes_now(self) -> None:
        result = rewrite_natural_date_keywords("added:[now-7d TO now]", UTC)
        assert "now" not in result
        assert "2026-03-" in result

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_minus_7_days(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords("added:[-7 days to now]", UTC),
            "added",
        )
        assert lo == "2026-03-21T12:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_minus_1_week(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords("added:[-1 week to now]", UTC),
            "added",
        )
        assert lo == "2026-03-21T12:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_minus_1_month_uses_relativedelta(self) -> None:
        # relativedelta(months=1) from 2026-03-28 = 2026-02-28 (not 29)
        lo, hi = _range(
            rewrite_natural_date_keywords("created:[-1 month to now]", UTC),
            "created",
        )
        assert lo == "2026-02-28T12:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_minus_1_year(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords("modified:[-1 year to now]", UTC),
            "modified",
        )
        assert lo == "2025-03-28T12:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_plural_unit_hours(self) -> None:
        lo, hi = _range(
            rewrite_natural_date_keywords("added:[-3 hours to now]", UTC),
            "added",
        )
        assert lo == "2026-03-28T09:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_bracket_case_insensitive(self) -> None:
        result = rewrite_natural_date_keywords("added:[-1 WEEK TO NOW]", UTC)
        assert "now" not in result.lower()
        lo, hi = _range(result, "added")
        assert lo == "2026-03-21T12:00:00Z"
        assert hi == "2026-03-28T12:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False)
    def test_relative_range_swaps_bounds_when_lo_exceeds_hi(self) -> None:
        # [now+1h TO now-1h] has lo > hi before substitution; they must be swapped
        lo, hi = _range(
            rewrite_natural_date_keywords("added:[now+1h TO now-1h]", UTC),
            "added",
        )
        assert lo == "2026-03-28T11:00:00Z"
        assert hi == "2026-03-28T13:00:00Z"

    def test_8digit_created_date_field_always_uses_utc_midnight(self) -> None:
        # created is a DateField: boundaries are always UTC midnight, no TZ offset
        result = rewrite_natural_date_keywords("created:20231201", EASTERN)
        lo, hi = _range(result, "created")
        assert lo == "2023-12-01T00:00:00Z"
        assert hi == "2023-12-02T00:00:00Z"

    def test_8digit_added_datetime_field_converts_local_midnight_to_utc(self) -> None:
        # added is DateTimeField: midnight Dec 1 Eastern (EST = UTC-5) = 05:00 UTC
        result = rewrite_natural_date_keywords("added:20231201", EASTERN)
        lo, hi = _range(result, "added")
        assert lo == "2023-12-01T05:00:00Z"
        assert hi == "2023-12-02T05:00:00Z"

    def test_8digit_modified_datetime_field_converts_local_midnight_to_utc(
        self,
    ) -> None:
        result = rewrite_natural_date_keywords("modified:20231201", EASTERN)
        lo, hi = _range(result, "modified")
        assert lo == "2023-12-01T05:00:00Z"
        assert hi == "2023-12-02T05:00:00Z"

    def test_8digit_invalid_date_passes_through_unchanged(self) -> None:
        assert rewrite_natural_date_keywords("added:20231340", UTC) == "added:20231340"

    def test_compact_14digit_invalid_date_passes_through_unchanged(self) -> None:
        # Month=13 makes datetime() raise ValueError; the token must be left as-is
        assert _rewrite_compact_date("20231300120000") == "20231300120000"


class TestParseUserQuery:
    """parse_user_query runs the full preprocessing pipeline."""

    @pytest.fixture
    def query_index(self) -> tantivy.Index:
        schema = build_schema()
        idx = tantivy.Index(schema, path=None)
        register_tokenizers(idx, "")
        return idx

    def test_returns_tantivy_query(self, query_index: tantivy.Index) -> None:
        assert isinstance(parse_user_query(query_index, "invoice", UTC), tantivy.Query)

    def test_fuzzy_mode_does_not_raise(
        self,
        query_index: tantivy.Index,
        settings,
    ) -> None:
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.5
        assert isinstance(parse_user_query(query_index, "invoice", UTC), tantivy.Query)

    def test_date_rewriting_applied_before_tantivy_parse(
        self,
        query_index: tantivy.Index,
    ) -> None:
        # created:today must be rewritten to an ISO range before Tantivy parses it;
        # if passed raw, Tantivy would reject "today" as an invalid date value
        with time_machine.travel(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), tick=False):
            q = parse_user_query(query_index, "created:today", UTC)
        assert isinstance(q, tantivy.Query)


class TestPassthrough:
    """Queries without field prefixes or unrelated content pass through unchanged."""

    def test_bare_keyword_no_field_prefix_unchanged(self) -> None:
        # Bare 'today' with no field: prefix passes through unchanged
        result = rewrite_natural_date_keywords("bank statement today", UTC)
        assert "today" in result

    def test_unrelated_query_unchanged(self) -> None:
        assert rewrite_natural_date_keywords("title:invoice", UTC) == "title:invoice"


class TestNormalizeQuery:
    """normalize_query expands comma-separated values and collapses whitespace."""

    def test_normalize_expands_comma_separated_tags(self) -> None:
        assert normalize_query("tag:foo,bar") == "tag:foo AND tag:bar"

    def test_normalize_expands_three_values(self) -> None:
        assert normalize_query("tag:foo,bar,baz") == "tag:foo AND tag:bar AND tag:baz"

    def test_normalize_collapses_whitespace(self) -> None:
        assert normalize_query("bank   statement") == "bank statement"

    def test_normalize_no_commas_unchanged(self) -> None:
        assert normalize_query("bank statement") == "bank statement"


class TestPermissionFilter:
    """
    build_permission_filter tests use an in-memory index — no DB access needed.

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
