# Friendlier advanced-search error shapes

**Status:** design / ready for implementation plan.
**Follow-up to:** the `InvalidDateQuery` work on branch `fix/search-query-translation`
(PR #13010), itself specced in
`docs/superpowers/done/specs/2026-06-14-search-query-translation-design.md`.
**Builds on:** the `SearchQueryError(ValueError)` base in
`documents/search/_translate.py` and the single `except SearchQueryError` handler
in `UnifiedSearchViewSet.list` (`documents/views.py:2477`), which re-raises as DRF
`ValidationError({"query": [msg]})`. Any new subclass surfaces through that one
handler automatically, so this work is purely additive.

## Problem

Every advanced-search failure other than the now-handled invalid date lands in
the view's generic `except Exception` and returns
`HttpResponseBadRequest("Error listing search results, check logs for more
detail.")` (`views.py:2479-2482`). `index.parse_query(...)` runs _outside_ the
`translate_query` try/except in `parse_user_query` (`_query.py:220-235`), so
anything Tantivy rejects bypasses `SearchQueryError` entirely and gets the
unhelpful generic 400. Some Tantivy errors also leak Rust internals (e.g.
`ParseIntError { kind: InvalidDigit }`) if surfaced verbatim.

## Ground truth: what Tantivy raises (empirically re-verified 2026-06-15)

Probed against a real index built from `documents.search._schema.build_schema` +
`_tokenizer.register_tokenizers`, running each query through `translate_query`
then `index.parse_query(..., DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)`.
`index.parse_query` raises `ValueError` with three distinguishable message
families:

| Family           | Example inputs                                                                                             | Tantivy message                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Unknown field    | `foobar:hello`, `owner:5`, `has_tags:true`, `is_shared:true`                                               | `Field does not exist: 'foobar'`                                   |
| Syntax error     | `(invoice OR bill`, `created:[2020 TO 2021`, `invoice AND`, `OR invoice`, `title:"abc`, `:value`, `AND OR` | `Syntax Error: <echoes the whole query, no location>`              |
| Wrong value type | `asn:notanumber`, `page_count:[foo TO bar]`                                                                | `Expected a valid integer: 'ParseIntError { kind: InvalidDigit }'` |

**Parses OK (NOT errors):** `page_count:>5`, `asn:<10`, `page_count:>=5` (these
produce _correct_ Tantivy `RangeQuery` objects — see the `>`/`<` decision below),
`page_count:5` (TermQuery), `title:[a TO b]` (Str range on a text field),
`title:~~~` (EmptyQuery), `` (empty query).

## The `>`/`<`/`>=`/`<=` decision (investigated)

The stub flagged these as "parses OK but possibly silently wrong vs Whoosh." That
is **incorrect** — verified empirically:

- `page_count:>5` -> `RangeQuery { lower_bound: Excluded(5), upper_bound: Unbounded }`
- `page_count:>=5` -> `RangeQuery { lower_bound: Included(5), ... }`
- `asn:<10` -> `RangeQuery { lower_bound: Unbounded, upper_bound: Excluded(10) }`

Tantivy's query parser supports comparison operators natively and produces
correct range queries. They were _never_ supported in paperless-Whoosh (no
`GtLtPlugin`; confirmed in the base design §3 and against the old schema on
`main`), so there is no prior behavior to "match" and nothing is silently wrong.

**Decision: leave them as-is.** They work correctly and are effectively a free
capability gain over Whoosh. Do not reject them. The numeric value validator
(below) must explicitly _allow_ a leading `>`, `<`, `>=`, or `<=` so it does not
wrongly reject working comparison queries. Document them as supported.

Note the asymmetry (verified): the _comparison_ forms work, but _open
bracket-ranges_ on numeric fields do NOT. `asn:[1 TO]` and `asn:[TO 10]`
translate verbatim and Tantivy raises `Syntax Error` on them — only open _date_
ranges are rewritten to bounded sentinels (`OPEN_LO`/`OPEN_HI`) by
`translate_range`. So `asn:>1` works but `asn:[1 TO]` is malformed; readers must
not assume bracket-ranges behave like the comparison operators.

## Clarification: the old "Whoosh-only" fields were backend internals

The stub proposed targeted "this field isn't available in full-text search; use
the filter sidebar" messages for `owner`, `has_tags`, `is_shared`, etc. Checking
the old Whoosh code still present on `main` (`src/documents/index.py`,
`make_schema`) shows these were **backend filter / permission fields, not
user-facing search syntax**:

- `has_correspondent`, `has_tag`, `has_type`, `has_path`, `has_owner`,
  `has_custom_fields`, `is_shared`, `custom_field_count`, and `owner` (username
  text) were populated at index time so the permission and list-filter machinery
  could query them. `get_permissions_criterias()` builds
  `query.Term("has_owner", ...)`, `query.Term("owner_id", ...)`,
  `query.Term("viewer_id", ...)` programmatically.
- The user-facing full-text parser (`DelayedFullTextQuery`) advertised only
  `["content", "title", "correspondent", "tag", "type", "notes",
"custom_fields"]`. (Whoosh's generic `FieldsPlugin` would technically parse a
  typed `has_tag:true`, but that was never a designed or documented feature.)

**Consequence:** no curated per-field messages. These names are simply _unknown
fields_ and flow through `UnknownFieldError` + did-you-mean like any typo. Note
that `owner_id` and `viewer_id` legitimately remain queryable (present in
`KNOWN_FIELDS` and the new schema, still used for permission filtering), so they
are correctly _not_ unknown; `owner`, the `has_*` booleans, `is_shared`, and
`custom_field_count` are correctly absent and read as plain unknown fields.

## Proposed error shapes (all `SearchQueryError` subclasses)

All three live next to `InvalidDateQuery` in `_translate.py` and inherit the
"message is safe to surface" contract.

### 1. `UnknownFieldError`

`Unknown search field 'corespondent'.` plus a `Did you mean 'correspondent'?`
suggestion via `difflib.get_close_matches(field, suggestion_pool, n=1)`. The
suggestion pool is the user-facing field set derived from `KNOWN_FIELDS` (see
single-source-of-truth below). Typos get a suggestion; names with no close match
(e.g. `has_tags`) get the bare unknown-field message.

### 2. `InvalidFieldValueError`

Sibling of `InvalidDateQuery`. For numeric fields: `Field 'asn' expects a number,
got 'notanumber'.` Carries `field` + `value` attributes like `InvalidDateQuery`.
Removes the `ParseIntError { ... }` Rust leak.

### 3. `MalformedQueryError`

Structural syntax errors. A cheap balance-check pass gives specific hints for the
common cases (unbalanced `"`, `[`, `(`, dangling/leading `AND`/`OR`) before
falling back to a clean generic "check for unbalanced quotes, brackets, or
parentheses." Tantivy's message has no location and echoes the whole query, so it
is **never** surfaced verbatim.

Caveat: an open numeric bracket-range (`asn:[1 TO]`) reaches this path as a
`Syntax Error` even though its brackets are _balanced_. The balance-check must not
confidently assert "unbalanced brackets" for it — when brackets/quotes/parens are
balanced, fall back to the generic hint rather than a wrong-but-specific one.

## Detection strategy: hybrid, split by what each layer can see

The scanner and the parse-wrapper see different things; assigning each error
shape to the layer that can detect it cleanly avoids false positives.

### Proactive numeric validation in the scanner (`_translate.py`)

`scan()` already tokenizes recognized `field:value` and `field:[range]` clauses
into `FieldValue` / `FieldRange` for fields in `KNOWN_FIELDS`. Add a
`NUMERIC_FIELDS` set (`asn`, `page_count`, `num_notes`, and the `*_id` fields)
and validate those tokens' values during translation, raising
`InvalidFieldValueError` before the string ever reaches `index.parse_query`.

Validation rules:

- Strip a single leading comparison operator (`>=`, `<=`, `>`, `<`) before the
  integer check, so comparison queries pass.
- For ranges, validate each present bound (`lo`, `hi`) as an integer. An empty
  bound passes the _integer_ check (an empty string is not a bad integer), but be
  aware that an open numeric bracket-range (`asn:[1 TO]`) is still rejected
  downstream by Tantivy as a `Syntax Error` (see the `>`/`<` note above) — i.e.
  the validator does not make it succeed, it falls through to the malformed path.
  Do not emit a "bad number" message for an empty bound; let the structural error
  surface as `MalformedQueryError`.
- For multi-value numeric fields after comma expansion (`tag_id`, `viewer_id`),
  validate each expanded value (`tag_id:1,foo` -> `InvalidFieldValueError`).

This path owns `InvalidFieldValueError` exclusively: messages are rich,
context-aware, and independent of Tantivy's English strings.

### Why unknown-field detection is NOT proactive

`_match_field_token` returns `None` for any field not in `KNOWN_FIELDS`
(`_translate.py:193`) — an unknown `foobar:hello` is intentionally left as a
`Passthrough` (the existing `http:`-misfire guard). Detecting unknown fields in
the scanner would require a separate `\w+:` pass that re-introduces exactly the
false positives that guard exists to prevent:

- URLs: `http://example.com/a` (`http:`)
- Dotted JSON subfields, which are valid: `notes.user:alice`,
  `custom_fields.invoice_no:123` (the `\w+:` regex would see `user:` / `invoice_no:`)
- Time-like literals: `12:30` (note: a bare `12:30` is already a parse failure
  today — Tantivy raises `Field does not exist: '12'` — so under this design it
  reshapes into `UnknownFieldError("12")` with no close match, i.e. the bare
  unknown-field message. It is _not_ a clean passthrough; the point here is only
  that a proactive `\w+:` pass would mis-flag it even more aggressively.)

So unknown fields are detected in the backstop instead, where Tantivy has already
confirmed the token is a real field reference.

### Catch-and-sanitize backstop around `index.parse_query` (`_query.py`)

Wrap the `index.parse_query` call(s) in `parse_user_query`. Map residual Tantivy
`ValueError` messages by prefix:

- `Field does not exist: 'X'` -> extract `X`, build `UnknownFieldError(X)` with
  did-you-mean.
- `Syntax Error: ...` -> `MalformedQueryError` (run the balance-check for a
  specific hint; never echo the Tantivy text).
- `Expected a valid integer: ...` -> `InvalidFieldValueError`. This backstop is
  effectively _unreachable today_: every query that produces this Tantivy error
  goes through a recognized numeric field token (`asn`, `page_count`, `num_notes`,
  `*_id`) that `scan()` already models, so the proactive pass catches it first
  (verified — no query reaches this branch without the proactive pass firing).
  Its real value is forward-safety: if a future numeric field is added to the
  schema but not to `NUMERIC_FIELDS`, this branch guarantees the raw
  `ParseIntError { ... }` Rust struct never leaks. Keep it; the generic "expects a
  number" message stands in when `field`/`value` cannot be recovered from the
  Tantivy text.
- Anything unrecognized -> re-raise, preserving today's generic-500/400 path
  rather than inventing a misleading message.

Both the fuzzy and exact `parse_query` calls go through the same wrapper.

### Single source of truth for fields

`KNOWN_FIELDS` (`_translate.py:63`) is the canonical set of field names a user may
validly scope on; it already includes the v2 aliases (`type`, `path`, `type_id`,
`path_id`) that `translate_query` rewrites to real schema names. Use it (with
aliases optionally excluded from the _suggestion_ pool to avoid suggesting a
deprecated alias) for both validation and did-you-mean.

Add a drift-guard test asserting `KNOWN_FIELDS` minus the alias set is a subset of
the schema field names produced by `build_schema()`, so the two definitions cannot
silently diverge as the schema evolves. The backend-only Whoosh names (`owner`,
`has_*`, `is_shared`, `custom_field_count`) are correctly excluded from both.

## Testing

New dedicated test file (per project convention), e.g.
`src/documents/tests/test_search_error_shapes.py`:

- One case per error family asserting the `SearchQueryError` subclass and a
  user-safe message (no paths, no Rust structs, no verbatim Tantivy echo).
- `UnknownFieldError`: typo yields a did-you-mean suggestion; a no-close-match
  name (e.g. `has_tags`) yields the bare message.
- `InvalidFieldValueError`: `asn:notanumber`, `page_count:[foo TO bar]`, and a
  bad multi-value `tag_id:1,foo`.
- **`>`/`<` working case**: `page_count:>5` / `asn:<10` / `page_count:>=5` parse
  successfully and are NOT raised as errors (guards the numeric validator's
  operator allowance).
- **Open numeric range**: `asn:[1 TO]` / `asn:[TO 10]` surface as
  `MalformedQueryError` (Tantivy `Syntax Error`, brackets balanced) and the hint
  is the generic one, NOT a false "unbalanced brackets" claim.
- **Dotted JSON non-regression**: `notes.user:alice`,
  `custom_fields.name:invoice` are not flagged as unknown fields.
- **URL behavior**: a query containing `http://...` is unchanged from today's
  behavior — Tantivy treats `http` as a field, so it still 400s; under this design
  the message becomes the clearer `UnknownFieldError('http')` (no close match) and
  the proactive numeric pass does not touch it. This is a clarity gain, not a
  regression (it already 400'd generically). Out of scope to make URL substrings
  searchable.
- **Message-prefix pin**: a test that asserts the exact Tantivy prefixes
  (`Field does not exist:`, `Syntax Error:`, `Expected a valid integer:`) the
  backstop depends on, so a `tantivy-py` upgrade that changes them fails loudly
  instead of silently regressing to the generic 400.
- **Drift guard**: `KNOWN_FIELDS` (minus aliases) ⊆ `build_schema()` field names.
- View-level: each subclass surfaces as HTTP 400 with `{"query": [msg]}` through
  the existing handler.

## Risks / notes

- The backstop depends on Tantivy's error _message-string prefixes_, which are
  brittle across `tantivy-py` upgrades. The pin test above is the mitigation.
- Keep all messages safe to surface: they may echo user input but must never
  include internal paths, stack details, or Rust error structs.
- The balance-check for `MalformedQueryError` is a heuristic for _hints_ only; its
  failure mode is the clean generic message, never a wrong-but-confident one.

## Out of scope

- Frontend rendering of the structured `{"query": [...]}` 400 (the inline search
  error UI). Only relevant if the messages should render differently from the
  current generic banner; the current banner already displays the message.
- Adding or changing `>`/`<` semantics. They work; this spec only ensures the
  numeric validator does not break them.
