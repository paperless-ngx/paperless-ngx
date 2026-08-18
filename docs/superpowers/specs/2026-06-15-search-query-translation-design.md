# Whoosh→Tantivy Advanced-Query Translation — Design

**Date:** 2026-06-15
**Branch base:** `dev` (Phase 1 implemented on `fix/search-query-translation`)
**Status:** Phase 1 implemented; Phase 2 pending an upstream `tantivy-py` release (see below)

## Problem

The Tantivy search migration changed the advanced-query (`?query=`) syntax contract.
A class of queries that worked under the old Whoosh backend now return an opaque
**HTTP 400**, because the old query string is handed to `tantivy.Index.parse_query`
which rejects forms Whoosh accepted. There is no fallback: a parse error propagates
through `documents/search/_backend.py` and is caught by the generic handler in
`documents/views.py` → `HttpResponseBadRequest`, with the real error only in logs.

Affected query forms (all verified against real Whoosh and real Tantivy):

- Bare dates on a date field: `created:2020`, `created:202003`.
- Bracketed absolute/partial/ISO ranges: `created:[20200101 TO 20201231]`,
  `created:[2020-01-01 TO 2020-12-31]`, `created:[202001 TO 202006]`.
- Open-ended ranges: `created:[2020 to]`, `created:[to 2020]`.
- Relative ranges: `added:[-1 week to now]`, `added:[now-7d TO now]`.
- Comma-joined clauses and value lists: `created:[r],added:[r]`, `tag:foo,bar`,
  the malformed `title:x,created:[…]`.
- Renamed fields: `type:`/`path:` (Whoosh names) vs `document_type:`/`storage_path:`
  (Tantivy names).
- Invalid dates (`created:202023`) — Whoosh matched nothing (NullQuery); Tantivy 400s.

The original compatibility layer was a stack of order-dependent regex substitutions,
which had no structural awareness (could not tell a comma inside `[...]` from a clause
separator) and required a new regex per form. This design replaces it.

## Approach

A structural, context-aware translation pass that intercepts only the forms Tantivy
parses differently (dates, commas, renamed fields) and passes everything else
(booleans, grouping, phrases, wildcards) straight through to Tantivy's own parser.

Pipeline (`documents/search/_translate.py`):

```
parse_user_query(raw, tz)
  → translate_query(raw, tz)                    # wrapped in a safety net: on any
      → scan(raw)            depth-aware tokenizer (quotes / [] depth)
      → resolve_commas       value-list (tag/tag_id/viewer_id) vs clause separator
      → _render              date tokens → translate_scalar / translate_range,
                             field aliasing, comma → AND
      → operator normalization (spaced/trailing -/+ cleanup)
  → index.parse_query(translated, …)            # exception → fall back to raw query
```

Date math lives in `documents/search/_dates.py` (no Django deps). The two date-field
semantics are preserved: `created` is date-only (UTC-midnight boundaries);
`added`/`modified` are datetimes (local-tz-midnight → UTC).

### Verified compatibility contract (from running both engines)

- Comma between clauses = AND, both sides preserved; comma within a `KEYWORD(commas=True)`
  field value = value list. Multi-value fields are exactly `{tag, tag_id, viewer_id}`.
- Invalid/unparsable dates → a no-match clause (never a 400), matching Whoosh's NullQuery.
- Field renames to alias: `type`→`document_type`, `type_id`→`document_type_id`,
  `path`→`storage_path`, `path_id`→`storage_path_id`. Both old and new names work.
- Partial-date ranges floor the low bound and ceil the high bound; reversed ranges swap.

## Phase 1 (implemented)

Branch `fix/search-query-translation`. The full pipeline above, output as a Tantivy
query **string**, with these workarounds for things the string parser cannot express
on date fields:

- **Open-ended ranges** use far-past / far-future string sentinels
  (`0001-01-01T00:00:00Z` / `9999-12-31T23:59:59Z`).
- **No-match** (unparsable date) uses a degenerate equal-bound date range.

Status: complete; the full `-m search` suite passes (date forms, comma clauses, field
aliasing, relative ranges, operator normalization, and the existing search tests now
validating the new pipeline). The old `_rewrite_*` regex helpers were left in place as
delegation shims during the transition.

Landed in 15 commits on `fix/search-query-translation` (`f1b92a493`..`816a078a4`):
`_dates.py` extraction → partial-date helpers → scanner → comma resolution →
scalar/range translation → field aliasing → relative ranges + operator normalization →
`parse_user_query` wiring + delegation + tests. Key symbols in `_translate.py`:
`scan`, `resolve_commas`, `translate_scalar`, `translate_range`, `translate_query`;
constants `MULTI_VALUE_FIELDS`, `DATE_FIELDS`, `KNOWN_FIELDS`, `FIELD_ALIASES`,
`NO_MATCH`, `OPEN_LO`, `OPEN_HI`.

## Phase 2 (pending — the thing being tracked)

Replace the Phase-1 string workarounds with real `tantivy.Query` objects for date
clauses, which removes the sentinel/degenerate-range hacks entirely:

1. **Open bounds** via `Query.range_query(field, FieldType.Date, lower_bound=…,
upper_bound=None)` (and vice-versa) instead of `OPEN_LO`/`OPEN_HI` sentinels.
2. **No-match** via `Query.empty_query()` instead of the degenerate range. This also
   fixes the cosmetic issue that the no-match sentinel always names the `created` field.
3. **Retire the dead code**: remove the now-unused `_rewrite_*` helpers and the
   `rewrite_natural_date_keywords` / `normalize_query` delegation shims in `_query.py`
   (~160 lines left from the Phase-1 transition), and migrate their string-output tests
   in `test_query.py` (replace the direct `_rewrite_compact_date` test with a
   `translate_scalar` test).

### Blocker

Phase 2 is **gated on a published `tantivy-py` release**, not on any further code
contribution. In `tantivy-py 0.26.0` (our current pin: `tantivy~=0.26.0` in
`pyproject.toml`, released 2026-04-29), `range_query`/`term_query` **reject Python
`datetime` values on `Date` fields** (`Expected DateTime type for field …`), so date
Query objects cannot be built from Python. The fix is already merged on `tantivy-py`
`master` across two PRs:

- **#655** — `feat: support unbounded range queries via None bounds`.
- **#666** — `fix: add_date loses tzinfo` (adds the `PyDateTime → tantivy DateTime`
  converter and routes `range_query`/`term_query` through it).

Both postdate the `0.26.0` wheel.

- **Trigger:** a `tantivy-py` release `> 0.26.0` containing #655 + #666 is published to PyPI.
- **Action:** bump the `tantivy-py` pin, then do items 1–3 above.

## Out of scope

- Unknown-field handling: Whoosh degraded an unknown `field:` to text; Tantivy 400s
  (`http://x/a,b` → `Field does not exist: 'http'`). Not a date/comma/rename issue.
- Whoosh fields with no Tantivy equivalent: `owner` (text), the `has_*` presence
  booleans, `is_shared`, `custom_field_count`, `custom_fields_id`.
- `>`/`<`/`>=`/`<=` comparisons — never supported in paperless-Whoosh (no `GtLtPlugin`).

## Reference / how to re-verify

- Tantivy side (does a translated string parse?): build a real index via
  `documents.search._schema.build_schema` + `register_tokenizers`, then
  `index.parse_query(translate_query(q, tz), DEFAULT_SEARCH_FIELDS, field_boosts=…)`.
- Whoosh side (what did v2 do?): `src/documents/index.py` (the old `get_schema()` +
  `MultifieldParser([...]) + DateParserPlugin(...)`) was deleted from `main` in
  `aed9abe48` (#12471, 2026-04-02); check it out at `git show aed9abe48^:src/documents/index.py`
  (or `git checkout aed9abe48^ -- src/documents/index.py`) and run a query through it
  to get the ground-truth `Query`.
- A fuller empirical gap matrix lives in `SEARCH_TANTIVY_WHOOSH_COMPAT.md`.
