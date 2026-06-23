from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import TypeAlias

import regex
from dateutil.relativedelta import relativedelta

from documents.search._dates import _DATE_KEYWORDS
from documents.search._dates import _DATE_ONLY_FIELDS
from documents.search._dates import _date_only_range
from documents.search._dates import _datetime_range
from documents.search._dates import _field_range_from_dates
from documents.search._dates import _fmt
from documents.search._dates import _precision_bounds
from documents.search._dates import _utc_bounds_for_field

# Compiled regex that matches any known multi-word (or single-word) date keyword
# at the start of a match position, longest alternatives first so "previous week"
# wins over a hypothetical shorter "previous".
_KEYWORD_VALUE_RE = regex.compile(
    "|".join(sorted((regex.escape(k) for k in _DATE_KEYWORDS), key=len, reverse=True)),
    regex.IGNORECASE,
)

if TYPE_CHECKING:
    from datetime import tzinfo

# TODO: this module translates date queries into Tantivy *string* syntax, which
# forces a workaround for something Tantivy's string parser cannot express on
# date fields: open-ended ranges use far-past/far-future string sentinels
# (OPEN_LO/OPEN_HI). These can be replaced with a real tantivy.Query object
# (Query.range_query(..., None) for open bounds) once tantivy-py accepts Python
# datetimes in range_query/term_query on Date fields. That support exists on
# tantivy-py master (PRs #655 + #666) but postdates the pinned 0.26.0 wheel, so
# it is blocked only on a published release > 0.26.0 and a dependency bump.
# (Unparsable dates now raise InvalidDateQuery -> HTTP 400 rather than using a
# no-match string sentinel.)

# Fields that store exact, non-analyzed comma-joined tokens in the index and so
# need explicit comma->AND expansion (Whoosh KEYWORD(commas=True) set).
MULTI_VALUE_FIELDS = frozenset({"tag", "tag_id", "viewer_id"})

# Date fields whose values/ranges get rewritten to RFC3339 Tantivy ranges.
DATE_FIELDS = frozenset({"created", "modified", "added"})

# Field aliases: Whoosh (v2) field names that were renamed in the Tantivy schema.
# Preserved here so v2 queries using the old names continue to work without 400
# errors instead of silently failing. Applied by _render to non-date field tokens.
FIELD_ALIASES: dict[str, str] = {
    "type": "document_type",
    "type_id": "document_type_id",
    "path": "storage_path",
    "path_id": "storage_path_id",
}

# Known schema fields: a comma immediately followed by ``<known>:`` is a clause
# separator. Restricting to known fields prevents URL-like ``http:`` misfires.
KNOWN_FIELDS = frozenset(
    {
        "title",
        "content",
        "correspondent",
        "document_type",
        "type",  # v2 alias -> document_type
        "storage_path",
        "path",  # v2 alias -> storage_path
        "tag",
        "tag_id",
        "correspondent_id",
        "document_type_id",
        "type_id",  # v2 alias -> document_type_id
        "storage_path_id",
        "path_id",  # v2 alias -> storage_path_id
        "owner_id",
        "viewer_id",
        "asn",
        "page_count",
        "num_notes",
        "created",
        "modified",
        "added",
        "original_filename",
        "checksum",
        "notes",
        "custom_fields",
    },
)

_FIELD_RE = regex.compile(r"(?P<field>\w+):")

# Matches the TO separator inside a range bracket. Handles three forms:
#   middle:   "lo TO hi"   (either lo or hi may be empty)
#   trailing: "lo TO"      (open upper bound)
#   leading:  "TO hi"      (open lower bound)
# Bounds MAY contain internal spaces (e.g. "-7 days"), so we use .*? / .+?
# and split on the whitespace-delimited " TO " / " to " separator.
_RANGE_RE = regex.compile(
    r"^\s*(?P<lo>.*?)\s+[Tt][Oo]\s+(?P<hi>.+?)\s*$"
    r"|"
    r"^\s*(?P<lo2>.+?)\s+[Tt][Oo]\s*$"
    r"|"
    r"^\s*[Tt][Oo]\s+(?P<hi2>.+?)\s*$",
)


@dataclass(frozen=True, slots=True)
class FieldValue:
    field: str
    value: str


# Produced by the comma-resolution pass (not by scan()).
@dataclass(frozen=True, slots=True)
class FieldValueList:
    field: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldRange:
    field: str
    open: str
    lo: str
    hi: str
    close: str


# Produced by the comma-resolution pass (not by scan()).
@dataclass(frozen=True, slots=True)
class Comma:
    pass


@dataclass(frozen=True, slots=True)
class Passthrough:
    raw: str


Token: TypeAlias = FieldValue | FieldValueList | FieldRange | Comma | Passthrough

_CLOSE: dict[str, str] = {"[": "]", "{": "}"}


def scan(query: str) -> list[Token]:
    """
    Tokenize a raw query into date/comma-aware tokens, leaving everything else
    as verbatim ``Passthrough`` runs. Non-recursive: finds the first matching
    close bracket/quote. Nested brackets are not valid Tantivy range syntax and
    pass through verbatim on mismatch.
    """
    tokens: list[Token] = []
    buf: list[str] = []  # accumulates passthrough chars
    i, n = 0, len(query)
    while i < n:
        matched = _match_field_token(query, i)
        if matched is None:
            buf.append(query[i])
            i += 1
            continue
        token, i = matched
        _flush(buf, tokens)
        tokens.append(token)
        i = _maybe_comma(query, i, tokens)
    _flush(buf, tokens)
    return tokens


def _flush(buf: list[str], tokens: list[Token]) -> None:
    """Emit any accumulated passthrough characters as a single token."""
    if buf:
        tokens.append(Passthrough("".join(buf)))
        buf.clear()


def _at_word_boundary(query: str, i: int) -> bool:
    """A field token may begin only at the start or after a non-word character."""
    return i == 0 or not (query[i - 1].isalnum() or query[i - 1] == "_")


def _match_field_token(query: str, i: int) -> tuple[Token, int] | None:
    """
    If a known ``field:`` token starts at ``i``, consume it and return
    ``(token, end_index)``; otherwise return None so the caller treats the
    character as passthrough. Handles both ``field:[range]`` and ``field:value``,
    and returns None when the range/value cannot be consumed.
    """
    m = _FIELD_RE.match(query, i)
    if m is None or m.group("field") not in KNOWN_FIELDS:
        return None
    if not _at_word_boundary(query, i):
        return None
    field = m.group("field")
    j = m.end()
    if j < len(query) and query[j] in "[{":
        return _consume_range(query, j, field)
    consumed = _consume_field_value(query, field, j)
    if consumed is None:
        return None
    value, end = consumed
    return FieldValue(field, value), end


def _consume_field_value(query: str, field: str, start: int) -> tuple[str, int] | None:
    """
    Consume a field value starting at ``start``: a multi-word date keyword phrase
    (date fields only), or a bare/quoted value, then absorb any comma-joined
    continuation that is not a clause separator. ``resolve_commas`` later splits a
    multi-value field's joined value into a ``FieldValueList``; for other fields
    the comma stays literal.
    """
    n = len(query)
    consumed = None
    if field in DATE_FIELDS:
        km = _KEYWORD_VALUE_RE.match(query, start)
        if km is not None and (km.end() >= n or query[km.end()] in " \t),"):
            consumed = (km.group(0), km.end())
    if consumed is None:
        consumed = _consume_value(query, start)
    if consumed is None:
        return None
    value, k = consumed
    while k < n and query[k] == ",":
        if _looks_like_known_field(query, k + 1):
            break  # clause separator: left for _maybe_comma to emit a Comma()
        more = _consume_value(query, k + 1)
        if more is None:
            break
        value = f"{value},{more[0]}"
        k = more[1]
    return value, k


def _consume_range(
    query: str,
    start: int,
    field: str,
) -> tuple[FieldRange, int] | None:
    """Consume ``[lo TO hi]`` / ``{lo TO hi}`` from ``start`` (the bracket)."""
    open_br = query[start]
    close_br = _CLOSE[open_br]
    end = query.find(close_br, start + 1)
    if end == -1:
        return None
    inner = query[start + 1 : end]
    m = _RANGE_RE.match(inner)
    if m is not None:
        if m.group("lo") is not None or m.group("hi") is not None:
            # Middle form: "lo TO hi" (either may be empty string)
            lo = (m.group("lo") or "").strip()
            hi = (m.group("hi") or "").strip()
        elif m.group("lo2") is not None:
            # Trailing form: "lo TO"
            lo = m.group("lo2").strip()
            hi = ""
        else:
            # Leading form: "TO hi"
            lo = ""
            hi = (m.group("hi2") or "").strip()
    else:
        lo, hi = inner.strip(), ""
    return FieldRange(field, open_br, lo, hi, close_br), end + 1


def _consume_value(query: str, start: int) -> tuple[str, int] | None:
    """Consume a bare or quoted field value from ``start``, stopping at comma."""
    n = len(query)
    if start >= n or query[start] in " \t":
        return None
    if query[start] in "\"'":
        quote = query[start]
        end = query.find(quote, start + 1)
        if end == -1:
            return None
        return query[start : end + 1], end + 1
    j = start
    while j < n and query[j] not in " \t),":
        j += 1
    return query[start:j], j


def _looks_like_known_field(query: str, pos: int) -> bool:
    """True if a known ``field:`` token starts at ``pos``."""
    m = _FIELD_RE.match(query, pos)
    return bool(m and m.group("field") in KNOWN_FIELDS)


def _maybe_comma(query: str, i: int, tokens: list) -> int:
    """If a clause-separator comma follows at ``i``, emit ``Comma()`` and advance."""
    if i < len(query) and query[i] == "," and _looks_like_known_field(query, i + 1):
        tokens.append(Comma())
        return i + 1
    return i


def resolve_commas(tokens: list) -> list:
    """
    Collapse value-list commas into ``FieldValueList`` and keep clause-separator
    commas as ``Comma``. (Clause-sep commas are already emitted by ``scan`` via
    the value-stop logic; this pass folds value-lists.)
    """
    out: list = []
    for tok in tokens:
        if (
            isinstance(tok, FieldValue)
            and tok.field in MULTI_VALUE_FIELDS
            and "," in tok.value
        ):
            values = tuple(v for v in tok.value.split(",") if v)
            out.append(FieldValueList(tok.field, values))
        else:
            out.append(tok)
    return out


class SearchQueryError(ValueError):
    """
    Base for user-fixable search query errors.

    Carries a message safe to surface to the user (no internal details). The view
    layer catches this and returns an HTTP 400, so any future subclass (unknown
    field, malformed range, wrapped parser errors) gets the same treatment.
    """


class InvalidDateQuery(SearchQueryError):
    """Raised when a date field value or range bound cannot be parsed."""

    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Invalid date value {value!r} for field {field!r}.")


_DIGITS_RE = regex.compile(r"^\d{4}(?:\d{2}){0,2}$")
_ISO_RE = regex.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")


def translate_scalar(field: str, value: str, tz: tzinfo) -> str:
    """Translate a bare date-field value to a Tantivy range string."""
    bare = value.strip("\"'").lower()
    if bare in _DATE_KEYWORDS:
        if field in _DATE_ONLY_FIELDS:
            return f"{field}:{_date_only_range(bare, tz)}"
        return f"{field}:{_datetime_range(bare, tz)}"
    digits = value.replace("-", "")
    if _DIGITS_RE.match(value) or _ISO_RE.match(value):
        bounds = _precision_bounds(digits)
        if bounds is None:
            raise InvalidDateQuery(field, value)
        return _field_range_from_dates(field, bounds[0], bounds[1], tz)
    if regex.fullmatch(r"\d{14}", value):
        try:
            dt = datetime(
                int(value[0:4]),
                int(value[4:6]),
                int(value[6:8]),
                int(value[8:10]),
                int(value[10:12]),
                int(value[12:14]),
                tzinfo=UTC,
            )
        except ValueError:
            raise InvalidDateQuery(field, value) from None
        iso = _fmt(dt)
        return f"{field}:[{iso} TO {iso}]"
    # Unrecognized shape -> tell the user their date is malformed rather than
    # silently matching nothing or emitting invalid Tantivy syntax.
    raise InvalidDateQuery(field, value)


# Open-bound sentinels for date ranges. These far-past/far-future strings allow
# open-ended ranges to be expressed as Tantivy string queries until tantivy-py
# exposes Query.range_query(..., None) on Date fields (see module TODO).
OPEN_LO = "0001-01-01T00:00:00Z"
OPEN_HI = "9999-12-31T23:59:59Z"


# Matches compact now-offset tokens like now-7d, now+1h, now-30m.
_NOW_COMPACT_RE = regex.compile(
    r"^now(?P<sign>[+-])(?P<n>\d+)(?P<unit>[dhm])$",
    regex.IGNORECASE,
)

# Matches "±N <unit>" Whoosh-style offsets (e.g. -7 days, -1 week, +3 hours)
# Unit is singular or plural; sign prefix is mandatory.
_NOW_SPACED_RE = regex.compile(
    r"^(?P<sign>[+-])(?P<n>\d+)\s*"
    r"(?P<unit>second|minute|hour|day|week|month|year)s?$",
    regex.IGNORECASE,
)


def _resolve_relative_bound(token: str) -> datetime | None:
    """
    Resolve a relative bound token to an exact UTC instant, or return None.

    Supported forms:
      - ``now``            -> current UTC instant
      - ``now+/-<n>d/h/m`` -> now +/- timedelta (d=days, h=hours, m=minutes)
      - ``±N <unit>``     -> now +/- delta; month/year use relativedelta
    """
    stripped = token.strip()
    low = stripped.lower()
    now = datetime.now(UTC)

    if low == "now":
        return now

    m = _NOW_COMPACT_RE.match(stripped)
    if m:
        sign = 1 if m.group("sign") == "+" else -1
        n = int(m.group("n"))
        unit = m.group("unit").lower()
        delta = (
            sign
            * {
                "d": timedelta(days=n),
                "h": timedelta(hours=n),
                "m": timedelta(minutes=n),
            }[unit]
        )
        return now + delta

    m = _NOW_SPACED_RE.match(stripped)
    if m:
        sign = 1 if m.group("sign") == "+" else -1
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
        return now - delta_map[unit] if sign == -1 else now + delta_map[unit]

    return None


def _bound_datetimes(
    field: str,
    token: str,
    tz: tzinfo,
) -> tuple[datetime, datetime] | None:
    """
    Return (floor_dt, ceil_dt) UTC datetimes for a single range bound token, or
    None if the token is unparsable. ``now`` and relative offsets resolve to the
    current instant (floor == ceil == that instant; no day-flooring).
    """
    token = token.strip()

    # Try relative/now forms first (before stripping hyphens which would mangle them).
    rel = _resolve_relative_bound(token)
    if rel is not None:
        return rel, rel

    # Full ISO datetime token (contains "T"): parse directly and return an exact
    # instant (floor == ceil). Python 3.11+ datetime.fromisoformat accepts trailing Z.
    if "T" in token:
        try:
            dt = datetime.fromisoformat(token)
            # Ensure timezone-aware UTC result.
            dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
            return dt, dt
        except ValueError:
            return None

    digits = token.replace("-", "")
    bounds = _precision_bounds(digits)
    if bounds is None:
        return None
    start, end = bounds
    return _utc_bounds_for_field(field, start, end, tz)


def _render(tok: Token, tz: tzinfo) -> str:
    """Render a single token back to a Tantivy query string fragment."""
    if isinstance(tok, Passthrough):
        return tok.raw
    if isinstance(tok, Comma):
        return " AND "
    if isinstance(tok, FieldValueList):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        return " AND ".join(f"{field}:{v}" for v in tok.values)
    if isinstance(tok, FieldValue):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        if field in DATE_FIELDS:
            return translate_scalar(field, tok.value, tz)
        return f"{field}:{tok.value}"
    if isinstance(tok, FieldRange):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        if field in DATE_FIELDS:
            return translate_range(field, tok.lo, tok.hi, tz)
        return f"{field}:{tok.open}{tok.lo} TO {tok.hi}{tok.close}"
    return ""  # pragma: no cover


# Post-render operator normalization patterns: collapse repeated whitespace and
# strip spaced/trailing Tantivy boolean operators that would otherwise be invalid.
_MULTI_SPACE_RE = regex.compile(r" {2,}")
_TRAILING_OP_RE = regex.compile(r"\s+[-+]+\s*$")
_SPACED_OP_RE = regex.compile(r"\s+[-+]\s+")


def _normalize_operators(text: str) -> str:
    """
    Collapse multiple spaces, strip trailing dangling operators, and replace
    spaced operators (`` - `` / `` + ``) with a single space.

    Applied only to Passthrough fragments (the rendered output is scanned for
    operator artifacts outside bracketed ranges) via a post-render pass on the
    full rendered string. This preserves date ranges (``[... TO ...]``) verbatim
    while cleaning natural-language separators in the surrounding text.
    """
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _TRAILING_OP_RE.sub("", text).strip()
    text = _SPACED_OP_RE.sub(" ", text).strip()
    return text


def translate_query(raw: str, tz: tzinfo) -> str:
    """Translate a raw Whoosh-style query into Tantivy-compatible syntax."""
    tokens = resolve_commas(scan(raw))
    rendered = "".join(_render(t, tz) for t in tokens)
    return _normalize_operators(rendered)


def translate_range(field: str, lo: str, hi: str, tz: tzinfo) -> str:
    """Translate a date-field ``[lo TO hi]`` range to a Tantivy ISO range string.

    Handles partial-date bounds (YYYY, YYYYMM, YYYYMMDD, ISO dash variants),
    open bounds (empty string -> OPEN_LO/OPEN_HI), ``now``, and reversed ranges
    (swaps tokens before computing floor/ceil so the span is always correct).
    """
    lo_s = lo.strip()
    hi_s = hi.strip()

    # Parse both bounds to (floor, ceil) pairs when present.
    lo_pair: tuple[datetime, datetime] | None = None
    hi_pair: tuple[datetime, datetime] | None = None

    if lo_s:
        lo_pair = _bound_datetimes(field, lo_s, tz)
        if lo_pair is None:
            raise InvalidDateQuery(field, lo_s)
    if hi_s:
        hi_pair = _bound_datetimes(field, hi_s, tz)
        if hi_pair is None:
            raise InvalidDateQuery(field, hi_s)

    # Detect a reversed range: only swap when BOTH bounds are present.
    if lo_pair is not None and hi_pair is not None and lo_pair[0] > hi_pair[0]:
        lo_pair, hi_pair = hi_pair, lo_pair

    lo_iso = _fmt(lo_pair[0]) if lo_pair is not None else OPEN_LO
    hi_iso = _fmt(hi_pair[1]) if hi_pair is not None else OPEN_HI

    return f"{field}:[{lo_iso} TO {hi_iso}]"
