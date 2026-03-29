from __future__ import annotations

import re
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import tzinfo

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


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_range(lo: datetime, hi: datetime) -> str:
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
    def _sub(m: re.Match) -> str:
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
            return m.group(0)

    return _COMPACT_DATE_RE.sub(_sub, query)


def _rewrite_relative_range(query: str) -> str:
    def _sub(m: re.Match) -> str:
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


def rewrite_natural_date_keywords(query: str, tz: tzinfo) -> str:
    """
    Preprocessing stage 1: rewrite Whoosh compact dates, relative ranges,
    and natural date keywords (field:today etc.) to ISO 8601.
    Bare keywords without a field: prefix pass through unchanged.
    """
    query = _rewrite_compact_date(query)
    query = _rewrite_relative_range(query)

    def _replace(m: re.Match) -> str:
        field, keyword = m.group(1), m.group(2)
        if field in _DATE_ONLY_FIELDS:
            return f"{field}:{_date_only_range(keyword, tz)}"
        return f"{field}:{_datetime_range(keyword, tz)}"

    return _FIELD_DATE_RE.sub(_replace, query)
