# Search Error Shapes Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic advanced-search HTTP 400 ("Error listing search results, check logs for more detail.") with three specific, user-fixable `SearchQueryError` subclasses (`UnknownFieldError`, `InvalidFieldValueError`, `MalformedQueryError`).

**Architecture:** Two detection layers feeding the _existing_ `except SearchQueryError` handler in `UnifiedSearchViewSet.list` (no view change). (1) A **proactive** numeric-value validator inside `translate_query`'s render pass (`_translate.py`) raises `InvalidFieldValueError` before the query reaches Tantivy. (2) A **backstop** wrapper around `index.parse_query` in `parse_user_query` (`_query.py`) maps residual Tantivy `ValueError` message prefixes (`Field does not exist:`, `Syntax Error:`, `Expected a valid integer:`) into the right subclass, so nothing leaks Rust internals or hits the generic 400.

**Tech Stack:** Python 3.11+, Django, `tantivy` (tantivy-py 0.26.0), `regex`, stdlib `difflib`, pytest + pytest-django. All commands run via `uv run` from `src/`.

**Spec:** `docs/superpowers/specs/2026-06-15-search-error-shapes-followup-design.md` (read it first).

**Reference facts (empirically verified 2026-06-15):**

- Tantivy `index.parse_query` raises `ValueError` with exactly these prefixes: `Field does not exist: '<X>'`, `Syntax Error: <echo>`, `Expected a valid integer: 'ParseIntError { kind: InvalidDigit }'`.
- `page_count:>5`, `asn:<10`, `page_count:>=5`, `asn:[1 TO 10]`, `tag_id:1,2,3` parse OK (comparison operators produce correct `RangeQuery`).
- `asn:[1 TO]` / `asn:[TO 10]` are a **Syntax Error** (open numeric ranges unsupported; only open _date_ ranges work via sentinels).
- `scan()` only tokenizes fields in `KNOWN_FIELDS`; unknown `foobar:hello` stays a `Passthrough` and only fails at `parse_query` -> detected by the backstop, not proactively.
- `difflib.get_close_matches("corespondent", pool)` -> `["correspondent"]`; `has_tags`/`http`/`12` -> `[]` (bare message).
- `tantivy.Schema` exposes no field-name list, so the drift guard is parse-based.

## File Structure

| File                                              | Responsibility                                                                                                     | Change          |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------- |
| `src/documents/search/_translate.py`              | Error classes, field-set constants, proactive numeric validation in `_render`, Tantivy-error mapper + hint helpers | Modify          |
| `src/documents/search/_query.py`                  | Backstop wrapper around `index.parse_query` in `parse_user_query`                                                  | Modify          |
| `src/documents/search/__init__.py`                | Re-export new error classes for the view import                                                                    | Modify (verify) |
| `src/documents/tests/search/test_error_shapes.py` | All unit tests for the new behavior (dedicated file per subject)                                                   | Create          |
| `src/documents/tests/test_api_search.py`          | One view-level 400 integration test (mirrors existing `test_search_added_invalid_date`)                            | Modify          |

**Test command convention:** single-file runs disable xdist:
`cd src && uv run pytest documents/tests/search/test_error_shapes.py --override-ini="addopts=" -v`

---

### Task 1: Error classes and field-set constants

**Files:**

- Modify: `src/documents/search/_translate.py` (add `import difflib`; add constants and classes after the existing `InvalidDateQuery` class, around line 337)
- Test: `src/documents/tests/search/test_error_shapes.py` (create)

- [ ] **Step 1: Write the failing test**

Create `src/documents/tests/search/test_error_shapes.py`:

```python
from __future__ import annotations

import pytest

from documents.search._translate import FIELD_ALIASES
from documents.search._translate import KNOWN_FIELDS
from documents.search._translate import NUMERIC_FIELDS
from documents.search._translate import SEARCHABLE_FIELDS
from documents.search._translate import InvalidFieldValueError
from documents.search._translate import MalformedQueryError
from documents.search._translate import SearchQueryError
from documents.search._translate import UnknownFieldError


@pytest.mark.search
class TestErrorClasses:
    def test_all_subclass_search_query_error(self):
        assert issubclass(UnknownFieldError, SearchQueryError)
        assert issubclass(InvalidFieldValueError, SearchQueryError)
        assert issubclass(MalformedQueryError, SearchQueryError)

    def test_unknown_field_message_without_suggestion(self):
        err = UnknownFieldError("has_tags")
        assert err.field == "has_tags"
        assert err.suggestion is None
        assert str(err) == "Unknown search field 'has_tags'."

    def test_unknown_field_message_with_suggestion(self):
        err = UnknownFieldError("corespondent", suggestion="correspondent")
        assert err.suggestion == "correspondent"
        assert str(err) == (
            "Unknown search field 'corespondent'. Did you mean 'correspondent'?"
        )

    def test_invalid_field_value_message_with_field(self):
        err = InvalidFieldValueError("asn", "notanumber")
        assert err.field == "asn"
        assert err.value == "notanumber"
        assert str(err) == "Field 'asn' expects a number, got 'notanumber'."

    def test_invalid_field_value_generic_message(self):
        err = InvalidFieldValueError()
        assert "number" in str(err).lower()
        assert "ParseIntError" not in str(err)

    def test_malformed_query_message(self):
        err = MalformedQueryError("Unbalanced quote in search query.")
        assert str(err) == "Unbalanced quote in search query."


@pytest.mark.search
class TestFieldSets:
    def test_numeric_fields_are_known(self):
        assert NUMERIC_FIELDS <= KNOWN_FIELDS

    def test_searchable_excludes_aliases(self):
        assert SEARCHABLE_FIELDS == KNOWN_FIELDS - set(FIELD_ALIASES)
        # aliases must NOT be suggestable
        for alias in FIELD_ALIASES:
            assert alias not in SEARCHABLE_FIELDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest documents/tests/search/test_error_shapes.py --override-ini="addopts=" -v`
Expected: FAIL with `ImportError: cannot import name 'NUMERIC_FIELDS'` (and the other new names).

- [ ] **Step 3: Write minimal implementation**

In `src/documents/search/_translate.py`, add `import difflib` to the stdlib import group (after line 2, before `from dataclasses import dataclass`):

```python
import difflib
```

Then, immediately after the `InvalidDateQuery` class (after line 336), add:

```python
class UnknownFieldError(SearchQueryError):
    """Raised when a query scopes on a field name that does not exist."""

    def __init__(self, field: str, suggestion: str | None = None) -> None:
        self.field = field
        self.suggestion = suggestion
        message = f"Unknown search field {field!r}."
        if suggestion:
            message += f" Did you mean {suggestion!r}?"
        super().__init__(message)


class InvalidFieldValueError(SearchQueryError):
    """Raised when a numeric field receives a non-numeric value."""

    def __init__(self, field: str | None = None, value: str | None = None) -> None:
        self.field = field
        self.value = value
        if field is not None and value is not None:
            message = f"Field {field!r} expects a number, got {value!r}."
        else:
            message = "A numeric field in the search query received a non-numeric value."
        super().__init__(message)


class MalformedQueryError(SearchQueryError):
    """Raised for structural syntax errors (unbalanced quotes/brackets, etc.)."""
```

Add the field-set constants next to `KNOWN_FIELDS` (after line 92, after the `KNOWN_FIELDS` definition):

```python
# Numeric (unsigned-int) fields. Values must be integers, optionally prefixed by
# a comparison operator (>, <, >=, <=). Validated proactively in _render.
NUMERIC_FIELDS = frozenset(
    {
        "asn",
        "page_count",
        "num_notes",
        "correspondent_id",
        "document_type_id",
        "storage_path_id",
        "tag_id",
        "owner_id",
        "viewer_id",
    },
)

# Canonical user-facing field names for validation and did-you-mean suggestions.
# Aliases are excluded so a typo is never "corrected" to a deprecated alias.
SEARCHABLE_FIELDS = KNOWN_FIELDS - frozenset(FIELD_ALIASES)
```

Note: `SEARCHABLE_FIELDS` references `FIELD_ALIASES`, which is defined above `KNOWN_FIELDS` (line 54), so this ordering is valid.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && uv run pytest documents/tests/search/test_error_shapes.py --override-ini="addopts=" -v`
Expected: PASS (all `TestErrorClasses` and `TestFieldSets` cases green).

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_error_shapes.py
git commit -m "feat(search): add error-shape classes and field-set constants"
```

---

### Task 2: Proactive numeric-value validation in `translate_query`

**Files:**

- Modify: `src/documents/search/_translate.py` (add `_validate_numeric`; hook into `_render` at lines 484-503)
- Test: `src/documents/tests/search/test_error_shapes.py`

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/search/test_error_shapes.py`:

```python
from datetime import UTC

from documents.search._translate import translate_query


@pytest.mark.search
class TestProactiveNumericValidation:
    @pytest.mark.parametrize(
        ("query", "field", "value"),
        [
            ("asn:notanumber", "asn", "notanumber"),
            ("num_notes:abc", "num_notes", "abc"),
            ("page_count:[foo TO bar]", "page_count", "foo"),
            ("tag_id:1,foo", "tag_id", "foo"),
        ],
    )
    def test_non_numeric_value_raises(self, query, field, value):
        with pytest.raises(InvalidFieldValueError) as exc_info:
            translate_query(query, UTC)
        assert exc_info.value.field == field
        assert exc_info.value.value == value

    @pytest.mark.parametrize(
        "query",
        [
            "asn:5",
            "asn:>5",
            "asn:<10",
            "page_count:>=5",
            "page_count:<=5",
            "asn:[1 TO 10]",
            "tag_id:1,2,3",
            "viewer_id:1,2",
            "asn:[1 TO]",  # open numeric range: passes the integer check here
            "asn:[TO 10]",
        ],
    )
    def test_valid_numeric_values_do_not_raise(self, query):
        # Should not raise InvalidFieldValueError. (Open numeric ranges still fail
        # later at parse_query as a Syntax Error -> MalformedQueryError, but NOT
        # here in the value validator.)
        translate_query(query, UTC)

    def test_alias_numeric_field_validated(self):
        # type_id is a numeric alias -> document_type_id; must still validate.
        with pytest.raises(InvalidFieldValueError):
            translate_query("type_id:abc", UTC)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestProactiveNumericValidation" --override-ini="addopts=" -v`
Expected: FAIL — `test_non_numeric_value_raises` cases do not raise (values currently pass through to Tantivy unvalidated).

- [ ] **Step 3: Write minimal implementation**

In `src/documents/search/_translate.py`, add a module-level regex near the other operator patterns (after line 510, near `_SPACED_OP_RE`):

```python
# Leading comparison operator on a numeric value (asn:>5, page_count:<=10).
_COMPARISON_PREFIX_RE = regex.compile(r"^(>=|<=|>|<)")
```

Add the validator helper (place it just above `_render`, around line 483):

```python
def _validate_numeric(field: str, value: str) -> None:
    """Raise InvalidFieldValueError if a numeric-field value is not an integer.

    Strips a single leading comparison operator (>, <, >=, <=) and surrounding
    quotes first so comparison queries pass. An empty value (open range bound)
    is accepted here; an open numeric bracket-range still fails downstream at
    parse_query as a Syntax Error, surfaced as MalformedQueryError.
    """
    candidate = _COMPARISON_PREFIX_RE.sub("", value.strip().strip("\"'")).strip()
    if candidate == "":
        return
    if not candidate.isdigit():
        raise InvalidFieldValueError(field, value)
```

Modify `_render` (lines 490-502) to validate numeric fields. Replace the `FieldValueList`, `FieldValue`, and `FieldRange` branches with:

```python
    if isinstance(tok, FieldValueList):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        if field in NUMERIC_FIELDS:
            for v in tok.values:
                _validate_numeric(field, v)
        return " AND ".join(f"{field}:{v}" for v in tok.values)
    if isinstance(tok, FieldValue):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        if field in DATE_FIELDS:
            return translate_scalar(field, tok.value, tz)
        if field in NUMERIC_FIELDS:
            _validate_numeric(field, tok.value)
        return f"{field}:{tok.value}"
    if isinstance(tok, FieldRange):
        field = FIELD_ALIASES.get(tok.field, tok.field)
        if field in DATE_FIELDS:
            return translate_range(field, tok.lo, tok.hi, tz)
        if field in NUMERIC_FIELDS:
            _validate_numeric(field, tok.lo)
            _validate_numeric(field, tok.hi)
        return f"{field}:{tok.open}{tok.lo} TO {tok.hi}{tok.close}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestProactiveNumericValidation" --override-ini="addopts=" -v`
Expected: PASS.

- [ ] **Step 5: Run the full translate test file to check for regressions**

Run: `cd src && uv run pytest documents/tests/search/test_translate.py --override-ini="addopts=" -q`
Expected: PASS (no existing translate behavior broken).

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_error_shapes.py
git commit -m "feat(search): proactively validate numeric field values"
```

---

### Task 3: Tantivy-error mapper and malformed-query hint

**Files:**

- Modify: `src/documents/search/_translate.py` (add `_suggest_field`, `_malformed_hint`, `map_tantivy_error`)
- Test: `src/documents/tests/search/test_error_shapes.py`

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/search/test_error_shapes.py`:

```python
from documents.search._translate import map_tantivy_error


@pytest.mark.search
class TestMapTantivyError:
    def test_unknown_field_maps_with_suggestion(self):
        exc = ValueError("Field does not exist: 'corespondent'")
        mapped = map_tantivy_error(exc, "corespondent:foo")
        assert isinstance(mapped, UnknownFieldError)
        assert mapped.field == "corespondent"
        assert mapped.suggestion == "correspondent"

    def test_unknown_field_maps_without_suggestion(self):
        exc = ValueError("Field does not exist: 'has_tags'")
        mapped = map_tantivy_error(exc, "has_tags:true")
        assert isinstance(mapped, UnknownFieldError)
        assert mapped.field == "has_tags"
        assert mapped.suggestion is None

    def test_integer_error_maps_to_invalid_value(self):
        exc = ValueError("Expected a valid integer: 'ParseIntError { kind: InvalidDigit }'")
        mapped = map_tantivy_error(exc, "asn:x")
        assert isinstance(mapped, InvalidFieldValueError)
        assert "ParseIntError" not in str(mapped)

    @pytest.mark.parametrize(
        ("raw", "fragment"),
        [
            ('title:"abc', "quote"),
            ("(invoice OR bill", "parenthes"),
            ("created:[2020 TO 2021", "bracket"),
            ("invoice AND", "AND/OR/NOT"),
            ("OR invoice", "AND/OR/NOT"),
        ],
    )
    def test_syntax_error_maps_to_specific_hint(self, raw, fragment):
        exc = ValueError(f"Syntax Error: {raw}")
        mapped = map_tantivy_error(exc, raw)
        assert isinstance(mapped, MalformedQueryError)
        assert fragment.lower() in str(mapped).lower()
        assert raw not in str(mapped)  # never echo the raw query verbatim

    def test_balanced_open_numeric_range_gets_generic_hint(self):
        # asn:[1 TO] is a Syntax Error but brackets ARE balanced: must NOT claim
        # "unbalanced bracket".
        exc = ValueError("Syntax Error: asn:[1 TO ]")
        mapped = map_tantivy_error(exc, "asn:[1 TO]")
        assert isinstance(mapped, MalformedQueryError)
        assert "unbalanced" not in str(mapped).lower()

    def test_unrecognized_message_returns_none(self):
        exc = ValueError("Some brand new tantivy error")
        assert map_tantivy_error(exc, "whatever") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestMapTantivyError" --override-ini="addopts=" -v`
Expected: FAIL with `ImportError: cannot import name 'map_tantivy_error'`.

- [ ] **Step 3: Write minimal implementation**

In `src/documents/search/_translate.py`, add near the other error helpers (after the `MalformedQueryError` class is fine; place all three together at the end of the error-class section):

```python
_FIELD_MISSING_RE = regex.compile(r"^Field does not exist: '(?P<field>[^']*)'")

_GENERIC_MALFORMED = (
    "Could not parse the search query. Check for unbalanced quotes, brackets, "
    "or parentheses, or a misplaced AND/OR/NOT operator."
)


def _suggest_field(field: str) -> str | None:
    """Return the closest valid field name to ``field``, or None."""
    matches = difflib.get_close_matches(field, SEARCHABLE_FIELDS, n=1)
    return matches[0] if matches else None


def _malformed_hint(raw_query: str) -> str:
    """Best-effort specific hint for a structural error; generic fallback.

    Only claims a specific cause when it is structurally evident (unbalanced
    delimiters or a clearly misplaced boolean operator); otherwise returns the
    generic message so we never assert a wrong-but-confident cause.
    """
    if raw_query.count('"') % 2 != 0:
        return "Unbalanced quote in the search query."
    if raw_query.count("(") != raw_query.count(")"):
        return "Unbalanced parenthesis in the search query."
    if (
        raw_query.count("[") != raw_query.count("]")
        or raw_query.count("{") != raw_query.count("}")
    ):
        return "Unbalanced bracket in the search query."
    upper = raw_query.strip().upper()
    if upper.startswith(("AND ", "OR ")) or upper.endswith((" AND", " OR", " NOT")):
        return "Misplaced AND/OR/NOT operator in the search query."
    return _GENERIC_MALFORMED


def map_tantivy_error(exc: ValueError, raw_query: str) -> SearchQueryError | None:
    """Map a tantivy parse_query ValueError to a user-safe SearchQueryError.

    Returns None when the message is not a recognised family, so the caller can
    re-raise the original (preserving today's generic 400 for truly unknown
    errors rather than inventing a misleading message).
    """
    message = str(exc)
    m = _FIELD_MISSING_RE.match(message)
    if m is not None:
        field = m.group("field")
        return UnknownFieldError(field, _suggest_field(field))
    if message.startswith("Expected a valid integer"):
        return InvalidFieldValueError()
    if message.startswith("Syntax Error"):
        return MalformedQueryError(_malformed_hint(raw_query))
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestMapTantivyError" --override-ini="addopts=" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_translate.py src/documents/tests/search/test_error_shapes.py
git commit -m "feat(search): map tantivy parse errors to user-safe messages"
```

---

### Task 4: Backstop wrapper wired into `parse_user_query`

**Files:**

- Modify: `src/documents/search/_query.py` (import `map_tantivy_error`; add `_parse_query_friendly`; use it at lines 231-235 and 253-259)
- Test: `src/documents/tests/search/test_error_shapes.py`

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/search/test_error_shapes.py`:

```python
import tantivy

from documents.search._query import parse_user_query
from documents.search._translate import SearchQueryError as _SQE  # noqa: F401


@pytest.mark.search
class TestBackstopViaParseUserQuery:
    """Uses the module-scope ``index`` fixture from conftest.py."""

    def test_unknown_field_raises_unknown_field_error(self, index: tantivy.Index):
        with pytest.raises(UnknownFieldError) as exc_info:
            parse_user_query(index, "foobar:hello", UTC)
        assert exc_info.value.field == "foobar"

    def test_unknown_field_suggestion(self, index: tantivy.Index):
        with pytest.raises(UnknownFieldError) as exc_info:
            parse_user_query(index, "corespondent:bob", UTC)
        assert exc_info.value.suggestion == "correspondent"

    def test_legacy_backend_field_is_unknown(self, index: tantivy.Index):
        with pytest.raises(UnknownFieldError) as exc_info:
            parse_user_query(index, "has_tags:true", UTC)
        assert exc_info.value.field == "has_tags"

    @pytest.mark.parametrize(
        "query",
        ["(invoice OR bill", "invoice AND", "OR invoice", 'title:"abc'],
    )
    def test_syntax_error_raises_malformed(self, index: tantivy.Index, query):
        with pytest.raises(MalformedQueryError):
            parse_user_query(index, query, UTC)

    def test_open_numeric_range_is_malformed_not_unbalanced(self, index: tantivy.Index):
        with pytest.raises(MalformedQueryError) as exc_info:
            parse_user_query(index, "asn:[1 TO]", UTC)
        assert "unbalanced" not in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "query",
        ["page_count:>5", "asn:<10", "page_count:>=5", "asn:[1 TO 10]", "tag_id:1,2,3"],
    )
    def test_comparison_and_range_queries_succeed(self, index: tantivy.Index, query):
        assert isinstance(parse_user_query(index, query, UTC), tantivy.Query)

    @pytest.mark.parametrize(
        "query",
        ["notes.user:alice", "custom_fields.name:invoice"],
    )
    def test_dotted_json_subfields_not_flagged(self, index: tantivy.Index, query):
        assert isinstance(parse_user_query(index, query, UTC), tantivy.Query)

    def test_numeric_mismatch_raises_invalid_value(self, index: tantivy.Index):
        # Proactive pass fires inside translate_query before parse_query.
        with pytest.raises(InvalidFieldValueError) as exc_info:
            parse_user_query(index, "asn:notanumber", UTC)
        assert exc_info.value.field == "asn"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestBackstopViaParseUserQuery" --override-ini="addopts=" -v`
Expected: FAIL — unknown-field/syntax cases currently raise the bare Tantivy `ValueError`, not the new subclasses (the `index.parse_query` calls are unwrapped). The numeric-mismatch and success cases may already pass.

- [ ] **Step 3: Write minimal implementation**

In `src/documents/search/_query.py`, add the import alongside the existing translate imports (after line 20):

```python
from documents.search._translate import map_tantivy_error
```

Add a module-level helper (place it just above `parse_user_query`, before line 191):

```python
def _parse_query_friendly(
    index: tantivy.Index,
    query_str: str,
    raw_query: str,
    default_fields: list[str],
    **kwargs,
) -> tantivy.Query:
    """Call index.parse_query, translating Tantivy ValueErrors into user-safe
    SearchQueryError subclasses. Unrecognised errors are re-raised unchanged."""
    try:
        return index.parse_query(query_str, default_fields, **kwargs)
    except SearchQueryError:
        raise
    except ValueError as exc:
        mapped = map_tantivy_error(exc, raw_query)
        if mapped is not None:
            raise mapped from exc
        raise
```

In `parse_user_query`, replace the exact-query parse (lines 231-235):

```python
    exact = _parse_query_friendly(
        index,
        query_str,
        raw_query,
        DEFAULT_SEARCH_FIELDS,
        field_boosts=_FIELD_BOOSTS,
    )
```

and the fuzzy parse (lines 253-259):

```python
        fuzzy = _parse_query_friendly(
            index,
            query_str,
            raw_query,
            DEFAULT_SEARCH_FIELDS,
            field_boosts=_FIELD_BOOSTS,
            # (prefix=True, distance=1, transposition_cost_one=True) — edit-distance fuzziness
            fuzzy_fields={f: (True, 1, True) for f in DEFAULT_SEARCH_FIELDS},
        )
```

(`SearchQueryError` is already imported in `_query.py` at line 19.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestBackstopViaParseUserQuery" --override-ini="addopts=" -v`
Expected: PASS.

- [ ] **Step 5: Run the full query test file for regressions**

Run: `cd src && uv run pytest documents/tests/search/test_query.py --override-ini="addopts=" -q`
Expected: PASS (existing `parse_user_query` behavior, including `InvalidDateQuery` propagation, intact).

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_query.py src/documents/tests/search/test_error_shapes.py
git commit -m "feat(search): wrap parse_query to surface friendly error shapes"
```

---

### Task 5: Guard tests (pin prefixes + drift) and view-level 400

**Files:**

- Modify: `src/documents/search/__init__.py` (verify the new error classes are exported; add if missing)
- Test: `src/documents/tests/search/test_error_shapes.py` (pin + drift guards)
- Test: `src/documents/tests/test_api_search.py` (one view-level integration test)

- [ ] **Step 1: Verify the search package exports the new classes**

Run: `cd src && rg -n "SearchQueryError|InvalidDateQuery|__all__" documents/search/__init__.py`

If `SearchQueryError` is re-exported there (the view imports `from documents.search import SearchQueryError`), add the three new classes the same way. Example edit — add to the existing `from documents.search._translate import ...` block and to `__all__` if present:

```python
from documents.search._translate import InvalidFieldValueError
from documents.search._translate import MalformedQueryError
from documents.search._translate import UnknownFieldError
```

(The subclasses route through the existing `except SearchQueryError` handler regardless, so exporting is for discoverability/consumers. Skip if the package does not re-export error classes.)

- [ ] **Step 2: Write the failing pin + drift guard tests**

Append to `src/documents/tests/search/test_error_shapes.py`:

```python
from documents.search._query import DEFAULT_SEARCH_FIELDS
from documents.search._query import _FIELD_BOOSTS
from documents.search._translate import SEARCHABLE_FIELDS as _SEARCHABLE


@pytest.mark.search
class TestTantivyPinnedPrefixes:
    """If a tantivy-py upgrade changes these prefixes, the backstop silently
    regresses to the generic 400. Pin them so the upgrade fails loudly."""

    def _err(self, index: tantivy.Index, raw: str) -> str:
        with pytest.raises(ValueError) as exc_info:
            index.parse_query(raw, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
        return str(exc_info.value)

    def test_unknown_field_prefix(self, index: tantivy.Index):
        assert self._err(index, "foobar:hello").startswith("Field does not exist:")

    def test_syntax_error_prefix(self, index: tantivy.Index):
        assert self._err(index, "(invoice OR bill").startswith("Syntax Error")

    def test_integer_error_prefix(self, index: tantivy.Index):
        assert self._err(index, "asn:notanumber").startswith("Expected a valid integer")


@pytest.mark.search
class TestFieldDriftGuard:
    """Every user-facing searchable field must be a real schema field. tantivy
    exposes no field-name list, so we assert via parse: a real field never raises
    'Field does not exist'."""

    @pytest.mark.parametrize("field", sorted(_SEARCHABLE))
    def test_searchable_field_exists_in_schema(self, index: tantivy.Index, field):
        try:
            index.parse_query(
                f"{field}:1",
                DEFAULT_SEARCH_FIELDS,
                field_boosts=_FIELD_BOOSTS,
            )
        except ValueError as exc:
            # A type/syntax error proves the field EXISTS; only "does not exist"
            # is a drift failure.
            assert "Field does not exist" not in str(exc), (
                f"{field!r} is in SEARCHABLE_FIELDS but missing from the schema"
            )
```

- [ ] **Step 3: Run the guard tests to verify they pass**

Run: `cd src && uv run pytest "documents/tests/search/test_error_shapes.py::TestTantivyPinnedPrefixes" "documents/tests/search/test_error_shapes.py::TestFieldDriftGuard" --override-ini="addopts=" -v`
Expected: PASS. (These assert current truth; they guard against future drift. If `TestFieldDriftGuard` fails now, `SEARCHABLE_FIELDS` lists a name not in the schema — fix `KNOWN_FIELDS`/`NUMERIC_FIELDS`, not the test.)

- [ ] **Step 4: Write the failing view-level test**

In `src/documents/tests/test_api_search.py`, locate `test_search_added_invalid_date` (around line 723) and add this test directly after it, inside the same `TestDocumentSearchApi` class (mirrors that test's structure):

```python
    def test_search_unknown_field_returns_400(self) -> None:
        """
        GIVEN:
            - A query scoping on a non-existent field
        WHEN:
            - The search API is called
        THEN:
            - HTTP 400 with the unknown-field message under the "query" key
        """
        response = self.client.get("/api/documents/?query=foobar:hello")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("foobar", str(response.data["query"]))
```

- [ ] **Step 5: Run the view-level test to verify it passes**

Run: `cd src && uv run pytest "documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_unknown_field_returns_400" --override-ini="addopts=" -v`
Expected: PASS (the existing `except SearchQueryError` handler converts `UnknownFieldError` to `ValidationError({"query": [...]})`).

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/__init__.py src/documents/tests/search/test_error_shapes.py src/documents/tests/test_api_search.py
git commit -m "test(search): pin tantivy error prefixes, guard field drift, view 400"
```

---

### Task 6: Full suite + lint

**Files:** none (verification only)

- [ ] **Step 1: Run the whole search test directory**

Run: `cd src && uv run pytest documents/tests/search/ --override-ini="addopts=" -q`
Expected: PASS.

- [ ] **Step 2: Run the API search tests**

Run: `cd src && uv run pytest documents/tests/test_api_search.py --override-ini="addopts=" -q`
Expected: PASS.

- [ ] **Step 3: Lint the changed files**

Run: `cd src && uv run ruff check documents/search/_translate.py documents/search/_query.py documents/tests/search/test_error_shapes.py`
Expected: no errors (fix any import-ordering/formatting issues ruff reports; run `uv run ruff format` on the same files if needed).

- [ ] **Step 4: Final commit (only if lint produced changes)**

```bash
git add -A
git commit -m "chore(search): lint error-shapes follow-up"
```

---

## Self-Review

**Spec coverage:**

- `UnknownFieldError` (+ did-you-mean, legacy backend fields as unknown) -> Tasks 1, 3, 4.
- `InvalidFieldValueError` (proactive + backstop) -> Tasks 1, 2, 4.
- `MalformedQueryError` (balance-check, no verbatim echo, open-range caveat) -> Tasks 1, 3, 4.
- Hybrid detection (proactive scanner + backstop wrapper) -> Tasks 2, 4.
- `>`/`<` left working + validator allows operators -> Task 2 (`test_valid_numeric_values_do_not_raise`), Task 4 (`test_comparison_and_range_queries_succeed`).
- Single source of truth + drift guard -> Task 1 (`SEARCHABLE_FIELDS`), Task 5 (`TestFieldDriftGuard`).
- Message-prefix pin test -> Task 5 (`TestTantivyPinnedPrefixes`).
- Dotted-JSON / open-numeric-range / view-400 -> Tasks 4 and 5.
- Out of scope (frontend, URL search) -> correctly untouched.

**Placeholder scan:** none — every code step shows full code and exact commands.

**Type/name consistency:** `UnknownFieldError(field, suggestion=)`, `InvalidFieldValueError(field=None, value=None)`, `MalformedQueryError(message)`, `NUMERIC_FIELDS`, `SEARCHABLE_FIELDS`, `_validate_numeric(field, value)`, `_suggest_field(field)`, `_malformed_hint(raw_query)`, `map_tantivy_error(exc, raw_query)`, `_parse_query_friendly(index, query_str, raw_query, default_fields, **kwargs)` are used identically across all tasks.
