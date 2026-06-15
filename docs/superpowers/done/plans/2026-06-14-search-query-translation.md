# Whoosh→Tantivy Query Translation Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the order-dependent regex stack in `search/_query.py` with a structural, context-aware translation layer that eliminates the date- and comma-class HTTP 400s while matching verified Whoosh v2 semantics.

**Architecture:** A flat, depth-aware scanner tokenizes the raw query into `FieldValue` / `FieldValueList` / `FieldRange` / `Comma` / `Passthrough` tokens; a single `translate_date_value` shape-dispatch converts date tokens to RFC3339 Tantivy ranges; comma tokens resolve to AND / value-list / literal; everything else passes through to Tantivy untouched. Output is a string handed to `index.parse_query` (Phase 1). Pure date math lives in a new dependency-free `_dates.py`.

**Tech Stack:** Python 3.11+, `regex` module, Tantivy 0.26.0 (`tantivy-py`), Django, pytest (`-m search` marker).

**Reference spec:** `docs/superpowers/specs/2026-06-14-search-query-translation-design.md`. Empirical ground truth: `SEARCH_TANTIVY_WHOOSH_COMPAT.md`.

**Conventions:** ruff (line length 88, double quotes, single-line isort). Run focused tests with `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" <path> -v`. The `--override-ini` drops coverage/xdist for fast iteration.

---

## File Structure

- **Create `src/documents/search/_dates.py`** — pure date-boundary helpers (moved from `_query.py`) + new partial-date precision helpers. No Django/app imports.
- **Create `src/documents/search/_translate.py`** — token dataclasses, `scan()`, `_resolve_commas()`, `translate_date_value()`, `translate_query()`.
- **Modify `src/documents/search/_query.py`** — re-export helpers from `_dates`; make `rewrite_natural_date_keywords`/`normalize_query` delegate; route `parse_user_query` through `translate_query` with a safety net.
- **Create `src/documents/tests/search/test_translate.py`** — all new unit + golden + parse-acceptance tests.
- **Modify `src/documents/tests/search/test_api_search.py`** (or nearest existing search-API test module) — end-to-end 400→200 tests. Confirm the exact module name first (see Task 8).

---

## Task 1: Extract date helpers into `_dates.py` (no behavior change)

**Files:**

- Create: `src/documents/search/_dates.py`
- Modify: `src/documents/search/_query.py` (remove the moved helpers, add re-export)
- Test: existing `src/documents/tests/search/test_query.py` must stay green.

- [ ] **Step 1: Create `_dates.py` by moving the helpers verbatim**

Move these symbols out of `_query.py` into a new `src/documents/search/_dates.py`, unchanged: the constants `_DATE_ONLY_FIELDS`, the eight `_*` keyword constants, `_DATE_KEYWORDS`, `_DATE_KEYWORD_PATTERN`, and the functions `_fmt`, `_iso_range`, `_date_only_range`, `_datetime_range`. Header of the new file:

```python
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

# ... (moved constants and functions verbatim) ...
```

- [ ] **Step 2: Re-export from `_query.py` for backward-compatible imports**

At the top of `_query.py`, after the existing imports, add:

```python
from documents.search._dates import _DATE_ONLY_FIELDS
from documents.search._dates import _date_only_range
from documents.search._dates import _datetime_range
from documents.search._dates import _fmt
from documents.search._dates import _iso_range
```

Keep `_query.py`'s remaining regex rewriters as-is for now (they still reference these names, now imported). Remove the now-duplicated definitions from `_query.py`.

- [ ] **Step 3: Run the existing search tests to confirm no behavior change**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_query.py -v`
Expected: PASS (same set as before; `TestCreatedDateField`/`TestDateTimeFields` import `_date_only_range`/`_datetime_range` from `_query` and still resolve via re-export).

- [ ] **Step 4: Commit**

```bash
git add src/documents/search/_dates.py src/documents/search/_query.py
git commit -m "Refactor: extract search date helpers into _dates.py"
```

---

## Task 2: Partial-date precision helpers in `_dates.py`

**Files:**

- Modify: `src/documents/search/_dates.py`
- Test: `src/documents/tests/search/test_translate.py` (new)

- [ ] **Step 1: Write the failing test**

Create `src/documents/tests/search/test_translate.py`:

```python
import pytest

from documents.search._dates import _precision_bounds


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py -v`
Expected: FAIL with `ImportError: cannot import name '_precision_bounds'`.

- [ ] **Step 3: Implement `_precision_bounds` in `_dates.py`**

```python
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
```

- [ ] **Step 4: Add `_field_range_from_dates` helper (used by the translator)**

```python
def _field_range_from_dates(field: str, start: date, end: date, tz: tzinfo) -> str:
    """
    Build a Tantivy ``field:[lo TO hi]`` ISO range from calendar-date bounds.

    For DateField (``created``) the bounds are UTC midnight (no offset). For
    DateTimeField (``added``/``modified``) the bounds are local-tz midnight
    converted to UTC, matching how each field is indexed.
    """
    if field in _DATE_ONLY_FIELDS:
        lo = datetime(start.year, start.month, start.day, tzinfo=UTC)
        hi = datetime(end.year, end.month, end.day, tzinfo=UTC)
    else:
        lo = datetime(start.year, start.month, start.day, tzinfo=tz).astimezone(UTC)
        hi = datetime(end.year, end.month, end.day, tzinfo=tz).astimezone(UTC)
    return f"{field}:{_iso_range(lo, hi)}"
```

- [ ] **Step 5: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_dates.py src/documents/tests/search/test_translate.py
git commit -m "Feature: partial-date precision helpers for query translation"
```

---

## Task 3: Token model + `scan()` for fields, ranges, passthrough

**Files:**

- Create: `src/documents/search/_translate.py`
- Test: `src/documents/tests/search/test_translate.py`

This task handles `FieldValue`, `FieldRange`, and `Passthrough` only. Commas and value-lists come in Task 4.

- [ ] **Step 1: Write the failing test**

Append to `test_translate.py`:

```python
from documents.search._translate import FieldRange
from documents.search._translate import FieldValue
from documents.search._translate import Passthrough
from documents.search._translate import scan


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

    def test_open_range(self):
        assert scan("created:[2020 to]") == [
            FieldRange("created", "[", "2020", "", "]"),
        ]
        assert scan("created:[to 2020]") == [
            FieldRange("created", "[", "", "2020", "]"),
        ]

    def test_comma_inside_range_not_split(self):
        # No depth-0 comma here; the whole thing is one range token.
        toks = scan("created:[2020 TO 2021]")
        assert len(toks) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestScan -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError`.

- [ ] **Step 3: Implement the token model and scanner core**

Create `src/documents/search/_translate.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING

import regex

if TYPE_CHECKING:
    from datetime import tzinfo

# Fields that store exact, non-analyzed comma-joined tokens in the index and so
# need explicit comma->AND expansion (Whoosh KEYWORD(commas=True) set).
MULTI_VALUE_FIELDS = frozenset({"tag", "tag_id", "viewer_id"})

# Date fields whose values/ranges get rewritten to RFC3339 Tantivy ranges.
DATE_FIELDS = frozenset({"created", "modified", "added"})

# Known schema fields: a comma immediately followed by ``<known>:`` is a clause
# separator. Restricting to known fields prevents URL-like ``http:`` misfires.
KNOWN_FIELDS = frozenset(
    {
        "title",
        "content",
        "correspondent",
        "document_type",
        "type",
        "storage_path",
        "tag",
        "tag_id",
        "correspondent_id",
        "document_type_id",
        "storage_path_id",
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


@dataclass(frozen=True)
class FieldValue:
    field: str
    value: str


@dataclass(frozen=True)
class FieldValueList:
    field: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class FieldRange:
    field: str
    open: str
    lo: str
    hi: str
    close: str


@dataclass(frozen=True)
class Comma:
    pass


@dataclass(frozen=True)
class Passthrough:
    raw: str


Token = "FieldValue | FieldValueList | FieldRange | Comma | Passthrough"

_CLOSE = {"[": "]", "{": "}"}


def scan(query: str) -> list:
    """
    Tokenize a raw query into date/comma-aware tokens, leaving everything else
    as verbatim ``Passthrough`` runs. Depth-aware over ``[]``/``{}`` and quotes.
    """
    tokens: list = []
    buf: list[str] = []  # accumulates passthrough chars
    i, n = 0, len(query)

    def flush() -> None:
        if buf:
            tokens.append(Passthrough("".join(buf)))
            buf.clear()

    while i < n:
        ch = query[i]
        # A field token can begin only at a word boundary outside any value.
        m = _FIELD_RE.match(query, i)
        if m and (i == 0 or not query[i - 1].isalnum() and query[i - 1] != "_"):
            field = m.group("field")
            j = m.end()
            if j < n and query[j] in "[{":
                rng = _consume_range(query, j, field)
                if rng is not None:
                    token, i = rng
                    flush()
                    tokens.append(token)
                    continue
            else:
                val = _consume_value(query, j)
                if val is not None:
                    value, i = val
                    flush()
                    tokens.append(FieldValue(field, value))
                    continue
        buf.append(ch)
        i += 1

    flush()
    return tokens


def _consume_range(query: str, start: int, field: str):
    """Consume ``[lo TO hi]`` / ``{lo TO hi}`` from ``start`` (the bracket)."""
    open_br = query[start]
    close_br = _CLOSE[open_br]
    end = query.find(close_br, start + 1)
    if end == -1:
        return None
    inner = query[start + 1 : end]
    parts = regex.split(r"\s+TO\s+", inner, maxsplit=1, flags=regex.IGNORECASE)
    if len(parts) == 2:
        lo, hi = parts[0].strip(), parts[1].strip()
    else:
        lo, hi = inner.strip(), ""
    return FieldRange(field, open_br, lo, hi, close_br), end + 1


def _consume_value(query: str, start: int):
    """Consume a bare or quoted field value from ``start``."""
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
    while j < n and query[j] not in " \t)":
        j += 1
    return query[start:j], j
```

> **Note for the implementer:** the comma-stops-value behavior is intentionally
> deferred to Task 4. In this task a value like `tag:foo,bar` will scan as a
> single `FieldValue("tag", "foo,bar")`; Task 4's tests pin the final behavior.

- [ ] **Step 4: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestScan -v`
Expected: PASS. If a case fails, fix `scan()` to satisfy the test (the tests are the spec).

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_translate.py
git commit -m "Feature: query scanner for field/range/passthrough tokens"
```

---

## Task 4: Comma resolution — value-lists and clause separators

**Files:**

- Modify: `src/documents/search/_translate.py`
- Test: `src/documents/tests/search/test_translate.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from documents.search._translate import Comma
from documents.search._translate import FieldValueList
from documents.search._translate import resolve_commas


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestCommaResolution -v`
Expected: FAIL (`resolve_commas` undefined, and current `scan` swallows commas into values).

- [ ] **Step 3: Make `_consume_value` comma-aware and add `resolve_commas`**

Update `_consume_value` so a value stops at a depth-0 comma **only** when that comma is a clause separator or a value-list separator; otherwise the comma stays in the value. Implement this by splitting value consumption in two stages: first consume up to whitespace/`)`/comma; then, in `scan`, when the next char is `,`, decide using the field and what follows.

Replace the field-handling branch in `scan()` and add the resolver:

```python
def _consume_value(query: str, start: int):
    """Consume a value, stopping at whitespace, ``)``, or a comma."""
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
```

Now update `scan()`'s comma handling: after consuming a `FieldValue`, if the next char is `,`, decide:

- if `field in MULTI_VALUE_FIELDS` and the char after the comma is a bare term (no `:` field, not a bracket): keep consuming `,term` into the value (value-list, folded later);
- elif the comma is a clause separator (followed by a known `field:`): emit the `FieldValue`, then a `Comma` token, and continue after the comma;
- else: the comma is literal — append it to the value and keep going.

Implement with a post-value loop in `scan` (replace the `FieldValue` emit branch):

```python
                val = _consume_value(query, j)
                if val is not None:
                    value, k = val
                    # Handle trailing comma semantics.
                    while k < n and query[k] == ",":
                        nxt = k + 1
                        if field in MULTI_VALUE_FIELDS and not _looks_like_known_field(
                            query, nxt
                        ) and (nxt >= n or query[nxt] not in "[{ \t),"):
                            more = _consume_value(query, nxt)
                            if more is None:
                                break
                            value = f"{value},{more[0]}"
                            k = more[1]
                            continue
                        break
                    flush()
                    tokens.append(FieldValue(field, value))
                    i = k
                    if i < n and query[i] == "," and _looks_like_known_field(
                        query, i + 1
                    ):
                        tokens.append(Comma())
                        i += 1
                    continue
```

Also handle the clause-separator comma that follows a `FieldRange` or quoted value. After emitting a `FieldRange` (in the range branch) or a quoted `FieldValue`, add the same post-emit check: if `query[i] == ","` and `_looks_like_known_field(query, i+1)`, emit `Comma()` and advance. Factor this into a helper:

```python
def _maybe_comma(query: str, i: int, tokens: list) -> int:
    if i < len(query) and query[i] == "," and _looks_like_known_field(query, i + 1):
        tokens.append(Comma())
        return i + 1
    return i
```

Call `i = _maybe_comma(query, i, tokens)` right after appending a `FieldRange` and after appending a quoted `FieldValue`.

> **Implementer note:** the comma rules are subtle. Treat the Task-4 tests as
> the contract and iterate `scan`/`resolve_commas` until all pass. Add a test
> for `correspondent:"A B",created:[2020 TO 2021]` (clause-sep after a quote)
> and `http://example.com/a,b` (must remain a single `Passthrough`, since
> `http` is not a known field — the comma stays literal).

- [ ] **Step 4: Add the two extra cases to the test**

```python
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
```

- [ ] **Step 5: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestCommaResolution -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_translate.py
git commit -m "Feature: comma resolution (value-list vs clause separator)"
```

---

## Task 5: `translate_date_value` — scalar values

**Files:**

- Modify: `src/documents/search/_translate.py`
- Test: `src/documents/tests/search/test_translate.py`

- [ ] **Step 1: Write the failing test (verified ground-truth rows)**

```python
from zoneinfo import ZoneInfo

from documents.search._translate import NO_MATCH
from documents.search._translate import translate_scalar

UTC_TZ = ZoneInfo("UTC")


@pytest.mark.search
class TestTranslateScalar:
    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("created", "2020", "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]"),
            ("created", "202003", "created:[2020-03-01T00:00:00Z TO 2020-04-01T00:00:00Z]"),
            ("created", "20200115", "created:[2020-01-15T00:00:00Z TO 2020-01-16T00:00:00Z]"),
            ("created", "2020-01-15", "created:[2020-01-15T00:00:00Z TO 2020-01-16T00:00:00Z]"),
            ("created", "2020-03", "created:[2020-03-01T00:00:00Z TO 2020-04-01T00:00:00Z]"),
        ],
    )
    def test_partial_and_iso_dates(self, field, value, expected):
        assert translate_scalar(field, value, UTC_TZ) == expected

    def test_invalid_date_is_no_match(self):
        assert translate_scalar("created", "202023", UTC_TZ) == NO_MATCH

    def test_keyword_delegates(self):
        # keyword path produces a range; just assert it is a created range
        out = translate_scalar("created", "today", UTC_TZ)
        assert out.startswith("created:[") and out.endswith("]")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateScalar -v`
Expected: FAIL (`translate_scalar`, `NO_MATCH` undefined).

- [ ] **Step 3: Implement `translate_scalar` and `NO_MATCH`**

Add to `_translate.py`:

```python
from documents.search._dates import _DATE_KEYWORDS
from documents.search._dates import _date_only_range
from documents.search._dates import _datetime_range
from documents.search._dates import _field_range_from_dates
from documents.search._dates import _precision_bounds

# A valid Tantivy clause that parses but matches nothing (degenerate range on a
# date field). Used for unparsable dates, matching Whoosh's NullQuery.
NO_MATCH = "created:[9999-12-31T23:59:59Z TO 9999-12-31T23:59:59Z]"

_DIGITS_RE = regex.compile(r"^\d{4}(?:\d{2}){0,2}$")
_ISO_RE = regex.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")


def translate_scalar(field: str, value: str, tz: tzinfo) -> str:
    """Translate a bare date-field value to a Tantivy range string."""
    bare = value.strip("\"'").lower()
    if bare in _DATE_KEYWORDS:
        if field in DATE_FIELDS and field == "created":
            return f"{field}:{_date_only_range(bare, tz)}"
        return f"{field}:{_datetime_range(bare, tz)}"
    digits = value.replace("-", "")
    if _DIGITS_RE.match(value) or _ISO_RE.match(value):
        bounds = _precision_bounds(digits)
        if bounds is None:
            return NO_MATCH
        return _field_range_from_dates(field, bounds[0], bounds[1], tz)
    # Unrecognized shape -> no-match rather than a Tantivy 400 (Whoosh parity).
    return NO_MATCH
```

> **Implementer note:** the `created` vs `added`/`modified` keyword split reuses
> the existing `_date_only_range`/`_datetime_range`. Use `_DATE_ONLY_FIELDS`
> from `_dates` instead of the literal `== "created"` if you prefer; behavior is
> identical for the current field set.

- [ ] **Step 4: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateScalar -v`
Expected: PASS.

- [ ] **Step 5: Verify the NO_MATCH string actually parses in Tantivy**

Run:

```bash
cd src && PAPERLESS_SECRET_KEY=ci uv run python -c "
import django, os, tempfile
os.environ.setdefault('DJANGO_SETTINGS_MODULE','paperless.settings'); django.setup()
import tantivy
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers
from documents.search._translate import NO_MATCH
from documents.search._query import DEFAULT_SEARCH_FIELDS, _FIELD_BOOSTS
idx = tantivy.Index(build_schema(), path=tempfile.mkdtemp()); register_tokenizers(idx,'english')
idx.parse_query(NO_MATCH, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
print('NO_MATCH parses OK')
"
```

Expected: `NO_MATCH parses OK`. If it raises, change `NO_MATCH` to a form that parses (e.g. an equal-bound inclusive range is valid; if not, use `[9999-12-31T23:59:59Z TO 9999-12-31T23:59:58Z]` only if Tantivy tolerates reversed — otherwise keep equal bounds).

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_translate.py
git commit -m "Feature: scalar date-value translation with no-match fallback"
```

---

## Task 6: `translate_date_value` — ranges (partial / now / open / reversed)

**Files:**

- Modify: `src/documents/search/_translate.py`
- Test: `src/documents/tests/search/test_translate.py`

- [ ] **Step 1: Write the failing test**

```python
from documents.search._translate import OPEN_HI
from documents.search._translate import OPEN_LO
from documents.search._translate import translate_range


@pytest.mark.search
class TestTranslateRange:
    @pytest.mark.parametrize(
        ("lo", "hi", "expected"),
        [
            ("2005", "2009", "created:[2005-01-01T00:00:00Z TO 2010-01-01T00:00:00Z]"),
            ("202001", "202006", "created:[2020-01-01T00:00:00Z TO 2020-07-01T00:00:00Z]"),
            ("20200101", "20201231", "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]"),
            ("2020-01-01", "2020-12-31", "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]"),
        ],
    )
    def test_absolute_ranges(self, lo, hi, expected):
        assert translate_range("created", lo, hi, UTC_TZ) == expected

    def test_reversed_swaps(self):
        assert translate_range("created", "2009", "2005", UTC_TZ) == (
            "created:[2005-01-01T00:00:00Z TO 2010-01-01T00:00:00Z]"
        )

    def test_open_upper(self):
        out = translate_range("created", "2020", "", UTC_TZ)
        assert out == f"created:[2020-01-01T00:00:00Z TO {OPEN_HI}]"

    def test_open_lower(self):
        out = translate_range("created", "", "2020", UTC_TZ)
        assert out == f"created:[{OPEN_LO} TO 2021-01-01T00:00:00Z]"

    def test_invalid_bound_is_no_match(self):
        assert translate_range("created", "202023", "2025", UTC_TZ) == NO_MATCH
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateRange -v`
Expected: FAIL.

- [ ] **Step 3: Implement `translate_range`, `OPEN_LO`, `OPEN_HI`**

```python
from datetime import UTC
from datetime import datetime

from documents.search._dates import _DATE_ONLY_FIELDS
from documents.search._dates import _fmt

OPEN_LO = "0001-01-01T00:00:00Z"
OPEN_HI = "9999-12-31T23:59:59Z"


def _bound_datetimes(field: str, token: str, tz: tzinfo):
    """
    Return (floor_dt, ceil_dt) UTC datetimes for a single range bound token, or
    None if the token is unparsable. ``now`` resolves to the current instant.
    """
    token = token.strip()
    if token.lower() == "now":
        now = datetime.now(UTC)
        return now, now
    digits = token.replace("-", "")
    bounds = _precision_bounds(digits)
    if bounds is None:
        return None
    start, end = bounds
    if field in _DATE_ONLY_FIELDS:
        lo = datetime(start.year, start.month, start.day, tzinfo=UTC)
        hi = datetime(end.year, end.month, end.day, tzinfo=UTC)
    else:
        lo = datetime(start.year, start.month, start.day, tzinfo=tz).astimezone(UTC)
        hi = datetime(end.year, end.month, end.day, tzinfo=tz).astimezone(UTC)
    return lo, hi


def translate_range(field: str, lo: str, hi: str, tz: tzinfo) -> str:
    """Translate a date-field ``[lo TO hi]`` range to a Tantivy ISO range."""
    lo_s = lo.strip()
    hi_s = hi.strip()

    lo_iso = OPEN_LO
    hi_iso = OPEN_HI

    if lo_s:
        b = _bound_datetimes(field, lo_s, tz)
        if b is None:
            return NO_MATCH
        lo_iso = _fmt(b[0])  # floor
    if hi_s:
        b = _bound_datetimes(field, hi_s, tz)
        if b is None:
            return NO_MATCH
        hi_iso = _fmt(b[1])  # ceil (exclusive end / start of next period)

    # Reversed explicit range: swap so it spans the intended window.
    if lo_s and hi_s and lo_iso > hi_iso:
        lo_iso, hi_iso = hi_iso, lo_iso
    return f"{field}:[{lo_iso} TO {hi_iso}]"
```

> **Note:** for `now` bounds, floor==ceil==the instant, so `[20200101 TO now]`
> uses `floor(20200101)`..`now`. Reversed-swap uses ISO string comparison, which
> is correct for RFC3339 `...Z` values (lexicographic == chronological).

- [ ] **Step 4: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateRange -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_translate.py
git commit -m "Feature: date range translation incl. open-ended and reversed"
```

---

## Task 7: `translate_query` — full pipeline + parse-acceptance

**Files:**

- Modify: `src/documents/search/_translate.py`
- Test: `src/documents/tests/search/test_translate.py`

- [ ] **Step 1: Write the failing test (golden cases + parse-acceptance)**

```python
import tempfile

import tantivy

from documents.search._query import DEFAULT_SEARCH_FIELDS
from documents.search._query import _FIELD_BOOSTS
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers
from documents.search._translate import translate_query


@pytest.fixture(scope="module")
def index():
    idx = tantivy.Index(build_schema(), path=tempfile.mkdtemp())
    register_tokenizers(idx, "english")
    return idx


@pytest.mark.search
class TestTranslateQuery:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("created:2020", "created:[2020-01-01T00:00:00Z TO 2021-01-01T00:00:00Z]"),
            ("tag:foo,bar", "tag:foo AND tag:bar"),
            ("tag:foo,type:bar", "tag:foo AND type:bar"),
            (
                "created:[2020 TO 2021],added:[2022 TO 2023]",
                "created:[2020-01-01T00:00:00Z TO 2022-01-01T00:00:00Z] AND "
                "added:[2022-01-01T00:00:00Z TO 2024-01-01T00:00:00Z]",
            ),
            ("correspondent:foo,bar", "correspondent:foo,bar"),
        ],
    )
    def test_golden(self, raw, expected):
        assert translate_query(raw, UTC_TZ) == expected

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
            "created:202023",
            "bank statement",
        ],
    )
    def test_parse_acceptance(self, index, raw):
        translated = translate_query(raw, UTC_TZ)
        # Must not raise:
        index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateQuery -v`
Expected: FAIL (`translate_query` not yet assembled / recombination missing).

- [ ] **Step 3: Implement `translate_query` (recombination)**

```python
def _render(tokens: list, tz: tzinfo) -> str:
    parts: list[str] = []
    for tok in tokens:
        if isinstance(tok, Passthrough):
            parts.append(tok.raw)
        elif isinstance(tok, Comma):
            parts.append(" AND ")
        elif isinstance(tok, FieldValueList):
            parts.append(" AND ".join(f"{tok.field}:{v}" for v in tok.values))
        elif isinstance(tok, FieldValue):
            if tok.field in DATE_FIELDS:
                parts.append(translate_scalar(tok.field, tok.value, tz))
            else:
                parts.append(f"{tok.field}:{tok.value}")
        elif isinstance(tok, FieldRange):
            if tok.field in DATE_FIELDS:
                parts.append(translate_range(tok.field, tok.lo, tok.hi, tz))
            else:
                parts.append(f"{tok.field}:{tok.open}{tok.lo} TO {tok.hi}{tok.close}")
    return "".join(parts)


def translate_query(raw: str, tz: tzinfo) -> str:
    """Translate a raw Whoosh-style query into Tantivy-compatible syntax."""
    tokens = resolve_commas(scan(raw))
    return _render(tokens, tz)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_translate.py::TestTranslateQuery -v`
Expected: PASS. Iterate `scan`/`resolve_commas`/`_render` until all golden + parse-acceptance cases pass.

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_translate.py
git commit -m "Feature: assemble translate_query pipeline with parse-acceptance tests"
```

---

## Task 8: Wire into `parse_user_query`, delegate old functions, end-to-end test

**Files:**

- Modify: `src/documents/search/_query.py`
- Test: existing `test_query.py`; new end-to-end test in the search-API test module.

- [ ] **Step 1: Route `parse_user_query` through `translate_query` with a safety net**

In `_query.py`, import and use the new pipeline:

```python
from documents.search._translate import translate_query
```

Replace the first two lines of `parse_user_query` body:

```python
    try:
        query_str = translate_query(raw_query, tz)
    except Exception:  # pragma: no cover - defensive
        logger.warning("Query translation failed; using raw query", exc_info=True)
        query_str = raw_query
```

(Ensure a module-level `logger = logging.getLogger("paperless.search")` exists; add it if missing.)

- [ ] **Step 2: Delegate the old functions**

Replace the bodies of `rewrite_natural_date_keywords` and `normalize_query` so they route through the new pipeline while preserving their existing tested outputs. Because the new pipeline does both date-rewriting and normalization in one pass, make `normalize_query` the full pipeline and `rewrite_natural_date_keywords` a no-op-preserving shim:

```python
def rewrite_natural_date_keywords(query: str, tz: tzinfo) -> str:
    # Back-compat shim: date rewriting now happens inside translate_query.
    # Kept (with its tests) until callers/tests migrate to _translate.
    from documents.search._translate import translate_query

    return translate_query(query, tz)


def normalize_query(query: str) -> str:
    # Back-compat shim: comma/operator normalization now happens in translate_query.
    from zoneinfo import ZoneInfo

    from documents.search._translate import translate_query

    return translate_query(query, ZoneInfo("UTC"))
```

- [ ] **Step 3: Run the existing search-query tests; update only where the new canonical output differs**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/search/test_query.py -v`
Expected: Most PASS. For any assertion that now differs because the new pipeline produces an equivalent-but-not-byte-identical string, update that assertion to the new canonical output (the spec authorized this as part of "delegate + plan removal"). Record each change in the commit message.

> If a large number of `test_query.py` assertions break, prefer marking the
> superseded string-output tests for removal (they are scheduled for deletion)
> rather than rewriting many — but keep at least the behavioral coverage that is
> not duplicated in `test_translate.py`.

- [ ] **Step 4: Add the end-to-end 400→200 test**

First find the search-API test module: `rg -l "search" src/documents/tests/test_api*.py`. Add (adjust module/class to the existing pattern):

```python
@pytest.mark.search
@pytest.mark.parametrize(
    "query",
    [
        "created:2020",
        "created:[20200101 TO 20201231]",
        "title:x,created:[2020 TO 2021]",
    ],
)
def test_advanced_search_no_longer_400s(self, query):
    response = self.client.get(f"/api/documents/?query={query}")
    assert response.status_code == 200
```

- [ ] **Step 5: Run the end-to-end test**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest --override-ini="addopts=" documents/tests/test_api_search.py -k no_longer_400 -v` (use the real module path).
Expected: PASS (200, not 400).

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_query.py src/documents/tests/
git commit -m "Feature: route advanced search through structural translation layer"
```

---

## Task 9: Full search suite, lint, and design-doc status update

**Files:**

- Modify: `docs/superpowers/specs/2026-06-14-search-query-translation-design.md` (status line)

- [ ] **Step 1: Run the full search marker suite**

Run: `cd src && PAPERLESS_SECRET_KEY=ci uv run pytest -m search`
Expected: PASS (full search suite, with coverage/xdist as configured).

- [ ] **Step 2: Lint and format**

Run: `uv run ruff check src/documents/search/ src/documents/tests/search/ && uv run ruff format src/documents/search/ src/documents/tests/search/`
Expected: no errors; formatting clean.

- [ ] **Step 3: Run pre-commit hooks on changed files**

Run: `uv run prek run --files src/documents/search/_translate.py src/documents/search/_dates.py src/documents/search/_query.py`
Expected: PASS.

- [ ] **Step 4: Update the spec status line**

Change the spec's `**Status:**` line to `Phase 1 implemented`. Add a one-line pointer to this plan.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-14-search-query-translation-design.md
git commit -m "Docs: mark query-translation Phase 1 implemented"
```

---

## Deferred (not in this plan)

- **Phase 2 (query objects):** build `tantivy.Query` objects for date clauses (`range_query(None)` open bounds, `empty_query()` no-match). Gated on the upstream tantivy-py date-value contribution documented in the spec §9. Separate plan.
- **Bare relative scalar** (`created:-1week`): currently falls to `NO_MATCH` (no-400). If desired later, add a relative-shape branch to `translate_scalar`.
- **Removal of `rewrite_natural_date_keywords` / `normalize_query`** and their string-output tests, once `test_translate.py` fully covers them.
- **Unknown-field 400** (`http:`), out of scope per spec §10.

---

## Self-Review notes (addressed)

- **Spec coverage:** scanner (Task 3-4), date scalar (Task 5), date range incl. open/reversed (Task 6), comma rules incl. multi-value scoping (Task 4), safety net + delegation (Task 8), tests incl. parse-acceptance + end-to-end (Tasks 7-8), `_dates` extraction (Task 1). Phase 2 + unknown-field explicitly deferred.
- **No placeholders:** every code step shows complete code; the two `> Implementer note` blocks flag where the scanner must be iterated against its own tests, not skipped.
- **Type consistency:** token names (`FieldValue`, `FieldValueList`, `FieldRange`, `Comma`, `Passthrough`), functions (`scan`, `resolve_commas`, `translate_scalar`, `translate_range`, `translate_query`, `_precision_bounds`, `_field_range_from_dates`, `_bound_datetimes`), and constants (`NO_MATCH`, `OPEN_LO`, `OPEN_HI`, `MULTI_VALUE_FIELDS`, `DATE_FIELDS`, `KNOWN_FIELDS`) are used consistently across tasks.
