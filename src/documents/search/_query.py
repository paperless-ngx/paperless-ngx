from __future__ import annotations

import re
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

import tantivy
from dateutil.relativedelta import relativedelta
from django.conf import settings

if TYPE_CHECKING:
    from datetime import tzinfo

    from django.contrib.auth.base_user import AbstractBaseUser

_DATE_ONLY_FIELDS = frozenset({"created"})

_DATE_KEYWORDS = frozenset(
    {
        "today",
        "yesterday",
        "this_week",
        "last_week",
        "this_month",
        "last_month",
        "this_year",
        "last_year",
    },
)

_FIELD_DATE_RE = re.compile(
    r"(\w+):(" + "|".join(_DATE_KEYWORDS) + r")\b",
)
_COMPACT_DATE_RE = re.compile(r"\b(\d{14})\b")
_RELATIVE_RANGE_RE = re.compile(
    r"\[now([+-]\d+[dhm])?\s+TO\s+now([+-]\d+[dhm])?\]",
    re.IGNORECASE,
)
# Whoosh-style relative date range: e.g. [-1 week to now], [-7 days to now]
_WHOOSH_REL_RANGE_RE = re.compile(
    r"\[-(?P<n>\d+)\s+(?P<unit>second|minute|hour|day|week|month|year)s?\s+to\s+now\]",
    re.IGNORECASE,
)
# Whoosh-style 8-digit date: field:YYYYMMDD — field-aware so timezone can be applied correctly
_DATE8_RE = re.compile(r"(?P<field>\w+):(?P<date8>\d{8})\b")


def _fmt(dt: datetime) -> str:
    """Format a datetime as an ISO 8601 UTC string for use in Tantivy range queries."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_range(lo: datetime, hi: datetime) -> str:
    """Format a [lo TO hi] range string in ISO 8601 for Tantivy query syntax."""
    return f"[{_fmt(lo)} TO {_fmt(hi)}]"


def _date_only_range(keyword: str, tz: tzinfo) -> str:
    """
    For `created` (DateField): use the local calendar date, converted to
    midnight UTC boundaries. No offset arithmetic — date only.
    """

    today = datetime.now(tz).date()

    if keyword == "today":
        lo = datetime(today.year, today.month, today.day, tzinfo=UTC)
        return _iso_range(lo, lo + timedelta(days=1))
    if keyword == "yesterday":
        y = today - timedelta(days=1)
        lo = datetime(y.year, y.month, y.day, tzinfo=UTC)
        hi = datetime(today.year, today.month, today.day, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == "this_week":
        mon = today - timedelta(days=today.weekday())
        lo = datetime(mon.year, mon.month, mon.day, tzinfo=UTC)
        return _iso_range(lo, lo + timedelta(weeks=1))
    if keyword == "last_week":
        this_mon = today - timedelta(days=today.weekday())
        last_mon = this_mon - timedelta(weeks=1)
        lo = datetime(last_mon.year, last_mon.month, last_mon.day, tzinfo=UTC)
        hi = datetime(this_mon.year, this_mon.month, this_mon.day, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == "this_month":
        lo = datetime(today.year, today.month, 1, tzinfo=UTC)
        if today.month == 12:
            hi = datetime(today.year + 1, 1, 1, tzinfo=UTC)
        else:
            hi = datetime(today.year, today.month + 1, 1, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == "last_month":
        if today.month == 1:
            lo = datetime(today.year - 1, 12, 1, tzinfo=UTC)
        else:
            lo = datetime(today.year, today.month - 1, 1, tzinfo=UTC)
        hi = datetime(today.year, today.month, 1, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == "this_year":
        lo = datetime(today.year, 1, 1, tzinfo=UTC)
        return _iso_range(lo, datetime(today.year + 1, 1, 1, tzinfo=UTC))
    if keyword == "last_year":
        lo = datetime(today.year - 1, 1, 1, tzinfo=UTC)
        return _iso_range(lo, datetime(today.year, 1, 1, tzinfo=UTC))
    raise ValueError(f"Unknown keyword: {keyword}")


def _datetime_range(keyword: str, tz: tzinfo) -> str:
    """
    For `added` / `modified` (DateTimeField, stored as UTC): convert local day
    boundaries to UTC — full offset arithmetic required.
    """

    now_local = datetime.now(tz)
    today = now_local.date()

    def _midnight(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, tzinfo=tz).astimezone(UTC)

    if keyword == "today":
        return _iso_range(_midnight(today), _midnight(today + timedelta(days=1)))
    if keyword == "yesterday":
        y = today - timedelta(days=1)
        return _iso_range(_midnight(y), _midnight(today))
    if keyword == "this_week":
        mon = today - timedelta(days=today.weekday())
        return _iso_range(_midnight(mon), _midnight(mon + timedelta(weeks=1)))
    if keyword == "last_week":
        this_mon = today - timedelta(days=today.weekday())
        last_mon = this_mon - timedelta(weeks=1)
        return _iso_range(_midnight(last_mon), _midnight(this_mon))
    if keyword == "this_month":
        first = today.replace(day=1)
        if today.month == 12:
            next_first = date(today.year + 1, 1, 1)
        else:
            next_first = date(today.year, today.month + 1, 1)
        return _iso_range(_midnight(first), _midnight(next_first))
    if keyword == "last_month":
        this_first = today.replace(day=1)
        if today.month == 1:
            last_first = date(today.year - 1, 12, 1)
        else:
            last_first = date(today.year, today.month - 1, 1)
        return _iso_range(_midnight(last_first), _midnight(this_first))
    if keyword == "this_year":
        return _iso_range(
            _midnight(date(today.year, 1, 1)),
            _midnight(date(today.year + 1, 1, 1)),
        )
    if keyword == "last_year":
        return _iso_range(
            _midnight(date(today.year - 1, 1, 1)),
            _midnight(date(today.year, 1, 1)),
        )
    raise ValueError(f"Unknown keyword: {keyword}")


def _rewrite_compact_date(query: str) -> str:
    """Rewrite Whoosh compact date tokens (14-digit YYYYMMDDHHmmss) to ISO 8601."""

    def _sub(m: re.Match[str]) -> str:
        raw = m.group(1)
        try:
            dt = datetime(
                int(raw[0:4]),
                int(raw[4:6]),
                int(raw[6:8]),
                int(raw[8:10]),
                int(raw[10:12]),
                int(raw[12:14]),
                tzinfo=UTC,
            )
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return str(m.group(0))

    return _COMPACT_DATE_RE.sub(_sub, query)


def _rewrite_relative_range(query: str) -> str:
    """Rewrite Whoosh relative ranges ([now-7d TO now]) to concrete ISO 8601 UTC boundaries."""

    def _sub(m: re.Match[str]) -> str:
        now = datetime.now(UTC)

        def _offset(s: str | None) -> timedelta:
            if not s:
                return timedelta(0)
            sign = 1 if s[0] == "+" else -1
            n, unit = int(s[1:-1]), s[-1]
            return (
                sign
                * {
                    "d": timedelta(days=n),
                    "h": timedelta(hours=n),
                    "m": timedelta(minutes=n),
                }[unit]
            )

        lo, hi = now + _offset(m.group(1)), now + _offset(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return f"[{_fmt(lo)} TO {_fmt(hi)}]"

    return _RELATIVE_RANGE_RE.sub(_sub, query)


def _rewrite_whoosh_relative_range(query: str) -> str:
    """Rewrite Whoosh-style relative date ranges ([-N unit to now]) to ISO 8601.

    Supports: second, minute, hour, day, week, month, year (singular and plural).
    Example: ``added:[-1 week to now]`` → ``added:[2025-01-01T… TO 2025-01-08T…]``
    """
    now = datetime.now(UTC)

    def _sub(m: re.Match[str]) -> str:
        n = int(m.group("n"))
        unit = m.group("unit").lower()
        delta_map: dict[str, timedelta | relativedelta] = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour": timedelta(hours=n),
            "day": timedelta(days=n),
            "week": timedelta(weeks=n),
            "month": relativedelta(months=n),
            "year": relativedelta(years=n),
        }
        lo = now - delta_map[unit]
        return f"[{_fmt(lo)} TO {_fmt(now)}]"

    return _WHOOSH_REL_RANGE_RE.sub(_sub, query)


def _rewrite_8digit_date(query: str, tz: tzinfo) -> str:
    """Rewrite field:YYYYMMDD date tokens to an ISO 8601 day range.

    Runs after ``_rewrite_compact_date`` so 14-digit timestamps are already
    converted and won't spuriously match here.

    For DateField fields (e.g. ``created``) uses UTC midnight boundaries.
    For DateTimeField fields (e.g. ``added``, ``modified``) uses local TZ
    midnight boundaries converted to UTC — matching the ``_datetime_range``
    behaviour for keyword dates.
    """

    def _sub(m: re.Match[str]) -> str:
        field = m.group("field")
        raw = m.group("date8")
        try:
            year, month, day = int(raw[0:4]), int(raw[4:6]), int(raw[6:8])
            d = date(year, month, day)
            if field in _DATE_ONLY_FIELDS:
                lo = datetime(d.year, d.month, d.day, tzinfo=UTC)
                hi = lo + timedelta(days=1)
            else:
                # DateTimeField: use local-timezone midnight → UTC
                lo = datetime(d.year, d.month, d.day, tzinfo=tz).astimezone(UTC)
                hi = datetime(
                    (d + timedelta(days=1)).year,
                    (d + timedelta(days=1)).month,
                    (d + timedelta(days=1)).day,
                    tzinfo=tz,
                ).astimezone(UTC)
            return f"{field}:[{_fmt(lo)} TO {_fmt(hi)}]"
        except ValueError:
            return m.group(0)

    return _DATE8_RE.sub(_sub, query)


def rewrite_natural_date_keywords(query: str, tz: tzinfo) -> str:
    """
    Preprocessing stage 1: rewrite Whoosh compact dates, relative ranges,
    and natural date keywords (field:today etc.) to ISO 8601.
    Bare keywords without a field: prefix pass through unchanged.
    """
    query = _rewrite_compact_date(query)
    query = _rewrite_whoosh_relative_range(query)
    query = _rewrite_8digit_date(query, tz)
    query = _rewrite_relative_range(query)

    def _replace(m: re.Match[str]) -> str:
        field, keyword = m.group(1), m.group(2)
        if field in _DATE_ONLY_FIELDS:
            return f"{field}:{_date_only_range(keyword, tz)}"
        return f"{field}:{_datetime_range(keyword, tz)}"

    return _FIELD_DATE_RE.sub(_replace, query)


# ── normalize_query ──────────────────────────────────────────────────────────


def normalize_query(query: str) -> str:
    """
    Join comma-separated field values with AND, collapse whitespace.
    tag:foo,bar → tag:foo AND tag:bar
    """

    def _expand(m: re.Match[str]) -> str:
        field = m.group(1)
        values = [v.strip() for v in m.group(2).split(",") if v.strip()]
        return " AND ".join(f"{field}:{v}" for v in values)

    query = re.sub(r"(\w+):([^\s\[\]]+(?:,[^\s\[\]]+)+)", _expand, query)
    return re.sub(r" {2,}", " ", query).strip()


# ── build_permission_filter ──────────────────────────────────────────────────

_MAX_U64 = 2**64 - 1  # u64 max — used as inclusive upper bound for "any owner" range


def build_permission_filter(
    schema: tantivy.Schema,
    user: AbstractBaseUser,
) -> tantivy.Query:
    """
    Returns a Query matching documents visible to user:
    - no owner (public)      → owner_id field absent (NULL in Django)
    - owned by user          → owner_id = user.pk
    - shared with user       → viewer_id = user.pk

    Uses disjunction_max_query — boolean Should-only would match all docs.

    NOTE: all integer queries use range_query, not term_query, to avoid the
    unsigned type-detection bug in tantivy-py 0.25 (lib.rs#L190 infers i64
    before u64; confirmed empirically — term_query returns 0 for u64 fields).
    Same root cause as issue #47 (from_dict) but the term_query path unfixed.
    See: https://github.com/quickwit-oss/tantivy-py/blob/f51d851e857385ad2907241fbce8cf08309c3078/src/lib.rs#L190
         https://github.com/quickwit-oss/tantivy-py/issues/47

    NOTE: no_owner uses boolean_query([Must(all), MustNot(range)]) because
    exists_query is not available in 0.25.1. It is present in master and can
    simplify this to MustNot(exists_query("owner_id")) once released.
    See: https://github.com/quickwit-oss/tantivy-py/blob/master/tantivy/tantivy.pyi
    """
    owner_any = tantivy.Query.range_query(
        schema,
        "owner_id",
        tantivy.FieldType.Unsigned,
        1,
        _MAX_U64,
    )
    no_owner = tantivy.Query.boolean_query(
        [
            (tantivy.Occur.Must, tantivy.Query.all_query()),
            (tantivy.Occur.MustNot, owner_any),
        ],
    )
    owned = tantivy.Query.range_query(
        schema,
        "owner_id",
        tantivy.FieldType.Unsigned,
        user.pk,
        user.pk,
    )
    shared = tantivy.Query.range_query(
        schema,
        "viewer_id",
        tantivy.FieldType.Unsigned,
        user.pk,
        user.pk,
    )
    return tantivy.Query.disjunction_max_query([no_owner, owned, shared])


# ── parse_user_query (full pipeline) ─────────────────────────────────────────

DEFAULT_SEARCH_FIELDS = [
    "title",
    "content",
    "correspondent",
    "document_type",
    "tag",
    "note",  # companion text field for notes content (notes JSON for structured: notes.user:x)
    "custom_field",  # companion text field for CF values (custom_fields JSON for structured: custom_fields.name:x)
]
_FIELD_BOOSTS = {"title": 2.0}


def parse_user_query(
    index: tantivy.Index,
    raw_query: str,
    tz: tzinfo,
) -> tantivy.Query:
    """Run the full query preprocessing pipeline: date rewriting → normalisation → Tantivy parse.

    When ADVANCED_FUZZY_SEARCH_THRESHOLD is set (any float), a fuzzy query is blended in as a
    Should clause boosted at 0.1 — keeping fuzzy hits ranked below exact matches. The fuzzy
    query uses edit-distance=1, prefix=True, transposition_cost_one=True on all search fields.
    The threshold float is a post-search minimum-score filter applied in the backend layer, not here.
    """

    query_str = rewrite_natural_date_keywords(raw_query, tz)
    query_str = normalize_query(query_str)

    exact = index.parse_query(
        query_str,
        DEFAULT_SEARCH_FIELDS,
        field_boosts=_FIELD_BOOSTS,
    )

    threshold = getattr(settings, "ADVANCED_FUZZY_SEARCH_THRESHOLD", None)
    if threshold is not None:
        fuzzy = index.parse_query(
            query_str,
            DEFAULT_SEARCH_FIELDS,
            field_boosts=_FIELD_BOOSTS,
            # (prefix=True, distance=1, transposition_cost_one=True) — edit-distance fuzziness
            fuzzy_fields={f: (True, 1, True) for f in DEFAULT_SEARCH_FIELDS},
        )
        return tantivy.Query.boolean_query(
            [
                (tantivy.Occur.Should, exact),
                # 0.1 boost keeps fuzzy hits ranked below exact matches (intentional)
                (tantivy.Occur.Should, tantivy.Query.boost_query(fuzzy, 0.1)),
            ],
        )

    return exact
