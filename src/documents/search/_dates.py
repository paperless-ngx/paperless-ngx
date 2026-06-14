from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Final

import regex as _regex
from dateutil.relativedelta import relativedelta

if TYPE_CHECKING:
    from datetime import tzinfo

_DATE_ONLY_FIELDS = frozenset({"created"})

_TODAY: Final[str] = "today"
_YESTERDAY: Final[str] = "yesterday"
_PREVIOUS_WEEK: Final[str] = "previous week"
_THIS_MONTH: Final[str] = "this month"
_PREVIOUS_MONTH: Final[str] = "previous month"
_THIS_YEAR: Final[str] = "this year"
_PREVIOUS_YEAR: Final[str] = "previous year"
_PREVIOUS_QUARTER: Final[str] = "previous quarter"

_DATE_KEYWORDS = frozenset(
    {
        _TODAY,
        _YESTERDAY,
        _PREVIOUS_WEEK,
        _THIS_MONTH,
        _PREVIOUS_MONTH,
        _THIS_YEAR,
        _PREVIOUS_YEAR,
        _PREVIOUS_QUARTER,
    },
)

_DATE_KEYWORD_PATTERN = "|".join(
    sorted((_regex.escape(k) for k in _DATE_KEYWORDS), key=len, reverse=True),
)


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

    def _quarter_start(d: date) -> date:
        return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)

    if keyword == _TODAY:
        lo = datetime(today.year, today.month, today.day, tzinfo=UTC)
        return _iso_range(lo, lo + timedelta(days=1))
    if keyword == _YESTERDAY:
        y = today - timedelta(days=1)
        lo = datetime(y.year, y.month, y.day, tzinfo=UTC)
        hi = datetime(today.year, today.month, today.day, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == _PREVIOUS_WEEK:
        this_mon = today - timedelta(days=today.weekday())
        last_mon = this_mon - timedelta(weeks=1)
        lo = datetime(last_mon.year, last_mon.month, last_mon.day, tzinfo=UTC)
        hi = datetime(this_mon.year, this_mon.month, this_mon.day, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == _THIS_MONTH:
        lo = datetime(today.year, today.month, 1, tzinfo=UTC)
        if today.month == 12:
            hi = datetime(today.year + 1, 1, 1, tzinfo=UTC)
        else:
            hi = datetime(today.year, today.month + 1, 1, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == _PREVIOUS_MONTH:
        if today.month == 1:
            lo = datetime(today.year - 1, 12, 1, tzinfo=UTC)
        else:
            lo = datetime(today.year, today.month - 1, 1, tzinfo=UTC)
        hi = datetime(today.year, today.month, 1, tzinfo=UTC)
        return _iso_range(lo, hi)
    if keyword == _THIS_YEAR:
        lo = datetime(today.year, 1, 1, tzinfo=UTC)
        return _iso_range(lo, datetime(today.year + 1, 1, 1, tzinfo=UTC))
    if keyword == _PREVIOUS_YEAR:
        lo = datetime(today.year - 1, 1, 1, tzinfo=UTC)
        return _iso_range(lo, datetime(today.year, 1, 1, tzinfo=UTC))
    if keyword == _PREVIOUS_QUARTER:
        this_quarter = _quarter_start(today)
        last_quarter = this_quarter - relativedelta(months=3)
        lo = datetime(
            last_quarter.year,
            last_quarter.month,
            last_quarter.day,
            tzinfo=UTC,
        )
        hi = datetime(
            this_quarter.year,
            this_quarter.month,
            this_quarter.day,
            tzinfo=UTC,
        )
        return _iso_range(lo, hi)
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

    def _quarter_start(d: date) -> date:
        return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)

    if keyword == _TODAY:
        return _iso_range(_midnight(today), _midnight(today + timedelta(days=1)))
    if keyword == _YESTERDAY:
        y = today - timedelta(days=1)
        return _iso_range(_midnight(y), _midnight(today))
    if keyword == _PREVIOUS_WEEK:
        this_mon = today - timedelta(days=today.weekday())
        last_mon = this_mon - timedelta(weeks=1)
        return _iso_range(_midnight(last_mon), _midnight(this_mon))
    if keyword == _THIS_MONTH:
        first = today.replace(day=1)
        if today.month == 12:
            next_first = date(today.year + 1, 1, 1)
        else:
            next_first = date(today.year, today.month + 1, 1)
        return _iso_range(_midnight(first), _midnight(next_first))
    if keyword == _PREVIOUS_MONTH:
        this_first = today.replace(day=1)
        if today.month == 1:
            last_first = date(today.year - 1, 12, 1)
        else:
            last_first = date(today.year, today.month - 1, 1)
        return _iso_range(_midnight(last_first), _midnight(this_first))
    if keyword == _THIS_YEAR:
        return _iso_range(
            _midnight(date(today.year, 1, 1)),
            _midnight(date(today.year + 1, 1, 1)),
        )
    if keyword == _PREVIOUS_YEAR:
        return _iso_range(
            _midnight(date(today.year - 1, 1, 1)),
            _midnight(date(today.year, 1, 1)),
        )
    if keyword == _PREVIOUS_QUARTER:
        this_quarter = _quarter_start(today)
        last_quarter = this_quarter - relativedelta(months=3)
        return _iso_range(_midnight(last_quarter), _midnight(this_quarter))
    raise ValueError(f"Unknown keyword: {keyword}")
