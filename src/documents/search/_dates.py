from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Final

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


def _fmt(dt: datetime) -> str:
    """Format a datetime as an ISO 8601 UTC string for use in Tantivy range queries."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_range(lo: datetime, hi: datetime) -> str:
    """Format a [lo TO hi] range string in ISO 8601 for Tantivy query syntax."""
    return f"[{_fmt(lo)} TO {_fmt(hi)}]"


def _quarter_start(d: date) -> date:
    """Return the first day of the calendar quarter containing ``d``."""
    return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)


def _midnight(d: date, tz: tzinfo) -> datetime:
    """Convert a calendar date at local-timezone midnight to a UTC datetime."""
    return datetime(d.year, d.month, d.day, tzinfo=tz).astimezone(UTC)


def _keyword_bounds(keyword: str, tz: tzinfo) -> tuple[date, date]:
    """
    Map a relative date keyword to ``(start, exclusive_end)`` calendar dates.

    ``tz`` only determines what "today" is; the caller decides how the returned
    dates become UTC datetime boundaries (date-only vs. local-midnight offset).
    """
    today = datetime.now(tz).date()
    if keyword == _TODAY:
        return today, today + timedelta(days=1)
    if keyword == _YESTERDAY:
        return today - timedelta(days=1), today
    if keyword == _PREVIOUS_WEEK:
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(weeks=1), this_monday
    if keyword == _THIS_MONTH:
        first = today.replace(day=1)
        return first, first + relativedelta(months=1)
    if keyword == _PREVIOUS_MONTH:
        this_first = today.replace(day=1)
        return this_first - relativedelta(months=1), this_first
    if keyword == _THIS_YEAR:
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    if keyword == _PREVIOUS_YEAR:
        return date(today.year - 1, 1, 1), date(today.year, 1, 1)
    if keyword == _PREVIOUS_QUARTER:
        this_quarter = _quarter_start(today)
        return this_quarter - relativedelta(months=3), this_quarter
    raise ValueError(f"Unknown keyword: {keyword}")


def _date_only_range(keyword: str, tz: tzinfo) -> str:
    """
    For `created` (DateField): use the local calendar date, converted to
    midnight UTC boundaries. No offset arithmetic — date only.
    """
    start, end = _keyword_bounds(keyword, tz)
    lo = datetime(start.year, start.month, start.day, tzinfo=UTC)
    hi = datetime(end.year, end.month, end.day, tzinfo=UTC)
    return _iso_range(lo, hi)


def _datetime_range(keyword: str, tz: tzinfo) -> str:
    """
    For `added` / `modified` (DateTimeField, stored as UTC): convert local day
    boundaries to UTC — full offset arithmetic required.
    """
    start, end = _keyword_bounds(keyword, tz)
    return _iso_range(_midnight(start, tz), _midnight(end, tz))


def _precision_bounds(digits: str) -> tuple[date, date] | None:
    """
    Map a 4/6/8-digit date token to (start, exclusive_end) calendar dates.

    YYYY -> whole year, YYYYMM -> whole month, YYYYMMDD -> single day.
    Returns None for any unparsable or out-of-range value (e.g. month 23),
    so callers can emit a no-match clause instead of erroring (Whoosh parity).
    """
    try:
        if len(digits) == 4:
            year = int(digits)
            return date(year, 1, 1), date(year + 1, 1, 1)
        if len(digits) == 6:
            year, month = int(digits[:4]), int(digits[4:6])
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            return start, end
        if len(digits) == 8:
            start = date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
            return start, start + timedelta(days=1)
    except ValueError:
        return None
    return None


def _utc_bounds_for_field(
    field: str,
    start: date,
    end: date,
    tz: tzinfo,
) -> tuple[datetime, datetime]:
    """
    Convert calendar-date bounds to UTC datetimes per the field's storage type.

    For DateField (``created``) the bounds are UTC midnight (no offset). For
    DateTimeField (``added``/``modified``) the bounds are local-tz midnight
    converted to UTC, matching how each field is indexed.
    """
    if field in _DATE_ONLY_FIELDS:
        return (
            datetime(start.year, start.month, start.day, tzinfo=UTC),
            datetime(end.year, end.month, end.day, tzinfo=UTC),
        )
    return (
        datetime(start.year, start.month, start.day, tzinfo=tz).astimezone(UTC),
        datetime(end.year, end.month, end.day, tzinfo=tz).astimezone(UTC),
    )


def _field_range_from_dates(field: str, start: date, end: date, tz: tzinfo) -> str:
    """Build a Tantivy ``field:[lo TO hi]`` ISO range from calendar-date bounds."""
    lo, hi = _utc_bounds_for_field(field, start, end, tz)
    return f"{field}:{_iso_range(lo, hi)}"
