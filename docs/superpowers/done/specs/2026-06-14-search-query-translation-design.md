# Design: Whoosh→Tantivy Advanced-Query Translation Layer

**Date:** 2026-06-14
**Status:** Phase 1 implemented on branch `fix/search-query-translation` (string-pipeline translation layer in `_translate.py`/`_dates.py`, wired into `parse_user_query`). Phase 2 (Query objects) remains gated on the tantivy-py release noted in §8/§9. Plan: `docs/superpowers/plans/2026-06-14-search-query-translation.md`.
**Branch context:** `beta`. Search code: `src/documents/search/`.
**Related:** `SEARCH_TANTIVY_WHOOSH_COMPAT.md` (repo root) — full empirical gap matrix and reproduction harnesses. Open branch `fix/scope-comma-expansion` (commit `d8fa97232`) — partial comma fix this design subsumes.

---

## 1. Problem

Paperless migrated full-text search from Whoosh (v2) to Tantivy (v3, commit `aed9abe48`, #12471). A
compatibility layer in `_query.py` rewrites old Whoosh query syntax into Tantivy syntax via a stack of
ordered regex substitutions before calling `tantivy.Index.parse_query`.

That regex stack is piecemeal and has hit its complexity ceiling:

- **No structural awareness.** It runs regex on a flat string, so it cannot distinguish a comma inside
  `[...]` from a top-level clause separator, or know whether a `:` is a field prefix or text. This causes
  real bugs (e.g. `title:x,created:[2020 TO 2021]` rewrites to malformed `title:x AND title:created:[...]`).
- **Order-dependence.** Six rewriters with implicit ordering contracts (14-digit before 8-digit, year-range
  before 8-digit, etc.). Each new date form means reasoning about all interactions again.

The result is a class of v2-valid queries that now return **HTTP 400**. There is no fallback: any syntax
Tantivy rejects raises out of `parse_query`, propagates through `_backend.py` (no try/except), and is caught
by the generic handler in `views.py:2471-2475` → `HttpResponseBadRequest`, with the real error only in logs.

### Confirmed regressions (empirically reproduced; full table in `SEARCH_TANTIVY_WHOOSH_COMPAT.md` §5)

| Class                    | Example                                                        | Today                  | Whoosh v2                   |
| ------------------------ | -------------------------------------------------------------- | ---------------------- | --------------------------- |
| Bare date on date field  | `created:2020`, `created:202003`                               | 400                    | full-year / full-month span |
| Bracketed absolute range | `created:[20200101 TO 20201231]`, `[2020-01-01 TO 2020-12-31]` | 400                    | floor/ceil range            |
| Open-ended range         | `created:[2020 to]`, `created:[to 2020]`                       | 400                    | `>=` / `<=` range           |
| Comma between clauses    | `title:x,created:[...]`                                        | 400 (malformed)        | AND, both sides             |
| Comma value-list scope   | `tag:foo,type:bar`                                             | wrong (`tag:type:bar`) | `tag:foo AND type:bar`      |
| Invalid date             | `created:202023`                                               | 400                    | NullQuery (no-match)        |

---

## 2. Goals / Non-goals

**Goals**

- Eliminate the date- and comma-class 400s by translating those forms to valid Tantivy syntax.
- Replace the order-dependent regex stack with a structural, context-aware pass.
- Match empirically-verified Whoosh v2 semantics (see §3).
- Additive tests: existing suite stays green during transition.
- **Field-name aliasing for the four renamed Whoosh→Tantivy fields** (added to scope 2026-06-14):
  `type`→`document_type`, `type_id`→`document_type_id`, `path`→`storage_path`, `path_id`→`storage_path_id`.
  These are the only fields the Tantivy migration renamed; v2 queries using the old names currently 400.
  Both old and new spellings work after aliasing (new names pass through verbatim). The alias targets are the
  text "name" fields (`document_type` is populated from `document_type.name`), so `type:invoice` →
  `document_type:invoice` is correct. Fields with no Tantivy equivalent (`owner`, the `has_*` booleans,
  `is_shared`, `custom_field_count`, `custom_fields_id`) are NOT aliased and remain out of scope.

**Non-goals (explicitly out of scope)**

- Full Whoosh query-language parity.
- Other Whoosh divergences: unknown-field-degrades-to-text (`http://x/a,b` → 400 on the `http:` unknown
  field), tolerant unbalanced parens, case-insensitive `AND/OR/NOT`. These pass through to Tantivy unchanged
  and are recorded as separate, known gaps (§10).
- `>`/`<`/`>=`/`<=` comparison operators — never supported in paperless-Whoosh (no `GtLtPlugin`); adding them
  would be a new feature, not a compat fix.

---

## 3. Empirical ground truth (verified, not inferred)

Both engines were run directly; do not regress these without re-checking.

**Whoosh v2** (paperless's exact `MultifieldParser([...]) + DateParserPlugin(basedate=...)` setup):

- `created:2020` → `DateRange(2020-01-01 .. 2020-12-31 23:59:59)`; `created:202003` → March 2020.
- `created:202023` (month 23) → `<_NullQuery>` — **invalid dates match nothing, never error.**
- `created:[202001 TO 202006]` → floor/ceil partial-date bounds; `[2020 to]` / `[to 2020]` → open bounds.
- `created:-1week` → an exact-microsecond `Term` — parsed but matches ~nothing (useless in v2).
- Comma = AND between clauses, both preserved: `created:[r],added:[r]`, `correspondent:acme,created:[...]`,
  `invoice,created:2020`.
- Comma value-list **only** for `KEYWORD(commas=True)` fields (`tag`, `tag_id`, `viewer_id`):
  `tag:a,b` → `tag:a AND tag:b`. Text-field commas (`correspondent:foo,bar`, `title:10,20`) are split by the
  field **analyzer** at parse time, not the comma plugin.
- `title:x,created:[...]` → only the DateRange (Whoosh drops `title:x`) — a v2 free-mode **bug**; the correct
  target keeps both sides.

**Tantivy 0.26.0** (`tantivy v0.26.0, index_format v7`):

- Date fields require RFC3339 (`...Z`) literals; rejects bare `2020`, `20200101`, `2020-01-01`, lowercase
  open ranges.
- Text-field commas parse fine verbatim (`correspondent:foo,bar`, `title:10,20`, `content:a,b,c`).
- Boolean/paren/phrase structure parses correctly, so a translated date token can sit anywhere:
  `created:[...Z TO ...Z] OR foo` and `(created:[...] OR foo)` both parse.
- String date sentinels `0001-01-01T00:00:00Z` and `9999-12-31T23:59:59Z` both parse on a date field.

---

## 4. Architecture (Approach 1: flat tokenizing scanner + single date translator)

The scanner specializes only the date/comma tokens and treats everything else (operators, parens, phrases,
words, wildcards) as opaque passthrough. Tantivy keeps doing boolean/grouping/phrase parsing. A `field:value`
span is locally recognizable regardless of surrounding boolean context, so the scanner needs no understanding
of `AND/OR/NOT`.

### 4.1 Module layout

New module `src/documents/search/_translate.py` — single source of truth:

```
translate_query(raw: str, tz) -> str        # top-level: scan → transform → recombine
  scan(raw) -> list[Token]                   # depth-aware char-walk tokenizer
  _resolve_commas(tokens) -> list[Token]     # comma → AND / value-list / literal
  translate_date_value(field, raw, tz) -> str  # shape-dispatch date translator
```

Date-boundary math (`_date_only_range`, `_datetime_range`, floor/ceil helpers) **moves** from `_query.py`
into `_translate.py` (or a small shared `_dates.py`) so there is one home. The existing math is reused
verbatim — not rewritten.

### 4.2 Data flow

```
parse_user_query(raw, tz)
  → translate_query(raw, tz)          # NEW pipeline
  → index.parse_query(translated, DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
```

### 4.3 Transition (delegate + planned removal)

- `rewrite_natural_date_keywords` and `normalize_query` become thin delegators to `translate_query` (or its
  sub-steps) so their existing assertions still pass.
- The plan **explicitly schedules deleting both functions and their string-output tests** once
  `test_translate.py` covers them. Single source of truth, no lingering dead code.

### 4.4 Safety net

`parse_user_query` wraps `translate_query` in try/except. On any unexpected scanner error it falls back to the
**raw** query string (today's behavior) and logs a warning. The new layer can never regress below current
behavior; worst case equals the status quo.

---

## 5. Scanner token model

`scan()` is a single left-to-right char walk tracking **quote state** and **`[]`/`{}` bracket depth**. Token
kinds:

- **`FieldValue(field, value)`** — `field:value`, value a single bare token (no brackets). Recognized when,
  outside quotes/brackets, it sees `\w+:` followed by a non-bracket value. Value runs until whitespace, a
  resolved clause-comma, `)`, or end (may itself be quoted: `correspondent:"A B"`).
- **`FieldValueList(field, [v1, v2, …])`** — value-list, **only** for `field ∈ {tag, tag_id, viewer_id}`. A
  `FieldValue` whose value is immediately followed by `,term` runs with **no spaces and no colon** in the
  continuation terms. The no-colon rule fixes `tag:foo,type:bar` (the `type:bar` is not swallowed).
- **`FieldRange(field, open, lo, hi, close)`** — `field:[lo TO hi]` / `{…}`. Split on case-insensitive
  `TO`; `lo`/`hi` may be empty (open). Consumed to the matching close bracket.
- **`Comma`** — emitted only when a depth-0 comma resolves to a clause separator (see §7).
- **`Passthrough(raw)`** — everything else, byte-for-byte: operators (`AND OR NOT + -`), parens, bare words,
  wildcards, phrases/quoted spans, whitespace.

**Key properties**

- `field:value` is recognized at any paren depth but **never inside `[]`/`{}` or quotes** — so
  `(created:2020 OR foo)` still finds the date token, and commas inside `[2020 TO 2021]` or `"a,b"` are never
  clause separators.
- Only date fields (`created`, `modified`, `added`) trigger date translation. Every other `field:value` /
  `field:range` (`tag:`, `asn:`, unknown fields) and every `Passthrough` is re-emitted verbatim — preserving
  queries Tantivy already handles.
- Multi-valued set is exactly `{tag, tag_id, viewer_id}`. `custom_fields` is now a JSON structure in the index
  (Whoosh smashed it into a comma-keyword field; the JSON path handles it better) and is **not** comma-split.

---

## 6. `translate_date_value` — shape dispatch

One entry point per token type, both emitting `field:[<ISO-Z> TO <ISO-Z>]`. `created` uses date-only
(UTC-midnight) boundaries; `added`/`modified` use local-tz-midnight→UTC. All boundary math reuses the
existing tested helpers.

### Scalar value (`FieldValue` on a date field)

| Shape                   | Example                            | Result                                                        | Status      |
| ----------------------- | ---------------------------------- | ------------------------------------------------------------- | ----------- |
| Keyword (opt. quoted)   | `created:today`, `"previous week"` | existing keyword ranges                                       | works today |
| 4-digit `YYYY`          | `created:2020`                     | full-year span, emitted as `[2020-01-01T…Z TO 2021-01-01T…Z]` | NEW         |
| 6-digit `YYYYMM`        | `created:202003`                   | month span                                                    | NEW         |
| 8-digit `YYYYMMDD`      | `created:20200101`                 | day span                                                      | works today |
| 14-digit                | `…120000`                          | exact-second point `[t TO t]`                                 | works today |
| ISO dashed              | `created:2020-01`, `2020-01-01`    | strip separators → digit-precision span                       | NEW         |
| Bare relative `-N unit` | `created:-1week`                   | `[t TO t]` instant (effectively no-match, matches v2)         | NEW (P3)    |
| Invalid / unparsable    | `created:202023`                   | **no-match clause, never 400**                                | NEW         |

### Range (`FieldRange`)

Parse each bound with the same shape parser, then `floor(lo)` / `ceil(hi)`:

- Partial / ISO / 8-digit / 14-digit bounds: `[202001 TO 202006]`, `[2020-01-01 TO 2020-12-31]` — NEW.
- `now` bound: `[20200101 TO now]` — NEW.
- Open bound (empty side): `[2020 to]`, `[to 2020]` → sentinel far-past floor / far-future ceil (§8) — NEW.
- Relative bound: generalize existing `[-N unit to now]` so `-N unit` works on either side.
- Reversed (`lo>hi`): swap (existing year-range `min/max` + Whoosh `disambiguated` behavior).
- Bare year range `[2005 to 2009]`: unchanged (works today).

**Boundary convention:** keep the existing "ceil = start of next period, inclusive bracket" (e.g.
`[2005-01-01 .. 2010-01-01]`) that current tests encode. Do not switch to Whoosh's `23:59:59.999999`; document
the one-instant boundary difference.

---

## 7. Comma resolution

A depth-0 comma is resolved three ways (this single rule set subsumes both `fix/scope-comma-expansion` and
the unstaged `]`/`"` fix, and fixes Gap E):

1. **Value-list** — preceding token is a `FieldValue`/`FieldValueList` on `{tag, tag_id, viewer_id}` and the
   following continuation is a bare, colon-free term → repeat the field: `tag:a,b,c` → `tag:a AND tag:b AND tag:c`.
2. **Clause separator → `AND`** — fires only at a structured boundary:
   - (a) the comma is preceded by a closing `]` or `"` (`created:[r],added:[r]`, `correspondent:"A B",created:[r]`), or
   - (b) the comma is followed by a **known schema** `field:` (`title:foo,created:[r]`, `correspondent:foo,created:[r]`).
     Requiring a _known_ field for (b) prevents `http://x,…`-style misfires.
3. **Literal** — anything else (a comma followed by a bare term on a non-multivalue field) stays in place:
   `correspondent:foo,bar`, `title:10,20`, URLs. Tantivy's analyzer tokenizes these on punctuation, matching
   Whoosh's analyzer behavior.

---

## 8. Open-range handling & the two phases

**Phase 1 (this work) — string output, no tantivy change.**
Open bounds use verified string sentinels: lower-open → `0001-01-01T00:00:00Z`, upper-open → `9999-12-31T23:59:59Z`
(both confirmed to parse on a date field in 0.26.0). No-match (invalid date) uses a degenerate date range
(exact representation flagged for verification in §11).

**Phase 2 (stretch) — build `tantivy.Query` objects for date clauses.**
`Query.range_query(..., lower_bound=None/upper_bound=None)` gives true open bounds and `empty_query()` gives a
real no-match, eliminating all string hacks. **Gated only on a released `tantivy-py` > 0.26.0 that includes
#655 + #666 — the code already exists on `tantivy-py` `master`, it just postdates the `0.26.0` wheel we pin
(`pyproject.toml`: `tantivy~=0.26.0`); see §9.** Splicing a Query object into an otherwise-string boolean query
is non-trivial, so Phase 2 is a separate, later effort; Phase 1 ships independently.

Phase 2 also folds in the deferred Phase-1 cleanup (maintainer decision, 2026-06-15):

- Replace the `NO_MATCH` degenerate-range sentinel with `Query.empty_query()` (this also retires the cosmetic
  issue that `NO_MATCH` always names the `created` field regardless of the queried field).
- Replace `OPEN_LO`/`OPEN_HI` string sentinels with `range_query(..., None)` open bounds.
- Retire the now-dead `_rewrite_*` helpers and the `rewrite_natural_date_keywords`/`normalize_query` delegation
  shims in `_query.py` (~160 lines left from the Phase-1 transition), and migrate their string-output tests in
  `test_query.py` (replace the direct `_rewrite_compact_date` test with a `translate_scalar` test).

---

## 9. Upstream tantivy-py contribution (PR-ready detail)

> **STATUS UPDATE (2026-06-14): already implemented upstream on `master`.** The date-value gap below is
> closed by two merged `tantivy-py` commits that postdate the released `0.26.0` wheel we pin:
> **#655** (`feat: support unbounded range queries via None bounds`) and **#666** (`fix: add_date loses
tzinfo`, which added the `PyDateTime → tantivy DateTime` converter and routed both `range_query` and
> `term_query` through it). `range_query` with `datetime` (incl. `None` open bounds) and
> `term_query`/`term_set_query` with `datetime` on `Date` fields are verified working upstream with
> regression tests. **The Phase 2 blocker is therefore no longer a code contribution** — it is only a
> published `tantivy-py` release > `0.26.0` containing #655 + #666, plus bumping our pin
> (`pyproject.toml`: `tantivy~=0.26.0`). The PR-ready detail below is retained as the historical record of
> the gap as observed against `0.26.0`.

**Repo:** `quickwit-oss/tantivy-py`. **Observed version:** `0.26.0` (`tantivy v0.26.0, index_format v7`).

**Gap.** Python `datetime` objects cannot be passed to _any_ Query constructor for a `Date` field. Both
`Query.range_query` and `Query.term_query` reject them:

```
Expected DateTime type for field created, got datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
```

Int timestamps (seconds and nanoseconds) are also rejected, and there is no exposed/constructible
`tantivy.DateTime` (`hasattr(tantivy, "DateTime") is False`). Consequently **all** date querying in paperless
goes through `parse_query` strings; every object-mode `term_query` in the codebase is on integer fields
(`id`, `owner_id`, `viewer_id`).

**Context.** PR #655 (merged 2026-04-27) added unbounded (`None`) bounds to `range_query`. That solved open
_bounds_ but left the date _value_ path unusable from Python, so the open-range feature can't actually be used
on date fields from Python yet.

**Reproduction** (against installed 0.26.0):

```python
import tantivy
from datetime import datetime, UTC
schema = build_schema()  # any schema with a date field "created"
dt1, dt2 = datetime(2020,1,1,tzinfo=UTC), datetime(2021,1,1,tzinfo=UTC)

tantivy.Query.range_query(schema, "created", tantivy.FieldType.Date, lower_bound=dt1, upper_bound=dt2)
# -> ValueError: Expected DateTime type for field created, got datetime.datetime(...)

tantivy.Query.range_query(schema, "created", tantivy.FieldType.Date, lower_bound=dt1, upper_bound=None)
# -> same error (open bound is fine; the date VALUE is the problem)

tantivy.Query.term_query(schema, "created", dt1)
# -> same error
```

**Proposed fix (preferred):** in the Rust binding, when the target field is `Date`, accept a Python
`datetime` and convert internally to `tantivy::DateTime` (e.g. `DateTime::from_timestamp_nanos(...)`), mirroring
the conversion the indexing path already performs when adding date values to a document (document add-date
already accepts `PyDateTime`). This makes `range_query`/`term_query` consistent with indexing. The value-coercion
lives in the Query-construction value handling (the term/bound extraction in the query bindings, e.g.
`src/query.rs`); reuse the existing `PyDateTime → tantivy DateTime` converter from the document bindings rather
than adding a new one. Confirm exact locations against the tantivy-py source at PR time.

**Alternative:** expose a constructible `tantivy.DateTime` (from a Python `datetime` or an epoch-nanos int) and
accept it in `range_query`/`term_query`. Less ergonomic; only do this if reusing the indexing converter proves
awkward.

**Validation for the PR:**

- `range_query` on a `Date` field with two `datetime` bounds builds and returns expected hits.
- `range_query` with one `datetime` bound and one `None` (open) works on a `Date` field.
- `term_query` on a `Date` field with a `datetime` builds and matches.
- Round-trip: index a doc with a known date, query it back via both closed and open ranges.

When this lands and we bump tantivy-py to the release containing it, Phase 2 (§8) becomes unblocked.

---

## 10. Out of scope / known separate gaps

- **Unknown-field 400.** `http://example.com/a,b` → `Field does not exist: 'http'`. Tantivy treats `http:` as
  a field; Whoosh's `remove_unknown=True` degraded unknown fields to text. This is the unknown-field divergence,
  not a comma or date issue. Recorded, not fixed here.
- `>`/`<`/`>=`/`<=` comparisons — never supported in paperless-Whoosh.
- Bare relative scalar (`created:-1week`) is P3: it "worked" in v2 but matched nothing. We only guarantee
  no-400.

---

## 11. Items to verify during implementation

- Exact RFC3339 **open-bound sentinels** to standardize on (`0001-01-01T00:00:00Z` / `9999-12-31T23:59:59Z`
  both parse; confirm they also behave in actual searches, not just parsing).
- The **no-match clause** string representation for a date field (a degenerate/empty range that parses but
  matches nothing). In Phase 2 this becomes `empty_query()`.
- ISO-dashed precision handling parity with Whoosh's separator-stripping (`-`, `.`, space).
- Coordination with `fix/scope-comma-expansion`: either land this after that branch merges and delete its
  now-redundant regex, or absorb its narrowing directly. Do not ship both comma implementations.

---

## 12. Test plan (additive)

- **`test_translate.py` (new):**
  - `scan()` token-sequence tests: quotes, brackets, parens, URLs, value-lists, mixed clauses.
  - `translate_date_value` shape table: every §6 row (scalar + range), all three date fields,
    UTC/Eastern/Auckland timezones (reuse existing tz test patterns).
  - comma resolution: value-list (`tag`/`tag_id`/`viewer_id`), clause-sep (after `]`/`"`, before known
    `field:`), literal (text fields, URLs, `title:10,20`).
  - `translate_query()` golden cases: the full §3 / report-§5b ground-truth matrix.
- **Parse-acceptance guardrail (current tests lack this):** for every golden case assert
  `index.parse_query(translate_query(q))` does not raise, against a real index.
- **End-to-end:** a `views.py` search test asserting previously-400 v2 queries (`created:2020`,
  `created:[20200101 TO 20201231]`, `title:x,created:[…]`) now return 200.
- Existing tests stay green via delegation; on removal of the old functions, migrate any unique assertions
  into `test_translate.py`.

---

## 13. Verification harnesses (keep for regression / ground-truth regeneration)

**Tantivy side** (does a translated string parse?):

```bash
cd src && PAPERLESS_SECRET_KEY=x uv run python -c "
import django, os, tempfile
os.environ.setdefault('DJANGO_SETTINGS_MODULE','paperless.settings'); django.setup()
import tantivy
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers
from documents.search._query import DEFAULT_SEARCH_FIELDS, _FIELD_BOOSTS
idx = tantivy.Index(build_schema(), path=tempfile.mkdtemp()); register_tokenizers(idx,'english')
idx.parse_query('<translated string>', DEFAULT_SEARCH_FIELDS, field_boosts=_FIELD_BOOSTS)
"
```

**Whoosh side** (what did v2 do? — ground truth):

```bash
uv run --with cached_property python3 -W ignore -c "
import sys; sys.path.insert(0,'whoosh/src')
from datetime import datetime
from whoosh.fields import Schema, TEXT, DATETIME, KEYWORD
from whoosh.qparser import MultifieldParser
from whoosh.qparser.dateparse import DateParserPlugin
schema = Schema(title=TEXT(), content=TEXT(), correspondent=TEXT(),
  tag=KEYWORD(commas=True, lowercase=True), tag_id=KEYWORD(commas=True), viewer_id=KEYWORD(commas=True),
  type=TEXT(), created=DATETIME(), added=DATETIME(), modified=DATETIME(), notes=TEXT(), custom_fields=TEXT())
qp = MultifieldParser(['content','title','correspondent','tag','type','notes','custom_fields'], schema)
qp.add_plugin(DateParserPlugin(basedate=datetime(2026,6,14,14,0,0)))
print(qp.parse('<query>'))
"
```

---

## 14. Phased summary

- **Phase 1 (now):** `_translate.py` scanner + `translate_date_value`, string output, sentinel open bounds,
  delegation shims, additive tests, parse-acceptance guardrail, end-to-end 400→200 tests. Ships on tantivy
  0.26.0, no upstream dependency. Subsumes `fix/scope-comma-expansion`.
- **Phase 2 (later, gated on §9 upstream):** build `tantivy.Query` objects for date clauses — true open ranges
  via `range_query(None)`, real no-match via `empty_query()`, no string sentinels. Requires the tantivy-py
  date-value contribution and a version bump.
