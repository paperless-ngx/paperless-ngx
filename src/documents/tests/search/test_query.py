from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from datetime import tzinfo
from zoneinfo import ZoneInfo

import pytest
import tantivy
import time_machine

from documents.search._query import build_permission_filter
from documents.search._query import normalize_query
from documents.search._query import rewrite_natural_date_keywords
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

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


class TestWhooshCompatShims:
    """Whoosh compact dates and relative ranges must be converted to ISO format."""

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_compact_date_shim_rewrites_to_iso(self) -> None:
        # Whoosh compact: YYYYMMDDHHmmss
        result = rewrite_natural_date_keywords("created:20240115120000", UTC)
        assert "2024-01-15" in result
        assert "20240115120000" not in result

    @time_machine.travel(datetime(2026, 3, 28, 15, 0, tzinfo=UTC), tick=False)
    def test_relative_range_shim_removes_now(self) -> None:
        result = rewrite_natural_date_keywords("added:[now-7d TO now]", UTC)
        assert "now" not in result
        assert "2026-03-" in result


class TestPassthrough:
    """Queries without field prefixes or unrelated content pass through unchanged."""

    def test_bare_keyword_no_field_prefix_unchanged(self) -> None:
        # Bare 'today' with no field: prefix passes through unchanged
        result = rewrite_natural_date_keywords("bank statement today", UTC)
        assert "today" in result

    def test_unrelated_query_unchanged(self) -> None:
        assert rewrite_natural_date_keywords("title:invoice", UTC) == "title:invoice"


# ── Task 6: normalize_query and build_permission_filter ─────────────────────


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
    """build_permission_filter tests use an in-memory index — no DB access needed."""

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

    def test_perm_no_owner_visible_to_any_user(self, perm_index: tantivy.Index) -> None:
        self._add_doc(perm_index, doc_id=1, owner_id=None)
        user = type("U", (), {"pk": 99})()
        perm = build_permission_filter(perm_index.schema, user)  # .schema is a property
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_owned_by_user_is_visible(self, perm_index: tantivy.Index) -> None:
        self._add_doc(perm_index, doc_id=2, owner_id=42)
        user = type("U", (), {"pk": 42})()
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_owned_by_other_not_visible(self, perm_index: tantivy.Index) -> None:
        self._add_doc(perm_index, doc_id=3, owner_id=42)
        user = type("U", (), {"pk": 99})()
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 0

    def test_perm_shared_viewer_is_visible(self, perm_index: tantivy.Index) -> None:
        self._add_doc(perm_index, doc_id=4, owner_id=42, viewer_ids=(99,))
        user = type("U", (), {"pk": 99})()
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1

    def test_perm_only_owned_docs_hidden_from_others(
        self,
        perm_index: tantivy.Index,
    ) -> None:
        self._add_doc(perm_index, doc_id=5, owner_id=10)  # owned by 10
        self._add_doc(perm_index, doc_id=6, owner_id=None)  # unowned
        user = type("U", (), {"pk": 20})()
        perm = build_permission_filter(perm_index.schema, user)
        assert perm_index.searcher().search(perm, limit=10).count == 1  # only unowned
