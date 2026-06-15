# Spec stub: friendlier advanced-search error shapes (follow-up)

**Status:** stub / not yet planned. Follow-up to the `InvalidDateQuery` work on
branch `fix/search-query-translation` (PR #13010).
**Builds on:** the `SearchQueryError(ValueError)` base added in
`documents/search/_translate.py` and the single `except SearchQueryError` handler
in `UnifiedSearchViewSet.list` (`documents/views.py`). Any new subclass surfaces
through that one handler automatically, so this work is purely additive.

## Problem

Every failure on the advanced-search path (other than the now-handled invalid
date) lands in the view's generic `except Exception` and returns
`HttpResponseBadRequest("Error listing search results, check logs for more
detail.")`. `index.parse_query(...)` runs _outside_ the `translate_query`
try/except in `parse_user_query`, so anything Tantivy rejects bypasses
`SearchQueryError` entirely and gets the unhelpful generic 400. Some Tantivy
errors also leak Rust internals if surfaced verbatim.

## Ground truth: what Tantivy raises (empirically probed 2026-06-15)

`index.parse_query` raises `ValueError` with three distinguishable message
families:

| Family           | Example inputs                                                                                             | Tantivy message                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Unknown field    | `foobar:hello`, `owner:5`, `has_tags:true`, `is_shared:true`                                               | `Field does not exist: 'foobar'`                                   |
| Syntax error     | `(invoice OR bill`, `created:[2020 TO 2021`, `invoice AND`, `OR invoice`, `title:"abc`, `:value`, `AND OR` | `Syntax Error: <echoes the whole query, no location>`              |
| Wrong value type | `asn:notanumber`, `page_count:[foo TO bar]`                                                                | `Expected a valid integer: 'ParseIntError { kind: InvalidDigit }'` |

Parses OK (NOT errors, but possibly silently wrong — out of scope for error
shapes, noted for awareness): `page_count:>5`, `asn:<10` (the `>`/`<`
comparisons), `title:[a TO b]` (range on a text field), `title:~~~` (bad fuzzy),
`` (empty query).

## Proposed error shapes (all `SearchQueryError` subclasses)

### 1. `UnknownFieldError` (highest value)

Distinguish two sub-cases:

- **Typo** -> `Unknown search field 'corespondent'.` plus a "Did you mean
  'correspondent'?" suggestion via `difflib.get_close_matches` against the known
  schema field set.
- **Whoosh-only field with no Tantivy equivalent** (finite known set: `owner`,
  `has_tags`, `has_correspondent`/other `has_*`, `is_shared`, custom-field
  id/count) -> targeted message, e.g. "`has_tags` isn't available in full-text
  search; use the filter sidebar," rather than "field does not exist."

The list of valid fields already exists implicitly: schema fields in
`documents/search/_schema.py` and `KNOWN_FIELDS` in `_translate.py`. Reconcile to
a single source of truth for validation + suggestions.

### 2. `InvalidFieldValueError` (sibling of `InvalidDateQuery`)

For numeric fields (`asn`, `page_count`, `num_notes`, `*_id`): "Field 'asn'
expects a number, got 'notanumber'." Carries `field` + `value` like
`InvalidDateQuery`. Also removes the `ParseIntError { ... }` Rust leak.

### 3. `MalformedQueryError` (structural syntax)

A cheap balance-check pass gives specific hints for the common cases (unbalanced
`"`, `[`, `(`, dangling `AND`/`OR`) before falling back to a clean generic
"check for unbalanced quotes, brackets, or parentheses." Tantivy's message has no
location, so do not echo it verbatim.

## Detection strategy: hybrid

- **Proactive validation in the scanner** (`_translate.py`): it already tokenizes
  `field:value` / `field:[range]`, so extend it to validate field existence (+
  suggestions) and numeric value types up front. Messages are rich,
  context-aware, and independent of Tantivy's English error strings. Lives next
  to `InvalidDateQuery`. Covers only the field-scoped tokens it recognizes.
- **Catch-and-sanitize wrapper** around `index.parse_query` in
  `parse_user_query`: map residual `Syntax Error:` / type-mismatch messages into
  `MalformedQueryError` / `InvalidFieldValueError` so nothing leaks internals or
  the generic message. Backstop for pure structural errors the scanner does not
  model.

Both paths raise `SearchQueryError`; the existing view handler routes them all.

## Risks / notes

- The catch-and-sanitize wrapper depends on Tantivy's error _message string
  prefixes_ (`Field does not exist:`, `Syntax Error:`, `Expected a valid
integer:`), which are brittle across `tantivy-py` upgrades. Add a test that
  pins those prefixes so an upgrade that changes them fails loudly rather than
  silently regressing to the generic 400.
- Decide separately whether `>`/`<` comparisons should be supported, rejected
  with a message, or left as-is. They currently parse without error and are
  likely silently wrong relative to Whoosh semantics.
- Keep messages safe to surface: they may echo user input but must not include
  internal paths, stack details, or Rust error structs.

## Out of scope

Frontend rendering of the structured `{"query": [...]}` 400 (the inline search
error UI) — only relevant if the messages should render differently from the
current generic banner.
