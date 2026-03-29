from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import time_machine

from documents.search._query import rewrite_natural_date_keywords

pytestmark = pytest.mark.search

UTC = UTC
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
    def test_today(self, tz, expected_lo, expected_hi):
        lo, hi = _range(rewrite_natural_date_keywords("created:today", tz), "created")
        assert lo == expected_lo
        assert hi == expected_hi

    @time_machine.travel(datetime(2026, 3, 28, 3, 0, tzinfo=UTC), tick=False)
    def test_today_auckland_ahead_of_utc(self):
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
                "this_week",
                "2026-03-23T00:00:00Z",
                "2026-03-30T00:00:00Z",
                id="this_week_mon_sun",
            ),
            pytest.param(
                "created",
                "last_week",
                "2026-03-16T00:00:00Z",
                "2026-03-23T00:00:00Z",
                id="last_week",
            ),
            pytest.param(
                "created",
                "this_month",
                "2026-03-01T00:00:00Z",
                "2026-04-01T00:00:00Z",
                id="this_month",
            ),
            pytest.param(
                "created",
                "last_month",
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
                id="last_month",
            ),
            pytest.param(
                "created",
                "this_year",
                "2026-01-01T00:00:00Z",
                "2027-01-01T00:00:00Z",
                id="this_year",
            ),
            pytest.param(
                "created",
                "last_year",
                "2025-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                id="last_year",
            ),
        ],
    )
    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_date_keywords(self, field, keyword, expected_lo, expected_hi):
        # 2026-03-28 is Saturday; Mon-Sun week calculation built into expectations
        query = f"{field}:{keyword}"
        lo, hi = _range(rewrite_natural_date_keywords(query, UTC), field)
        assert lo == expected_lo
        assert hi == expected_hi


class TestDateTimeFields:
    """
    added/modified store full UTC datetimes. Natural keywords must convert
    the local day boundaries to UTC - timezone offset arithmetic IS required.
    """

    @time_machine.travel(datetime(2026, 3, 28, 15, 30, tzinfo=UTC), tick=False)
    def test_added_today_eastern(self):
        # EDT = UTC-4; local midnight 2026-03-28 00:00 EDT = 2026-03-28 04:00 UTC
        lo, hi = _range(rewrite_natural_date_keywords("added:today", EASTERN), "added")
        assert lo == "2026-03-28T04:00:00Z"
        assert hi == "2026-03-29T04:00:00Z"

    @time_machine.travel(datetime(2026, 3, 29, 2, 0, tzinfo=UTC), tick=False)
    def test_added_today_auckland_midnight_crossing(self):
        # UTC 02:00 on 2026-03-29 -> Auckland (UTC+13) = 2026-03-29 15:00 local
        # Auckland midnight = UTC 2026-03-28 11:00
        lo, hi = _range(rewrite_natural_date_keywords("added:today", AUCKLAND), "added")
        assert lo == "2026-03-28T11:00:00Z"
        assert hi == "2026-03-29T11:00:00Z"

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_modified_today_utc(self):
        lo, hi = _range(
            rewrite_natural_date_keywords("modified:today", UTC),
            "modified",
        )
        assert lo == "2026-03-28T00:00:00Z"
        assert hi == "2026-03-29T00:00:00Z"


class TestWhooshCompatShims:
    """Whoosh compact dates and relative ranges must be converted to ISO format."""

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_compact_date_shim_rewrites_to_iso(self):
        # Whoosh compact: YYYYMMDDHHmmss
        result = rewrite_natural_date_keywords("created:20240115120000", UTC)
        assert "2024-01-15" in result
        assert "20240115120000" not in result

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_relative_range_shim_removes_now(self):
        result = rewrite_natural_date_keywords("added:[now-7d TO now]", UTC)
        assert "now" not in result
        assert "2026-03-" in result


class TestPassthrough:
    """Queries without field prefixes or unrelated content pass through unchanged."""

    def test_bare_keyword_no_field_prefix_unchanged(self):
        # Bare 'today' with no field: prefix passes through unchanged
        result = rewrite_natural_date_keywords("bank statement today", UTC)
        assert "today" in result

    def test_unrelated_query_unchanged(self):
        assert rewrite_natural_date_keywords("title:invoice", UTC) == "title:invoice"
