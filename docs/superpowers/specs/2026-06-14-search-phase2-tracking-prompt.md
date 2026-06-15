# Agent prompt: add tracking todo for search Phase 2 (Whoosh→Tantivy date queries)

Paste the block below to the paperless-ngx agent. It is self-contained.

---

**Add a tracking todo for search Phase 2 (Whoosh→Tantivy date queries).**

Context discovered while reviewing the upstream `tantivy-py` library against
`docs/superpowers/specs/2026-06-14-search-query-translation-design.md`:

- §9 of that spec describes an "upstream tantivy-py contribution" needed before Phase 2:
  making Python `datetime` objects work in `Query.range_query` / `Query.term_query` on
  `Date` fields.
- **That contribution is already implemented on `tantivy-py` `master`** — it just postdates
  the released `0.26.0` wheel the spec was tested against. Two commits close the gap:
  **#655** (`feat: support unbounded range queries via None bounds`) and **#666**
  (`fix: add_date loses tzinfo`, which added the `PyDateTime → tantivy DateTime` converter
  and routed both `range_query` and `term_query` through it). `range_query` with `datetime`
  (incl. `None` open bounds) and `term_query`/`term_set_query` with `datetime` on `Date`
  fields were all verified working, and regression tests were added upstream.
- So the Phase 2 blocker is **no longer a code contribution** — it is simply **a released
  `tantivy-py` version newer than the current `0.26.0` wheel that includes #655 + #666**,
  plus the dependency bump on our side.

Please create a tracking todo (in whatever issue/todo system this repo uses) capturing:

1. **Title:** "Unblock search Phase 2: bump tantivy-py once a release includes datetime query
   support (#655 + #666)."
2. **Trigger:** A `tantivy-py` release > the current `0.26.0` wheel containing both commits is
   published to PyPI.
3. **Action when unblocked:** Bump the `tantivy-py` pin, then execute Phase 2 from the design
   doc — replace Phase 1's string-sentinel open bounds (`0001-01-01…Z` / `9999-12-31…Z`) and
   degenerate no-match ranges with real `tantivy.Query` objects (`range_query(..., None)` for
   open bounds, `empty_query()` for no-match).
4. **Doc update:** Note in §8/§9 of
   `docs/superpowers/specs/2026-06-14-search-query-translation-design.md` that the upstream
   code already exists on master and only a release + bump remains.

Do not start Phase 2 implementation now — this is only a tracking todo. Confirm the current
pinned `tantivy-py` version in our dependency files when writing it.
