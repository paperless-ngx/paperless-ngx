from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Final

import regex
import tantivy
from dateutil.relativedelta import relativedelta
from django.conf import settings

from documents.search._normalize import ascii_fold

if TYPE_CHECKING:
    from datetime import tzinfo

    from django.contrib.auth.base_user import AbstractBaseUser

# Maximum seconds any single regex substitution may run.
# Prevents ReDoS on adversarial user-supplied query strings.
_REGEX_TIMEOUT: Final[float] = 1.0

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
    sorted((regex.escape(k) for k in _DATE_KEYWORDS), key=len, reverse=True),
)

_FIELD_DATE_RE = regex.compile(
    rf"""(?P<field>\w+)\s*:\s*(?:
    (?P<quote>["'])(?P<quoted>{_DATE_KEYWORD_PATTERN})(?P=quote)
    |
    (?P<bare>{_DATE_KEYWORD_PATTERN})(?![\w-])
)""",
    regex.IGNORECASE | regex.VERBOSE,
)
_COMPACT_DATE_RE = regex.compile(r"\b(\d{14})\b")
_RELATIVE_RANGE_RE = regex.compile(
    r"\[now([+-]\d+[dhm])?\s+TO\s+now([+-]\d+[dhm])?\]",
    regex.IGNORECASE,
)
# Whoosh-style relative date range: e.g. [-1 week to now], [-7 days to now]
_WHOOSH_REL_RANGE_RE = regex.compile(
    r"\[-(?P<n>\d+)\s+(?P<unit>second|minute|hour|day|week|month|year)s?\s+to\s+now\]",
    regex.IGNORECASE,
)
# Whoosh-style 8-digit date: field:YYYYMMDD — field-aware so timezone can be applied correctly
_DATE8_RE = regex.compile(r"(?P<field>\w+):(?P<date8>\d{8})\b")
_SIMPLE_QUERY_TOKEN_RE = regex.compile(r"\S+")


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


def _rewrite_compact_date(query: str) -> str:
    """Rewrite Whoosh compact date tokens (14-digit YYYYMMDDHHmmss) to ISO 8601."""

    def _sub(m: regex.Match[str]) -> str:
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

    try:
        return _COMPACT_DATE_RE.sub(_sub, query, timeout=_REGEX_TIMEOUT)
    except TimeoutError:  # pragma: no cover
        raise ValueError(
            "Query too complex to process (compact date rewrite timed out)",
        )


def _rewrite_relative_range(query: str) -> str:
    """Rewrite Whoosh relative ranges ([now-7d TO now]) to concrete ISO 8601 UTC boundaries."""

    def _sub(m: regex.Match[str]) -> str:
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

    try:
        return _RELATIVE_RANGE_RE.sub(_sub, query, timeout=_REGEX_TIMEOUT)
    except TimeoutError:  # pragma: no cover
        raise ValueError(
            "Query too complex to process (relative range rewrite timed out)",
        )


def _rewrite_whoosh_relative_range(query: str) -> str:
    """Rewrite Whoosh-style relative date ranges ([-N unit to now]) to ISO 8601.

    Supports: second, minute, hour, day, week, month, year (singular and plural).
    Example: ``added:[-1 week to now]`` → ``added:[2025-01-01T… TO 2025-01-08T…]``
    """
    now = datetime.now(UTC)

    def _sub(m: regex.Match[str]) -> str:
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

    try:
        return _WHOOSH_REL_RANGE_RE.sub(_sub, query, timeout=_REGEX_TIMEOUT)
    except TimeoutError:  # pragma: no cover
        raise ValueError(
            "Query too complex to process (Whoosh relative range rewrite timed out)",
        )


def _rewrite_8digit_date(query: str, tz: tzinfo) -> str:
    """Rewrite field:YYYYMMDD date tokens to an ISO 8601 day range.

    Runs after ``_rewrite_compact_date`` so 14-digit timestamps are already
    converted and won't spuriously match here.

    For DateField fields (e.g. ``created``) uses UTC midnight boundaries.
    For DateTimeField fields (e.g. ``added``, ``modified``) uses local TZ
    midnight boundaries converted to UTC — matching the ``_datetime_range``
    behaviour for keyword dates.
    """

    def _sub(m: regex.Match[str]) -> str:
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

    try:
        return _DATE8_RE.sub(_sub, query, timeout=_REGEX_TIMEOUT)
    except TimeoutError:  # pragma: no cover
        raise ValueError(
            "Query too complex to process (8-digit date rewrite timed out)",
        )


def rewrite_natural_date_keywords(query: str, tz: tzinfo) -> str:
    """
    Rewrite natural date syntax to ISO 8601 format for Tantivy compatibility.

    Performs the first stage of query preprocessing, converting various date
    formats and keywords to ISO 8601 datetime ranges that Tantivy can parse:
    - Compact 14-digit dates (YYYYMMDDHHmmss)
    - Whoosh relative ranges ([-7 days to now], [now-1h TO now+2h])
    - 8-digit dates with field awareness (created:20240115)
    - Natural keywords (field:today, field:"previous quarter", etc.)

    Args:
        query: Raw user query string
        tz: Timezone for converting local date boundaries to UTC

    Returns:
        Query with date syntax rewritten to ISO 8601 ranges

    Note:
        Bare keywords without field prefixes pass through unchanged.
    """
    query = _rewrite_compact_date(query)
    query = _rewrite_whoosh_relative_range(query)
    query = _rewrite_8digit_date(query, tz)
    query = _rewrite_relative_range(query)

    def _replace(m: regex.Match[str]) -> str:
        field = m.group("field")
        keyword = (m.group("quoted") or m.group("bare")).lower()
        if field in _DATE_ONLY_FIELDS:
            return f"{field}:{_date_only_range(keyword, tz)}"
        return f"{field}:{_datetime_range(keyword, tz)}"

    try:
        return _FIELD_DATE_RE.sub(_replace, query, timeout=_REGEX_TIMEOUT)
    except TimeoutError:  # pragma: no cover
        raise ValueError(
            "Query too complex to process (date keyword rewrite timed out)",
        )


def normalize_query(query: str) -> str:
    """
    Normalize query syntax for better search behavior.

    Expands comma-separated field values to explicit AND clauses and
    collapses excessive whitespace for cleaner parsing:
    - tag:foo,bar → tag:foo AND tag:bar
    - multiple spaces → single spaces

    Args:
        query: Query string after date rewriting

    Returns:
        Normalized query string ready for Tantivy parsing
    """

    def _expand(m: regex.Match[str]) -> str:
        field = m.group(1)
        values = [v.strip() for v in m.group(2).split(",") if v.strip()]
        return " AND ".join(f"{field}:{v}" for v in values)

    try:
        query = regex.sub(
            r"(\w+):([^\s\[\]]+(?:,[^\s\[\]]+)+)",
            _expand,
            query,
            timeout=_REGEX_TIMEOUT,
        )
        return regex.sub(r" {2,}", " ", query, timeout=_REGEX_TIMEOUT).strip()
    except TimeoutError:  # pragma: no cover
        raise ValueError("Query too complex to process (normalization timed out)")


_MAX_U64 = 2**64 - 1  # u64 max — used as inclusive upper bound for "any owner" range


def build_permission_filter(
    schema: tantivy.Schema,
    user: AbstractBaseUser,
) -> tantivy.Query:
    """
    Build a query filter for user document permissions.

    Creates a query that matches only documents visible to the specified user
    according to paperless-ngx permission rules:
    - Public documents (no owner) are visible to all users
    - Private documents are visible to their owner
    - Documents explicitly shared with the user are visible

    Args:
        schema: Tantivy schema for field validation
        user: User to check permissions for

    Returns:
        Tantivy query that filters results to visible documents

    Implementation Notes:
        - Uses range_query instead of term_query for owner_id/viewer_id to work
          around a tantivy-py bug where Python ints are inferred as i64, causing
          term_query to return no hits on u64 fields.
          TODO: Replace with term_query once
          https://github.com/quickwit-oss/tantivy-py/pull/642 lands.

        - Uses range_query(owner_id, 1, MAX_U64) as an "owner exists" check
          because exists_query is not yet available in tantivy-py 0.25.
          TODO: Replace with exists_query("owner_id") once that is exposed in
          a tantivy-py release.

        - Uses disjunction_max_query to combine permission clauses with OR logic
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


DEFAULT_SEARCH_FIELDS = [
    "title",
    "content",
    "correspondent",
    "document_type",
    "tag",
]
SIMPLE_SEARCH_FIELDS = ["simple_title", "simple_content"]
TITLE_SEARCH_FIELDS = ["simple_title"]
_FIELD_BOOSTS = {"title": 2.0}
_SIMPLE_FIELD_BOOSTS = {"simple_title": 2.0}


def _build_simple_field_query(
    index: tantivy.Index,
    field: str,
    tokens: list[str],
) -> tantivy.Query:
    patterns = []
    for idx, token in enumerate(tokens):
        escaped = regex.escape(token)
        # For multi-token substring search, only the first token can begin mid-word.
        # Later tokens follow a whitespace boundary in the original query, so anchor
        # them to the start of the next indexed token to reduce false positives like
        # matching "Z-Berichte 16" for the query "Z-Berichte 6".
        if idx == 0:
            patterns.append(f".*{escaped}.*")
        else:
            patterns.append(f"{escaped}.*")
    if len(patterns) == 1:
        query = tantivy.Query.regex_query(index.schema, field, patterns[0])
    else:
        query = tantivy.Query.regex_phrase_query(index.schema, field, patterns)

    boost = _SIMPLE_FIELD_BOOSTS.get(field, 1.0)
    if boost > 1.0:
        return tantivy.Query.boost_query(query, boost)
    return query


def parse_user_query(
    index: tantivy.Index,
    raw_query: str,
    tz: tzinfo,
) -> tantivy.Query:
    """
    Parse user query through the complete preprocessing pipeline.

    Transforms the raw user query through multiple stages:
    1. Date keyword rewriting (today → ISO 8601 ranges)
    2. Query normalization (comma expansion, whitespace cleanup)
    3. Tantivy parsing with field boosts
    4. Optional fuzzy query blending (if ADVANCED_FUZZY_SEARCH_THRESHOLD set)

    Args:
        index: Tantivy index with registered tokenizers
        raw_query: Original user query string
        tz: Timezone for date boundary calculations

    Returns:
        Parsed Tantivy query ready for execution

    Note:
        When ADVANCED_FUZZY_SEARCH_THRESHOLD is configured, adds a low-priority
        fuzzy query as a Should clause (0.1 boost) to catch approximate matches
        while keeping exact matches ranked higher. The threshold value is applied
        as a post-search score filter, not during query construction.
    """

    query_str = rewrite_natural_date_keywords(raw_query, tz)
    query_str = normalize_query(query_str)

    exact = index.parse_query(
        query_str,
        DEFAULT_SEARCH_FIELDS,
        field_boosts=_FIELD_BOOSTS,
    )

    threshold = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD
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


def parse_simple_query(
    index: tantivy.Index,
    raw_query: str,
    fields: list[str],
) -> tantivy.Query:
    """
    Parse a plain-text query using Tantivy over a restricted field set.

    Query string is escaped and normalized to be treated as "simple" text query.
    """
    tokens = [
        ascii_fold(token.lower())
        for token in _SIMPLE_QUERY_TOKEN_RE.findall(raw_query, timeout=_REGEX_TIMEOUT)
    ]
    tokens = [token for token in tokens if token]
    if not tokens:
        return tantivy.Query.empty_query()

    field_queries = [
        (tantivy.Occur.Should, _build_simple_field_query(index, field, tokens))
        for field in fields
    ]
    if len(field_queries) == 1:
        return field_queries[0][1]
    return tantivy.Query.boolean_query(field_queries)


def parse_simple_text_query(
    index: tantivy.Index,
    raw_query: str,
) -> tantivy.Query:
    """
    Parse a plain-text query over title/content for simple search inputs.
    """

    return parse_simple_query(index, raw_query, SIMPLE_SEARCH_FIELDS)


def parse_simple_title_query(
    index: tantivy.Index,
    raw_query: str,
) -> tantivy.Query:
    """
    Parse a plain-text query over the title field only.
    """

    return parse_simple_query(index, raw_query, TITLE_SEARCH_FIELDS)
