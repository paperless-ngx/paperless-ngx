# Structured Advanced-Search Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every advanced-search HTTP 400 also returns, per error, its field, location, offending text and suggested fix (from whoosh-compat's `Diagnostic`), plus one server-computed corrected query, while the existing `query` message list stays byte-identical.

**Architecture:** `SearchQueryError` gains optional `field`/`start`/`end`/`suggestion` attributes, filled from the `Diagnostic` in the two mapping functions in `_query.py`. A pure helper in `_errors.py` turns an error plus the parsed query string into the structured entries and the corrected query. A small DRF `APIException` subclass in `views.py` builds the 400 body without DRF's string coercion and replaces the two existing `ValidationError` raises.

**Tech Stack:** Python 3.11+, Django REST Framework, whoosh-compat 0.3 (`Diagnostic`), tantivy-py 0.26, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-14-search-error-details-design.md` (read it first).

## Global Constraints

- **No plan metadata anywhere in the change.** No task numbers, step numbers, "per the spec/plan", spec or plan file names, or design-section names in code, comments, docstrings, test names, test docstrings, or commit messages. Comments explain the code on its own terms.
- **No em dashes** in code, comments, docstrings, or commit messages.
- **Commit messages:** a `Feature:`-prefixed subject line, then a short paragraph on the problem and a short paragraph on the solution. No bullet lists, no conventional-commit prefixes, no `Co-Authored-By` or other attribution trailers.
- **Tests:** pytest style only (no `TestCase`), grouped in classes, every fixture param, fixture return and test signature type-annotated, GIVEN/WHEN/THEN docstring on every test, `pytest.param(..., id=...)` on every parametrize case, `mocker` rather than `unittest.mock.patch`.
- **Scope:** backend only. Do not touch `src-ui/`. A co-maintainer adapts the frontend on the same branch.
- **Messages unchanged:** `str()` of every existing `SearchQueryError` subclass stays byte-identical; the `query` key of every search 400 stays the same list of strings.
- **Lazy imports in `views.py`:** `documents.search` is only imported function-locally there (it pulls in tantivy). Keep it that way; type-only imports go under `TYPE_CHECKING`.
- **No version-defensive code:** target whoosh-compat 0.3 and DRF exactly as pinned; no `getattr`/`try` shims for other versions.
- **Lint/types:** `ruff check` and `ruff format` (the global binary, not `uv run ruff`), and `uv run pyrefly check`, clean on touched files.

## Delegation (model tiers)

Each task names the tier to dispatch it to. The rule used: Haiku for mechanical work where the plan carries every line; Sonnet for code with real edge cases or framework behavior to get right; Opus for the final whole-branch review, where the job is judging the change against the spec rather than writing it.

| Task                           | Tier   | Why                                                                                 |
| ------------------------------ | ------ | ----------------------------------------------------------------------------------- |
| Error model and detail helper  | Sonnet | Span bounds, right-to-left splicing and overlap rules are easy to get subtly wrong. |
| Diagnostic plumbing            | Sonnet | Touches every mapping branch; end-to-end tests pin library contracts.               |
| 400 body in the views          | Sonnet | DRF coercion behavior and the lazy-import constraint in `views.py`.                 |
| Branch verification            | Haiku  | Run commands, report output, fix only formatting.                                   |
| Final review (after all tasks) | Opus   | Whole-branch review against the spec and the Review Focus list below.               |

## Review Focus

Inputs the spec implies that are most likely to bite, each pinned by a test in the owning task:

- A character outside the Basic Multilingual Plane (emoji, CJK Extension B) before the error: `text` must still be the right substring. (Error model task, `test_text_after_astral_character`.)
- A decomposed (NFD) character before the error in the request: spans index the NFC-normalized query, so `text` and `suggested_query` must be computed from the normalized string, not the raw param. (Views task, `test_decomposed_input_spans_index_the_normalized_query`.)
- A query with one fixable and one unfixable error: the fix is applied and the other part is left as typed, never dropped. (Error model task, `test_unfixable_error_does_not_block_fix`; views task, `test_list_endpoint_returns_structured_errors`.)
- A search error raised where no `query` param exists (an over-long `text`, or the `more_like_id` path): no crash, entries carry `text: null` and `suggested_query` is `null`. (Views task, `test_missing_query_param_yields_null_text` and `test_over_long_text_param_yields_null_location`.)
- JSON rendering: `start`/`end` must arrive as JSON integers and absent values as JSON `null`, not the strings `"8"` and `"None"` DRF's `ValidationError` would produce. (Views task, asserted on `response.json()`.)

## Before starting

Branch from `dev` with a `feature-` prefix (hyphen, not slash), for example `feature-search-error-details`. That prefix makes CI build a Docker image the co-maintainer can run while adding the frontend half.

## File Structure

| File                                               | Responsibility                                                                            | Change |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------ |
| `src/documents/search/_errors.py`                  | Error classes carry location and fix; `search_query_error_details` builds entries and fix | Modify |
| `src/documents/search/__init__.py`                 | Export `search_query_error_details` and `SearchQueryErrorDetail`                          | Modify |
| `src/documents/search/_query.py`                   | Copy `field`/span/`suggestion` from each `Diagnostic` onto the error it builds            | Modify |
| `src/documents/views.py`                           | `SearchQueryValidationError`; the two `except SearchQueryError` sites raise it            | Modify |
| `src/documents/tests/search/test_error_details.py` | Unit tests for the error attributes and the detail helper                                 | Create |
| `src/documents/tests/search/test_error_routing.py` | Plumbing tests, including end-to-end span/suggestion pins against real parses             | Modify |
| `src/documents/tests/test_api_search_errors.py`    | API tests for the 400 body on the list and bulk-edit endpoints                            | Modify |

---

### Task 1: Error model and detail helper

**Model tier:** Sonnet

**Files:**

- Modify: `src/documents/search/_errors.py`
- Modify: `src/documents/search/__init__.py`
- Create: `src/documents/tests/search/test_error_details.py`

**Interfaces:**

- Consumes: nothing new.
- Produces:
  - `SearchQueryError(message: str, *, field: str | None = None, start: int | None = None, end: int | None = None, suggestion: str | None = None)` with attributes `.field`, `.start`, `.end`, `.suggestion`.
  - `InvalidDateQuery(field: str | None, value: str | None, *, start: int | None = None, end: int | None = None, suggestion: str | None = None)` and the same signature for `InvalidNumberQuery`. Both keep `.value`.
  - `class SearchQueryErrorDetail(TypedDict)` with keys `message: str`, `field: str | None`, `start: int | None`, `end: int | None`, `text: str | None`, `suggestion: str | None`.
  - `search_query_error_details(e: SearchQueryError, query: str) -> tuple[list[SearchQueryErrorDetail], str | None]`, exported from `documents.search`.

- [ ] **Step 1: Write the failing tests**

Create `src/documents/tests/search/test_error_details.py`:

```python
from __future__ import annotations

import pytest

from documents.search import InvalidDateQuery
from documents.search import InvalidNumberQuery
from documents.search import MultipleSearchQueryErrors
from documents.search import QueryTooLongError
from documents.search import SearchQueryError
from documents.search import search_query_error_details
from documents.search import search_query_error_messages

pytestmark = pytest.mark.search


class TestErrorLocationAttributes:
    def test_base_error_defaults_to_no_location(self) -> None:
        """
        GIVEN:
            - A SearchQueryError built with only a message
        WHEN:
            - Its location attributes are read
        THEN:
            - field, start, end and suggestion are all None and the
              message is unchanged
        """
        error = SearchQueryError("The search query is nested too deeply.")
        assert error.field is None
        assert error.start is None
        assert error.end is None
        assert error.suggestion is None
        assert str(error) == "The search query is nested too deeply."

    @pytest.mark.parametrize(
        ("error_cls", "expected_message"),
        [
            pytest.param(
                InvalidDateQuery,
                "Invalid date value 'december 2019' for field 'created'.",
                id="date",
            ),
            pytest.param(
                InvalidNumberQuery,
                "Invalid numeric value 'december 2019' for field 'created'.",
                id="number",
            ),
        ],
    )
    def test_typed_errors_carry_location_and_keep_message(
        self,
        error_cls: type[InvalidDateQuery] | type[InvalidNumberQuery],
        expected_message: str,
    ) -> None:
        """
        GIVEN:
            - An InvalidDateQuery or InvalidNumberQuery built with a span
              and a suggestion
        WHEN:
            - Its attributes and message are read
        THEN:
            - field, value, start, end and suggestion are set and the
              message is exactly what it was before spans existed
        """
        error = error_cls(
            "created",
            "december 2019",
            start=8,
            end=21,
            suggestion='"december 2019"',
        )
        assert error.field == "created"
        assert error.value == "december 2019"
        assert error.start == 8
        assert error.end == 21
        assert error.suggestion == '"december 2019"'
        assert str(error) == expected_message


class TestSearchQueryErrorDetails:
    def test_single_error_with_suggestion(self) -> None:
        """
        GIVEN:
            - One date error spanning "december 2019" with a quoting fix
        WHEN:
            - Details are built for the query it was raised from
        THEN:
            - One entry carries every field, and the corrected query has the
              value quoted
        """
        query = "created:december 2019"
        error = InvalidDateQuery(
            "created",
            "december 2019",
            start=8,
            end=21,
            suggestion='"december 2019"',
        )
        errors, suggested = search_query_error_details(error, query)
        assert errors == [
            {
                "message": "Invalid date value 'december 2019' for field 'created'.",
                "field": "created",
                "start": 8,
                "end": 21,
                "text": "december 2019",
                "suggestion": '"december 2019"',
            },
        ]
        assert suggested == 'created:"december 2019"'

    def test_two_suggestions_applied_right_to_left(self) -> None:
        """
        GIVEN:
            - Two errors with fixes, the second fix longer than the text it
              replaces
        WHEN:
            - Details are built
        THEN:
            - Both fixes land in the right place, because splicing runs from
              the end of the query backwards
        """
        query = "created:may 2020 added:june 2021"
        first = InvalidDateQuery(
            "created",
            "may 2020",
            start=8,
            end=16,
            suggestion='"may 2020"',
        )
        second = InvalidDateQuery(
            "added",
            "june 2021",
            start=23,
            end=32,
            suggestion='"june 2021"',
        )
        _, suggested = search_query_error_details(
            MultipleSearchQueryErrors([first, second]),
            query,
        )
        assert suggested == 'created:"may 2020" added:"june 2021"'

    def test_unfixable_error_does_not_block_fix(self) -> None:
        """
        GIVEN:
            - One error with a fix and one without
        WHEN:
            - Details are built
        THEN:
            - The fix is applied and the unfixable part is left as typed
        """
        query = "created:december 2019 asn:x"
        errors, suggested = search_query_error_details(
            MultipleSearchQueryErrors(
                [
                    InvalidDateQuery(
                        "created",
                        "december 2019",
                        start=8,
                        end=21,
                        suggestion='"december 2019"',
                    ),
                    InvalidNumberQuery("asn", "x", start=26, end=27),
                ],
            ),
            query,
        )
        assert [entry["text"] for entry in errors] == ["december 2019", "x"]
        assert [entry["suggestion"] for entry in errors] == ['"december 2019"', None]
        assert suggested == 'created:"december 2019" asn:x'

    @pytest.mark.parametrize(
        "errors",
        [
            pytest.param(
                [SearchQueryError("msg", suggestion='"a b"')],
                id="suggestion-without-span",
            ),
            pytest.param(
                [SearchQueryError("msg", start=5, end=99, suggestion='"a b"')],
                id="span-past-end",
            ),
            pytest.param(
                [
                    SearchQueryError("one", start=0, end=6, suggestion="x"),
                    SearchQueryError("two", start=4, end=9, suggestion="y"),
                ],
                id="overlapping-spans",
            ),
        ],
    )
    def test_unsafe_suggestions_yield_no_corrected_query(
        self,
        errors: list[SearchQueryError],
    ) -> None:
        """
        GIVEN:
            - Suggestions whose span is missing, out of range, or overlaps
              another suggestion
        WHEN:
            - Details are built for "abcdefghij"
        THEN:
            - No corrected query is offered, since any splice could corrupt
              the query
        """
        _, suggested = search_query_error_details(
            MultipleSearchQueryErrors(errors),
            "abcdefghij",
        )
        assert suggested is None

    def test_out_of_range_span_has_no_text(self) -> None:
        """
        GIVEN:
            - An error whose span runs past the end of the query
        WHEN:
            - Details are built
        THEN:
            - The entry keeps its offsets but its text is None
        """
        errors, _ = search_query_error_details(
            SearchQueryError("msg", start=5, end=99),
            "abcdefghij",
        )
        assert errors[0]["start"] == 5
        assert errors[0]["text"] is None

    def test_no_suggestions_yield_no_corrected_query(self) -> None:
        """
        GIVEN:
            - An error with a span but no fix
        WHEN:
            - Details are built
        THEN:
            - The entry has its text and no corrected query is offered
        """
        errors, suggested = search_query_error_details(
            InvalidNumberQuery("asn", "x", start=4, end=5),
            "asn:x",
        )
        assert errors[0]["text"] == "x"
        assert suggested is None

    def test_text_after_astral_character(self) -> None:
        """
        GIVEN:
            - A query starting with an emoji (outside the Basic Multilingual
              Plane) before the bad date, with spans counted in code points
        WHEN:
            - Details are built
        THEN:
            - text is exactly the bad value and the fix lands on it
        """
        query = "\U0001f600 created:december 2019"
        error = InvalidDateQuery(
            "created",
            "december 2019",
            start=10,
            end=23,
            suggestion='"december 2019"',
        )
        errors, suggested = search_query_error_details(error, query)
        assert errors[0]["text"] == "december 2019"
        assert suggested == '\U0001f600 created:"december 2019"'

    def test_query_too_long_has_null_location(self) -> None:
        """
        GIVEN:
            - A QueryTooLongError, which is raised before parsing
        WHEN:
            - Details are built
        THEN:
            - One entry with its message and every location field None
        """
        error = QueryTooLongError(5000, 4096)
        errors, suggested = search_query_error_details(error, "")
        assert errors == [
            {
                "message": str(error),
                "field": None,
                "start": None,
                "end": None,
                "text": None,
                "suggestion": None,
            },
        ]
        assert suggested is None

    def test_entry_order_matches_messages(self) -> None:
        """
        GIVEN:
            - Several errors aggregated in one MultipleSearchQueryErrors
        WHEN:
            - Details and the plain message list are both built
        THEN:
            - Entries appear in the same order as the messages
        """
        aggregate = MultipleSearchQueryErrors(
            [
                InvalidNumberQuery("asn", "x", start=4, end=5),
                InvalidDateQuery("created", "bad", start=14, end=17),
                SearchQueryError("The search query is nested too deeply."),
            ],
        )
        errors, _ = search_query_error_details(aggregate, "asn:x created:bad")
        assert [entry["message"] for entry in errors] == (
            search_query_error_messages(aggregate)
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/documents/tests/search/test_error_details.py`
Expected: FAIL at import with `ImportError: cannot import name 'search_query_error_details'`.

- [ ] **Step 3: Implement the error attributes and the helper**

Replace the contents of `src/documents/search/_errors.py` with:

```python
from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING
from typing import TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence


class SearchQueryError(ValueError):
    """
    Base for user-fixable search query errors.

    Carries a message safe to surface to the user (no internal details). The
    view layer catches this and returns an HTTP 400, so any future subclass
    gets the same treatment.

    field, start and end locate the problem when it is known: start/end are
    code-point offsets into the query string that was parsed. suggestion is
    replacement text for that span when exactly one rewrite of the query
    would fix it.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        start: int | None = None,
        end: int | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.field = field
        self.start = start
        self.end = end
        self.suggestion = suggestion
        super().__init__(message)


class InvalidDateQuery(SearchQueryError):
    """Raised when a date field value or range bound cannot be parsed."""

    def __init__(
        self,
        field: str | None,
        value: str | None,
        *,
        start: int | None = None,
        end: int | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.value = value
        super().__init__(
            f"Invalid date value {value!r} for field {field!r}.",
            field=field,
            start=start,
            end=end,
            suggestion=suggestion,
        )


class InvalidNumberQuery(SearchQueryError):
    """Raised when a numeric field value or range bound cannot be parsed."""

    def __init__(
        self,
        field: str | None,
        value: str | None,
        *,
        start: int | None = None,
        end: int | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.value = value
        super().__init__(
            f"Invalid numeric value {value!r} for field {field!r}.",
            field=field,
            start=start,
            end=end,
            suggestion=suggestion,
        )
```

Keep `QueryTooLongError`, `MultipleSearchQueryErrors` and `search_query_error_messages` exactly as they are (their `super().__init__(message)` calls still work), then append:

```python
class SearchQueryErrorDetail(TypedDict):
    """One user-fixable error, located in the query string that was parsed."""

    message: str
    field: str | None
    start: int | None
    end: int | None
    text: str | None
    suggestion: str | None


def _leaf_errors(e: SearchQueryError) -> tuple[SearchQueryError, ...]:
    if isinstance(e, MultipleSearchQueryErrors):
        return e.errors
    return (e,)


def _span(e: SearchQueryError, query: str) -> tuple[int, int] | None:
    """The error's (start, end) if it lies inside query, else None."""
    start, end = e.start, e.end
    if start is None or end is None or not 0 <= start <= end <= len(query):
        return None
    return start, end


def _suggested_query(
    errors: Sequence[SearchQueryError],
    query: str,
) -> str | None:
    """Apply every suggestion to query, or None if none can be applied safely.

    A suggestion with no usable span, or two whose spans overlap, means any
    splice could corrupt the query, so nothing is offered at all. Errors
    without a suggestion are left as typed.
    """
    fixes: list[tuple[int, int, str]] = []
    for error in errors:
        if error.suggestion is None:
            continue
        span = _span(error, query)
        if span is None:
            return None
        fixes.append((span[0], span[1], error.suggestion))
    if not fixes:
        return None
    fixes.sort()
    if any(later[0] < earlier[1] for earlier, later in pairwise(fixes)):
        return None
    fixed = query
    # Right to left, so each splice leaves the spans before it valid.
    for start, end, suggestion in reversed(fixes):
        fixed = fixed[:start] + suggestion + fixed[end:]
    return fixed


def search_query_error_details(
    e: SearchQueryError,
    query: str,
) -> tuple[list[SearchQueryErrorDetail], str | None]:
    """The structured errors and corrected query for a SearchQueryError.

    query must be the exact string that was parsed (after normalization),
    since that is what the offsets index. text is cut here rather than left
    to clients because the offsets count code points, which JavaScript
    string indexing does not.
    """
    leaves = _leaf_errors(e)
    details: list[SearchQueryErrorDetail] = []
    for leaf in leaves:
        span = _span(leaf, query)
        details.append(
            {
                "message": str(leaf),
                "field": leaf.field,
                "start": leaf.start,
                "end": leaf.end,
                "text": query[span[0] : span[1]] if span is not None else None,
                "suggestion": leaf.suggestion,
            },
        )
    return details, _suggested_query(leaves, query)
```

In `src/documents/search/__init__.py`, add these imports beside the other `_errors` imports:

```python
from documents.search._errors import SearchQueryErrorDetail
from documents.search._errors import search_query_error_details
```

and add `"SearchQueryErrorDetail"` and `"search_query_error_details"` to `__all__`, keeping it sorted the way it is now (uppercase names first, then lowercase).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/documents/tests/search/test_error_details.py src/documents/tests/search/test_error_routing.py`
Expected: PASS (the routing tests confirm existing messages are unchanged).

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/search src/documents/tests/search/test_error_details.py` then `ruff format src/documents/search src/documents/tests/search/test_error_details.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_errors.py src/documents/search/__init__.py src/documents/tests/search/test_error_details.py
git commit -m "Feature: Locate search query errors and build a corrected query

A SearchQueryError only carried a message, so nothing downstream could say
where in the query a problem was or offer a fix.

SearchQueryError and its date/number subclasses now carry an optional field,
code-point span and suggested replacement. search_query_error_details turns
an error and the parsed query into one entry per error, including the
offending text, plus a corrected query built by applying every suggestion
right to left. No corrected query is offered when any suggestion's span is
missing, out of range or overlapping."
```

---

### Task 2: Diagnostic plumbing

**Model tier:** Sonnet

**Files:**

- Modify: `src/documents/search/_query.py` (`_map_emit_error`, `_single_diagnostic_to_error`)
- Modify: `src/documents/tests/search/test_error_routing.py`

**Interfaces:**

- Consumes: `SearchQueryError`, `InvalidDateQuery`, `InvalidNumberQuery` keyword arguments `field`/`start`/`end`/`suggestion` from Task 1.
- Produces: every `SearchQueryError` raised by `parse_user_query` carries the diagnostic's `field` (as `str(FieldRef)`), `startchar`→`start`, `endchar`→`end` and `suggestion`.

- [ ] **Step 1: Write the failing tests**

In `src/documents/tests/search/test_error_routing.py`, add to the imports:

```python
from documents.search._errors import InvalidDateQuery
from documents.search._errors import InvalidNumberQuery
from documents.search._errors import MultipleSearchQueryErrors
```

Then append these classes:

```python
class TestDiagnosticLocationIsCopied:
    """field, span and suggestion survive the Diagnostic -> error mapping."""

    @pytest.mark.parametrize(
        ("kind", "field", "field_kind", "expected_cls"),
        [
            pytest.param(
                DiagnosticKind.BAD_DATE,
                FieldRef("created"),
                FieldKind.DATE,
                InvalidDateQuery,
                id="bad-date",
            ),
            pytest.param(
                DiagnosticKind.BAD_NUMBER,
                FieldRef("asn"),
                FieldKind.U64,
                InvalidNumberQuery,
                id="bad-number",
            ),
            pytest.param(
                DiagnosticKind.PATTERN_ON_NUMERIC,
                FieldRef("asn"),
                FieldKind.U64,
                SearchQueryError,
                id="pattern-on-numeric",
            ),
            pytest.param(
                DiagnosticKind.SINGLE_CHAR_BRACKET_RANGE,
                FieldRef("title"),
                FieldKind.TEXT,
                SearchQueryError,
                id="single-char-bracket-range",
            ),
            pytest.param(
                DiagnosticKind.TOO_DEEP,
                None,
                None,
                SearchQueryError,
                id="too-deep-no-field",
            ),
        ],
    )
    def test_parse_diagnostic_location_is_copied(
        self,
        kind: DiagnosticKind,
        field: FieldRef | None,
        field_kind: FieldKind | None,
        expected_cls: type[SearchQueryError],
    ) -> None:
        """
        GIVEN:
            - A parse-time Diagnostic with a span and a suggestion
        WHEN:
            - _single_diagnostic_to_error maps it
        THEN:
            - The error is the expected class and carries the canonical
              field name (or None), the span and the suggestion
        """
        diagnostic = Diagnostic(
            kind=kind,
            cause=cause_for(kind),
            message=_LIBRARY_PROSE,
            startchar=3,
            endchar=9,
            field=field,
            field_kind=field_kind,
            raw_value="raw",
            suggestion='"raw"',
        )
        error = _single_diagnostic_to_error(diagnostic)
        assert type(error) is expected_cls
        assert error.field == (str(field) if field is not None else None)
        assert (error.start, error.end) == (3, 9)
        assert error.suggestion == '"raw"'

    def test_emit_diagnostic_location_is_copied(self) -> None:
        """
        GIVEN:
            - An emit-time TEXT_RANGE QueryError on a JSON subpath, with a span
        WHEN:
            - _map_emit_error maps it
        THEN:
            - The 400 error carries the dotted field name and the span
        """
        diagnostic = Diagnostic(
            kind=DiagnosticKind.TEXT_RANGE,
            cause=cause_for(DiagnosticKind.TEXT_RANGE),
            message=_LIBRARY_PROSE,
            startchar=0,
            endchar=27,
            field=FieldRef("custom_fields", "value"),
            field_kind=FieldKind.JSON,
        )
        error = _map_emit_error(QueryError(diagnostic))
        assert error.field == "custom_fields.value"
        assert (error.start, error.end) == (0, 27)
        assert error.suggestion is None


class TestRealQueryLocations:
    """Pins the whoosh-compat span and suggestion contracts paperless relies
    on, against real parses: an upgrade that changes them fails here."""

    def test_parse_time_spans_and_suggestion(
        self,
        query_index: tantivy.Index,
    ) -> None:
        """
        GIVEN:
            - A real query index
        WHEN:
            - parse_user_query is called with an unquoted multi-word date and
              a bad number ("created:december 2019 asn:x")
        THEN:
            - Two errors: the date located at 8..21 with a quoting fix, the
              number at 26..27 with none
        """
        with pytest.raises(MultipleSearchQueryErrors) as excinfo:
            parse_user_query(query_index, "created:december 2019 asn:x", UTC)
        date_error, number_error = excinfo.value.errors
        assert (date_error.field, date_error.start, date_error.end) == (
            "created",
            8,
            21,
        )
        assert date_error.suggestion == '"december 2019"'
        assert (number_error.field, number_error.start, number_error.end) == (
            "asn",
            26,
            27,
        )
        assert number_error.suggestion is None

    def test_emit_time_span(
        self,
        query_index: tantivy.Index,
    ) -> None:
        """
        GIVEN:
            - A real query index
        WHEN:
            - parse_user_query is called with a range on a text field
              ("title:[a TO b]"), which only fails at emit time
        THEN:
            - The error names "title" and spans the range, 6..14
        """
        with pytest.raises(SearchQueryError) as excinfo:
            parse_user_query(query_index, "title:[a TO b]", UTC)
        error = excinfo.value
        assert (error.field, error.start, error.end) == ("title", 6, 14)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/documents/tests/search/test_error_routing.py`
Expected: the new tests FAIL (`error.field`/`error.start` are `None`); the existing tests still pass.

- [ ] **Step 3: Copy the location in both mapping functions**

In `src/documents/search/_query.py`, change the last line of `_map_emit_error` from `return SearchQueryError(_user_facing_emit_message(d))` to:

```python
    return SearchQueryError(
        _user_facing_emit_message(d),
        field=str(d.field) if d.field is not None else None,
        start=d.startchar,
        end=d.endchar,
        suggestion=d.suggestion,
    )
```

Replace the body of `_single_diagnostic_to_error` with:

```python
def _single_diagnostic_to_error(d: Diagnostic) -> SearchQueryError:
    # d.field is a FieldRef, not a str: str(d.field) gives the canonical
    # dotted name (an aliased query, e.g. type:, reports document_type).
    field_name = str(d.field) if d.field is not None else None
    if d.kind is DiagnosticKind.BAD_DATE:
        return InvalidDateQuery(
            field_name,
            d.raw_value,
            start=d.startchar,
            end=d.endchar,
            suggestion=d.suggestion,
        )
    if d.kind is DiagnosticKind.BAD_NUMBER:
        return InvalidNumberQuery(
            field_name,
            d.raw_value,
            start=d.startchar,
            end=d.endchar,
            suggestion=d.suggestion,
        )
    if d.kind is DiagnosticKind.TOO_DEEP:
        message = "The search query is nested too deeply."
    elif d.kind in _PATTERN_ON_KINDS:
        kind_label = f" ({d.field_kind.name.lower()})" if d.field_kind else ""
        message = (
            f"Wildcard patterns are not supported for field {field_name!r}{kind_label}."
        )
    elif d.kind is DiagnosticKind.SINGLE_CHAR_BRACKET_RANGE:
        field_label = f" for field {field_name!r}" if field_name else ""
        message = (
            f"{d.raw_value!r} looks like a bracket range{field_label}, but "
            "'[' is not a wildcard character on its own. Combine it with a "
            "wildcard, e.g. a trailing '*', or double-quote the value to "
            "search it as literal text."
        )
    else:
        logger.warning(
            "Unmapped parse diagnostic %s: %s",
            d.kind,
            d.message,
        )  # pragma: no cover
        message = "The search query could not be executed."  # pragma: no cover
    return SearchQueryError(
        message,
        field=field_name,
        start=d.startchar,
        end=d.endchar,
        suggestion=d.suggestion,
    )
```

The message strings must stay character-for-character identical to the current ones; only the control flow changes so every branch shares one constructor call.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/documents/tests/search/test_error_routing.py src/documents/tests/search/test_error_details.py src/documents/tests/search/test_query.py`
Expected: PASS. If `test_parse_time_spans_and_suggestion` or `test_emit_time_span` reports different offsets, stop and report the actual values rather than editing the expectations: they pin library behavior the payload depends on.

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/search/_query.py src/documents/tests/search/test_error_routing.py` then `ruff format` on the same files.
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_query.py src/documents/tests/search/test_error_routing.py
git commit -m "Feature: Carry whoosh-compat diagnostic locations onto search errors

whoosh-compat reports a field, a character span and sometimes a one-line fix
for every diagnostic, but mapping a diagnostic to a SearchQueryError kept
only the message.

Both the parse-time and emit-time mappings now copy the field, span and
suggestion onto the error they build. Tests against real parses pin the
offsets and the multi-word date suggestion so a whoosh-compat upgrade that
changes them fails loudly."
```

---

### Task 3: 400 body in the views

**Model tier:** Sonnet

**Files:**

- Modify: `src/documents/views.py` (new class after `_get_tantivy_query_and_mode`; the `except SearchQueryError` blocks in `UnifiedSearchViewSet.list`, around line 2771, and in `DocumentSelectionMixin._get_search_document_ids`, around line 2930)
- Modify: `src/documents/tests/test_api_search_errors.py`

**Interfaces:**

- Consumes: `search_query_error_details`, `search_query_error_messages` from `documents.search`; `normalize_search_text` from `documents.search._query`; the error attributes from Tasks 1 and 2.
- Produces: `SearchQueryValidationError(error: SearchQueryError, raw_query: object | None)` in `documents.views`, an `APIException` with status 400 whose body is `{"query": list[str], "query_errors": list[SearchQueryErrorDetail], "suggested_query": str | None}`.

- [ ] **Step 1: Write the failing tests**

In `src/documents/tests/test_api_search_errors.py`, add to the runtime imports:

```python
from typing import Any
from typing import cast

from documents.search import InvalidDateQuery
from documents.views import _MAX_QUERY_LENGTH
from documents.views import SearchQueryValidationError
```

Then append:

```python
@pytest.mark.usefixtures("searchable_document")
class TestStructuredQueryErrors:
    """The 400 body locates each error and offers a corrected query, on top
    of the unchanged message list."""

    def test_list_endpoint_returns_structured_errors(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A query with an unquoted multi-word date and a bad number
        WHEN:
            - The document list endpoint is queried
        THEN:
            - A 400 whose "query" messages are unchanged, whose
              "query_errors" locate both errors with JSON integers and
              nulls, and whose "suggested_query" quotes only the date
        """
        response = admin_client.get(
            "/api/documents/",
            {"query": "created:december 2019 asn:x"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["query"] == [
            "Invalid date value 'december 2019' for field 'created'.",
            "Invalid numeric value 'x' for field 'asn'.",
        ]
        assert body["query_errors"] == [
            {
                "message": "Invalid date value 'december 2019' for field 'created'.",
                "field": "created",
                "start": 8,
                "end": 21,
                "text": "december 2019",
                "suggestion": '"december 2019"',
            },
            {
                "message": "Invalid numeric value 'x' for field 'asn'.",
                "field": "asn",
                "start": 26,
                "end": 27,
                "text": "x",
                "suggestion": None,
            },
        ]
        assert body["suggested_query"] == 'created:"december 2019" asn:x'

    def test_unfixable_query_has_null_suggested_query(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A query whose only error has no fix ("asn:x")
        WHEN:
            - The document list endpoint is queried
        THEN:
            - suggested_query is JSON null, not the string "None"
        """
        response = admin_client.get("/api/documents/", {"query": "asn:x"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["suggested_query"] is None

    def test_spans_index_the_query_param_alongside_text(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A plain text search combined with an advanced query filter
        WHEN:
            - The document list endpoint is queried
        THEN:
            - The error's span and text index the "query" param, not "text"
        """
        response = admin_client.get(
            "/api/documents/",
            {"text": "invoice", "query": "created:december 2019"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        entry = response.json()["query_errors"][0]
        assert (entry["start"], entry["end"], entry["text"]) == (
            8,
            21,
            "december 2019",
        )

    def test_decomposed_input_spans_index_the_normalized_query(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A query whose first word is spelled with a decomposed accent
              ("cafe" plus a combining acute), which the backend
              NFC-normalizes before parsing
        WHEN:
            - The document list endpoint is queried with a bad date after it
        THEN:
            - text is the bad value and suggested_query is built from the
              normalized query, so nothing is shifted by one character
        """
        response = admin_client.get(
            "/api/documents/",
            {"query": "café created:december 2019"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["query_errors"][0]["text"] == "december 2019"
        assert body["suggested_query"] == 'café created:"december 2019"'

    def test_over_long_text_param_yields_null_location(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A "text" search longer than the maximum query length, rejected
              before any parsing
        WHEN:
            - The document list endpoint is queried
        THEN:
            - One error entry with every location field null and no
              suggested query
        """
        response = admin_client.get(
            "/api/documents/",
            {"text": "x" * (_MAX_QUERY_LENGTH + 1)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert len(body["query_errors"]) == 1
        entry = body["query_errors"][0]
        assert [entry[key] for key in ("field", "start", "end", "text")] == [
            None,
            None,
            None,
            None,
        ]
        assert body["suggested_query"] is None

    def test_bulk_edit_returns_structured_errors(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A bulk edit whose selection filter has an unquoted multi-word
              date
        WHEN:
            - The bulk_edit endpoint is called
        THEN:
            - The 400 carries the same structured errors and corrected
              query as the list endpoint
        """
        response = admin_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [],
                "all": True,
                "filters": {"query": "created:december 2019"},
                "method": "set_document_type",
                "parameters": {"document_type": None},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["query_errors"][0]["text"] == "december 2019"
        assert body["suggested_query"] == 'created:"december 2019"'


class TestSearchQueryValidationError:
    def test_missing_query_param_yields_null_text(self) -> None:
        """
        GIVEN:
            - A located SearchQueryError raised where there is no "query"
              param (the more_like_id path, or an over-long "text")
        WHEN:
            - SearchQueryValidationError is built with no raw query
        THEN:
            - The entry keeps its offsets, its text is None, and no
              corrected query is offered
        """
        error = InvalidDateQuery(
            "created",
            "december 2019",
            start=8,
            end=21,
            suggestion='"december 2019"',
        )
        detail = cast("dict[str, Any]", SearchQueryValidationError(error, None).detail)
        assert detail["query_errors"][0]["text"] is None
        assert detail["suggested_query"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/documents/tests/test_api_search_errors.py`
Expected: FAIL at import with `ImportError: cannot import name 'SearchQueryValidationError'`.

- [ ] **Step 3: Add the exception class**

In `src/documents/views.py`, add `from rest_framework.exceptions import APIException` beside the other `rest_framework.exceptions` imports, and add to the existing `if TYPE_CHECKING:` block (line 279):

```python
    from documents.search import SearchQueryError
```

`views.py` has no `from __future__ import annotations`, so the annotation below must stay a string (`"SearchQueryError"`); unquoted it raises `NameError` at import time.

Add this class directly after `_get_tantivy_query_and_mode`:

```python
class SearchQueryValidationError(APIException):
    """HTTP 400 for a user-fixable search query error.

    "query" keeps the plain message list existing clients read.
    "query_errors" locates each error in the query and "suggested_query" is
    the query with every available fix applied, or None.

    The body is assigned to self.detail directly because passing it to
    APIException/ValidationError runs every value through force_str, which
    would turn the offsets into strings and None into "None".
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, error: "SearchQueryError", raw_query: object | None) -> None:
        from documents.search import search_query_error_details
        from documents.search import search_query_error_messages
        from documents.search._query import normalize_search_text

        super().__init__()
        # The offsets index the query exactly as it was parsed: str() as in
        # _get_tantivy_query_and_mode, then the backend's NFC normalization.
        query = normalize_search_text(str(raw_query)) if raw_query is not None else ""
        errors, suggested_query = search_query_error_details(error, query)
        detail: dict[str, object] = {
            "query": search_query_error_messages(error),
            "query_errors": errors,
            "suggested_query": suggested_query,
        }
        self.detail = detail
```

- [ ] **Step 4: Raise it from both call sites**

In `UnifiedSearchViewSet.list`, replace

```python
            raise ValidationError({"query": search_query_error_messages(e)}) from e
```

with

```python
            raise SearchQueryValidationError(e, request.query_params.get("query")) from e
```

and delete the now-unused `from documents.search import search_query_error_messages` at the top of `list`.

In `DocumentSelectionMixin._get_search_document_ids`, replace

```python
            raise ValidationError({"query": search_query_error_messages(e)}) from e
```

with

```python
            raise SearchQueryValidationError(e, filters.get("query")) from e
```

and delete the now-unused `from documents.search import search_query_error_messages` import in that method. Leave the comments above both raises as they are.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest src/documents/tests/test_api_search_errors.py src/documents/tests/test_api_search.py`
Expected: PASS. `test_api_search.py` confirms the existing `"added" in str(response.data["query"])`-style assertions still hold.

- [ ] **Step 6: Lint**

Run: `ruff check src/documents/views.py src/documents/tests/test_api_search_errors.py` then `ruff format` on the same files.
Expected: no errors (in particular no F401 for the removed imports).

- [ ] **Step 7: Commit**

```bash
git add src/documents/views.py src/documents/tests/test_api_search_errors.py
git commit -m "Feature: Return located errors and a corrected query on search 400s

A search query 400 only listed messages, so a client could not show where
the problem was or offer the fix whoosh-compat had already worked out.

Search 400s from the document list and the selection endpoints now add
query_errors, one entry per error with its field, offsets, offending text
and suggestion, and suggested_query with every fix applied. The existing
query message list is unchanged. The body is set directly on an
APIException subclass because DRF's ValidationError would stringify the
offsets and nulls."
```

---

### Task 4: Branch verification

**Model tier:** Haiku

**Files:** none, unless formatting needs a fix.

**Interfaces:** none.

- [ ] **Step 1: Run the search test package and the touched API tests**

Run: `uv run pytest src/documents/tests/search/ src/documents/tests/test_api_search_errors.py src/documents/tests/test_api_search.py`
Expected: PASS. Report any failure with its full output; do not change test expectations to make them pass.

- [ ] **Step 2: Lint and format the whole change**

Run: `ruff check src/documents/search src/documents/views.py src/documents/tests/search src/documents/tests/test_api_search_errors.py` and `ruff format --check` on the same paths.
Expected: no errors and no files to reformat.

- [ ] **Step 3: Type check**

Run: `uv run pyrefly check`
Expected: no new errors in `src/documents/search/_errors.py`, `src/documents/search/_query.py` or `src/documents/views.py` compared with the baseline (`.pyrefly-baseline.json`).

- [ ] **Step 4: Commit only if formatting changed anything**

```bash
git add -u
git commit -m "Feature: Format search error detail changes

Formatting after the search error detail work left files that ruff would
rewrite.

Applied ruff format; no behavior change."
```

Skip this step when Steps 2 and 3 were already clean.

---

### Final review

**Model tier:** Opus

Review the whole branch against `docs/superpowers/specs/2026-10-14-search-error-details-design.md`, the Global Constraints and the Review Focus list above. Check in particular that no plan metadata or em dashes leaked into code, comments, test docstrings or commit messages, that every existing message string is unchanged, and that `views.py` still imports `documents.search` only function-locally.
