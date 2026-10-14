# Structured advanced-search errors from whoosh-compat diagnostics

**Status:** design / ready for implementation plan.
**Builds on:** advanced search parsed by whoosh-compat (#14072) and the search
field registry (#14071). Line numbers below refer to `dev` at `34a6c718f`.
**Scope:** backend. The frontend work lands on the same branch from a
co-maintainer; see "Frontend compatibility" and "Consumer notes".

## Current behavior

Advanced search does not use Tantivy's query-string parser.
`parse_user_query` (`documents/search/_query.py`) calls `wc.parse()` against the
`FieldRegistry` built from `PUBLIC_FIELDS`, maps any `Diagnostic`s to
`SearchQueryError` subclasses, then emits a `tantivy.Query` directly from the
AST. Probing the real `parse_user_query` on `dev` (whoosh-compat 0.3, tantivy
0.26) gives:

| Input                                                                                   | Result today                                                                                                 |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `foobar:hello`, `correspondent:bob`, `has_tags:true`, `owner_id:1`, `http://x`, `12:30` | No error. Unknown field prefixes are demoted to text and searched literally (documented in `docs/usage.md`). |
| `(invoice OR bill`, `invoice AND`, `OR invoice`, `title:"abc`                           | No error. The whoosh grammar is lenient and never fails on structure.                                        |
| `asn:notanumber`, `page_count:[foo TO bar]`, `asn:1,2`                                  | 400, `InvalidNumberQuery`.                                                                                   |
| `page_count:>5`, `asn:<10`                                                              | 400, `InvalidNumberQuery` (comparison operators are not whoosh syntax).                                      |
| `asn:[1 TO]`, `asn:[TO 10]`                                                             | Works (open numeric ranges).                                                                                 |
| `created:notadate`, `created:[2020 TO 2021`                                             | 400, `InvalidDateQuery`.                                                                                     |
| `title:[a TO b]`, `notes:*`, `asn:*x`                                                   | 400, plain `SearchQueryError` with a kind-specific message.                                                  |
| `asn:5 created:bad page_count:x`                                                        | 400, `MultipleSearchQueryErrors`, one message per bad value.                                                 |

Every user-fixable failure already arrives as a `SearchQueryError` with a safe
message.

## Problem

whoosh-compat's `Diagnostic` carries more than paperless uses. Besides `kind`
and `raw_value`, each record has:

- `field`: set on parse-time diagnostics and on every emit-time one, but
  paperless only keeps it on `InvalidDateQuery`/`InvalidNumberQuery`.
- `startchar` / `endchar`: where in the query string the problem is. Set on
  parse-time diagnostics and on emit-time ones (the emitter copies the node's
  span, `emitters/tantivy_.py:732-733`; `_widen_leaf`, `_cjk_alternative` and
  `_fuzzy_alternative` keep the original leaf span via `_leaf_span`).
- `suggestion`: replacement text for that span when exactly one rewrite of the
  query would work. The library's documented host contract is to splice it in
  rather than re-derive the rule:
  `fixed = q[:startchar] + suggestion + q[endchar:]`.
  In 0.3 the only case that carries one is an unquoted multi-word date
  (`created:december 2019` suggests `"december 2019"`); `created:20231340`,
  number errors and every emit-time diagnostic carry none.

Paperless throws most of that away. `_single_diagnostic_to_error` and
`_map_emit_error` keep only a message, and both views raise
`ValidationError({"query": [msg, ...]})`. A client can tell the user _what_ is
wrong but not _where_, and cannot offer the fix the library already computed.

Probed spans for reference:

```
created:december 2019        BAD_DATE   8..21  suggestion '"december 2019"'
created:december 2019 asn:x  BAD_DATE   8..21  suggestion '"december 2019"'
                             BAD_NUMBER 26..27 suggestion None
created:20231340             BAD_DATE   8..16  suggestion None
😀 created:december 2019     BAD_DATE   10..23 (code points; 11..24 in UTF-16)
```

## Goals

- Every search-query 400 also carries, per error, its field, location, the
  offending text and the suggested replacement, in a typed shape a client can
  rely on.
- When suggestions exist, the server returns one corrected query string, so no
  client has to do span arithmetic.
- Additive only, with no new API version: the `query` key keeps exactly today's
  strings.
- whoosh-compat types stay private to `_query.py`. The public payload is
  paperless's own contract, not the library's enum names.

## Non-goals

- New suggestions. Fixes come only from `Diagnostic.suggestion`; paperless adds
  no rewrite rules of its own. New library suggestions (for example for `>5`)
  appear in the payload with a whoosh-compat upgrade and no paperless change.
- Changes to whoosh-compat.
- Hints for demoted unknown fields (`correspondent:bob`). `Diagnostic` is
  fatal-only by library contract, and the documented paperless behavior is to
  search such text literally.
- Frontend changes. They are done on the same branch by a co-maintainer (see
  "Frontend compatibility" and "Consumer notes").
- A live query-validation endpoint (see "Future work").
- The `corrected_query: null` key on successful search responses
  (`views.py:2744`), a leftover of Whoosh spelling correction. Untouched.
- An OpenAPI schema for the 400 body. The search list endpoint documents none
  today.

## Design

### Error model (`documents/search/_errors.py`)

`SearchQueryError` gains four keyword-only, optional attributes:

```python
class SearchQueryError(ValueError):
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
```

`SearchQueryError("msg")` keeps working. `InvalidDateQuery` and
`InvalidNumberQuery` keep their positional `(field, value)` signature, pass
`field` up to the base, and accept and forward `start`, `end` and `suggestion`.
`QueryTooLongError` and `MultipleSearchQueryErrors` leave all four `None`: the
first has no span, and the second holds sub-errors that each carry their own.

Messages are unchanged byte for byte. The fix is never folded into `str(e)`.

### Diagnostic plumbing (`documents/search/_query.py`)

- `_single_diagnostic_to_error(d)` passes `field=str(d.field)` (when set),
  `start=d.startchar`, `end=d.endchar` and `suggestion=d.suggestion` to
  whichever error it builds, including the plain `SearchQueryError` branches
  (TOO_DEEP, PATTERN_ON_*, SINGLE_CHAR_BRACKET_RANGE) and the unmapped
  fallback.
- `_map_emit_error(e)` does the same for the 400 it returns. Emit-time
  diagnostics never carry a suggestion in 0.3 (the emitter's `_fail` takes
  none); it is copied anyway so a future one flows through. The paths that
  re-raise (INTERNAL, and MISCONFIGURED other than EXISTS_REQUIRES_FAST) are
  unchanged.

`field` is the canonical dotted name `str(FieldRef)` produces, as messages
already use (`type:` reports `document_type`, `notes.user:` reports
`notes.user`).

### Detail helper (`documents/search/_errors.py`)

Next to `search_query_error_messages`, and exported from `documents.search`:

```python
def search_query_error_details(
    e: SearchQueryError,
    query: str,
) -> tuple[list[dict[str, object]], str | None]:
    """(errors, suggested_query) for a SearchQueryError raised parsing ``query``."""
```

- `errors` has one entry per leaf error, flattening `MultipleSearchQueryErrors`
  in the same order as the messages helper:

  ```
  {"message": str, "field": str | None, "start": int | None,
   "end": int | None, "text": str | None, "suggestion": str | None}
  ```

  `start`/`end` are code-point offsets into the normalized query (see
  "Which string the spans index"). `text` is `query[start:end]`, so a client
  never has to slice by offset itself; JavaScript strings index in UTF-16 units
  and would get astral characters (emoji, CJK Extension B) wrong. `text` is
  `None` when the error has no span or the span falls outside `query`.

- `suggested_query` applies every non-`None` suggestion to `query` right to
  left, so earlier spans stay valid. It is `None` when no error has a
  suggestion, or when any suggestion lacks a span, has a span outside `query`,
  or overlaps another suggestion's span. A wrong fix is worse than none.
- Errors without a suggestion do not block the others: in
  `created:december 2019 asn:x` the date is quoted and `asn:x` is left as typed.

`query` must be the exact string that was parsed. See the next section.

### Which string the spans index

`wc.parse` has one call site (`_query.py`, in `parse_user_query`), reached only
through `TantivyBackend._parse_query`. In every search mode the only string it
parses is the `query` request parameter: `_get_tantivy_query_and_mode`
(`views.py:324`) uses it as the search itself in `QUERY` mode and as
`filter_query` alongside `text`/`title_search`. The simple modes never produce
diagnostics. The backend NFC-normalizes before parsing (`_backend.py:485`), so
spans index `normalize_search_text(str(params["query"]))`, written with `str()`
to match `_get_tantivy_query_and_mode` (bulk `filters` values are not guaranteed
to be strings). The views pass that string to the helper. For the NFC input
browsers normally send, this is identical to what the user typed.

### Response and views (`documents/views.py`)

A search-query 400 becomes:

```json
{
  "query": [
    "Invalid date value 'december 2019' for field 'created'.",
    "Invalid numeric value 'x' for field 'asn'."
  ],
  "query_errors": [
    {
      "message": "Invalid date value 'december 2019' for field 'created'.",
      "field": "created",
      "start": 8,
      "end": 21,
      "text": "december 2019",
      "suggestion": "\"december 2019\""
    },
    {
      "message": "Invalid numeric value 'x' for field 'asn'.",
      "field": "asn",
      "start": 26,
      "end": 27,
      "text": "x",
      "suggestion": null
    }
  ],
  "suggested_query": "created:\"december 2019\" asn:x"
}
```

- `query`: unchanged.
- `query_errors`: always present on a search-query 400.
- `suggested_query`: string or `null`, always present.
- `QueryTooLongError` (raised in `_get_tantivy_query_and_mode` before parsing,
  for an over-long `text`, `title_search` or `query`): one entry with `field`,
  `start`, `end`, `text` and `suggestion` all `null`, and
  `suggested_query: null`.
- A `SearchQueryError` on the `more_like_id` path (both try blocks catch it
  there too) gets the same shape with `query` treated as `""`, so every entry
  has `text: null`.

DRF's `ValidationError` cannot carry this. `_get_error_details` runs every leaf
through `force_str` (`rest_framework/exceptions.py:39`), so `start: 8` would
serialize as `"8"` and `None` as `"None"`. Add a small `APIException` subclass:

```python
class SearchQueryValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, e: SearchQueryError, query: str) -> None:
        errors, suggested = search_query_error_details(e, query)
        detail: dict[str, object] = {
            "query": search_query_error_messages(e),
            "query_errors": errors,
            "suggested_query": suggested,
        }
        # Assigned directly, not via super().__init__(detail), so DRF does not
        # stringify the ints and nulls.
        self.detail = detail
```

DRF's default `exception_handler` returns a dict `detail` as the response body
unchanged, and paperless configures no custom `EXCEPTION_HANDLER`. The `query`
list serializes to the same JSON as today's `ValidationError` (`ErrorDetail` is
a `str` subclass). Where the class lives (`documents/views.py` beside its two
users, or a small module the views import) is a plan-level choice.

Both call sites switch to it, each a one-line change with no signature changes:

- the document search list endpoint (`views.py:2771`);
- `_get_search_document_ids` in `DocumentSelectionMixin` (`views.py:2930`),
  reached through `_resolve_document_ids` by bulk edit, bulk download and the
  other selection endpoints. It raises from inside a helper, which is why this
  is an exception rather than a returned `Response`. It already has `filters`,
  the params dict to read `query` from.

### Frontend compatibility

The current frontend does not read `query` specifically. Its error handler
(`document-list-view.service.ts:391-403`) loops over every key of a 400 body and
prints `key: value[0]`. Against the new body it would print
`query_errors: [object Object]` and the first character of `suggested_query`,
and on `suggested_query: null` it throws a `TypeError` inside the handler, so
the banner never appears.

The backend change is therefore not merged on its own. The branch is shared
with a co-maintainer who adapts that handler (at minimum, stop treating the two
new keys as generic field errors) and builds the UI from "Consumer notes"
before the branch merges.

## Consumer notes (for the frontend, not implemented here)

What the payload enables, so the UI work can be scheduled with its owner:

- With `MultipleSearchQueryErrors` only the first message reaches the user
  today (`fieldError[0]`). The UI can list every `query_errors[].message`.
- Show the offending part with `query_errors[].text`. Do not slice the query
  with `start`/`end` in JavaScript: they are code-point offsets and JS strings
  index in UTF-16 units.
- When `suggested_query` is set, offer "Search for `<suggested_query>`
  instead", which replaces the `FILTER_FULLTEXT_QUERY` rule value and calls
  `setFilterRules(rules, true)`.
- Global search (`/api/search/`) runs `SearchMode.TEXT` (`views.py:3829`),
  never produces diagnostics, and is unaffected.

## Testing

Pytest-style, grouped in classes, with GIVEN/WHEN/THEN docstrings and
`pytest.param` ids, marked `search` (and `django_db` where needed).

- **Helper unit tests** (new `src/documents/tests/search/test_error_details.py`),
  built from hand-constructed errors:
  - single error with a suggestion: entry fields, `text`, and spliced
    `suggested_query`;
  - two suggestions in one query: both applied, right to left;
  - one fixable and one unfixable error: only the fixable span changes;
  - missing span, out-of-range span, overlapping spans: `suggested_query` is
    `None` and out-of-range `text` is `None`;
  - no suggestions: `suggested_query` is `None`;
  - non-ASCII before the span (an astral character): `text` is the right
    substring;
  - `QueryTooLongError`: one entry, all-null location;
  - `MultipleSearchQueryErrors` order matches `search_query_error_messages`.
- **Plumbing** (extend `src/documents/tests/search/test_error_routing.py`):
  - `_single_diagnostic_to_error` and `_map_emit_error` copy `field`,
    `startchar`, `endchar` and `suggestion` onto the error for each branch;
  - end to end through `parse_user_query` with the `query_index` fixture:
    `created:december 2019 asn:x` yields the spans and single suggestion probed
    above, and `title:[a TO b]` yields an emit-time error with `field` and a
    span. These pin the whoosh-compat contracts paperless depends on, so an
    upgrade that changes them fails loudly.
- **API** (extend `src/documents/tests/test_api_search_errors.py`, which already
  covers the list endpoint and the selection endpoints pytest-style):
  - list endpoint: 400 with `query` identical to today, `query_errors` entries
    with integer (not string) `start`/`end`, `text`, JSON `null`s, and the
    expected `suggested_query`;
  - a query with no possible fix: `suggested_query` is `null`;
  - `query` sent alongside `text=`: spans index the `query` param;
  - over-long query: all-null entry;
  - a selection endpoint (bulk edit): same shape.

## Risks / notes

- Span correctness depends on passing the exact parsed string. The helper's
  bounds check and the end-to-end tests guard against drift; a mismatch yields
  `text: null` / `suggested_query: null`, never a corrupted query.
- `suggestion` and the emit-time span are whoosh-compat contracts (`Diagnostic`
  docstring, README host contract). The end-to-end tests are the upgrade
  tripwire.
- Until the frontend half lands on the branch, the document list's search error
  banner is broken there (see "Frontend compatibility"). Expected on a shared
  branch; it must not merge in that state.
- Third-party clients that iterate every key of a 400 body the way paperless's
  own frontend does would see the new keys. Clients that read `query` are
  unaffected. Note the new keys in the release notes.

## Future work

- A live `/api/search/validate/` endpoint so the filter editor can mark spans
  and offer fixes while the user types.
- More suggestions in whoosh-compat (for example comparison operators to range
  syntax), which this payload surfaces without paperless changes.
