---
name: paperless-benchmarking
description: Use when profiling paperless-ngx performance, running `manage.py benchmark`, investigating a slow query or endpoint, or deciding whether a profiling finding should become a permanent registered scenario. Covers command reference, the fork/merge-back branch workflow for perf investigations, and how to read query-plan output.
---

# Paperless-ngx Benchmarking

This repo has a built-in benchmarking/profiling tool: `manage.py benchmark`, in
the `paperless_benchmark` Django app. It replaces ad hoc standalone scripts —
use it instead of writing new one-off seed/timing scripts.

## Command reference

```
manage.py benchmark seed --tier {home,medium,large} [--reset] [--seed N]
manage.py benchmark run --repeat 5 [--label baseline]
manage.py benchmark profile <scenario_name> [--repeat 5] [--explain]
manage.py benchmark list-scenarios
```

- **`seed`** builds a realistic dataset at one of three scales: `home` (500
  documents — fast, use this for iteration), `medium` (20,000), `large`
  (360,000 — matches the scale reported in real large-install bug reports;
  slow, only use it when a finding needs confirming at real scale). `--reset`
  wipes any previously-seeded benchmark data first — always pass it unless you
  specifically want to layer more data onto an existing seed. `seed` creates
  two named users, `perf_target` (mixed owned/shared documents, realistic
  guardian permission grants) and `perf_admin` (superuser), plus a general
  user/group pool with realistic permission-row ratios.
- **`run`** times the 3 built-in API endpoint benchmarks
  (`/api/documents/`, `/api/documents/?page_size=50`, `/api/tags/`) for both
  `perf_target` and `perf_admin`, reporting min/median/max wall-clock and SQL
  query count. Requires `seed` to have already run — it reuses that data, it
  does not seed its own.
- **`profile`** times one named scenario from the registry (see
  `list-scenarios`) via best-of-N repeat timing and SQL query count, against
  `perf_target`. `--explain` additionally captures and prints the query plan:
  real `EXPLAIN ANALYZE` execution stats on PostgreSQL/MariaDB, or
  `EXPLAIN QUERY PLAN` (plan only, no real timing/row counts — clearly labeled
  as such) on SQLite. Like `run`, `profile` requires `seed` to have already
  run — it does not seed its own data either.
- Every `run`/`profile` invocation appends a JSON line to
  `benchmark_results/history.jsonl` at the repo root (local-only, gitignored —
  never commit this file). Use it to compare a `before`/`after` pair across
  two invocations without hand-copying numbers.
- Full chain example: `seed --reset` once, then `run` and `profile` as many
  times as you want against that same seeded data — no need to reseed between
  them.

## Adding a new scenario

A "scenario" is a named, registered query/operation that `profile` can time
and explain. To add one, edit `src/paperless_benchmark/scenarios.py`: write a
`_<name>_run(user)` function (returns whatever `run_profile` should time) and
optionally a `_<name>_queryset(user)` function (returns the `QuerySet` for
`--explain` to analyze), then `register(Scenario(name=..., describe=...,
run=..., queryset_for_explain=...))` at module level. Both functions receive
the already-seeded `perf_target` user — they should not seed their own data.

## Branch workflow

`tools/benchmark-management-commands` is a **long-lived tooling branch**, not
a feature branch that gets merged and closed:

1. It is periodically brought up to date with `dev` (merge `dev` into it) so
   the tooling doesn't drift from the schema/codebase it profiles. Do this
   before starting a new investigation if it's been a while since the last
   sync.
2. **Every performance investigation forks its own branch from
   `tools/benchmark-management-commands`** (not from `dev`). Do the
   investigation there: write throwaway profiling code, try fixes, capture
   before/after numbers.
3. **That investigation branch never merges into `dev` or production.** Its
   only job is to produce evidence and, optionally, a reusable scenario.
4. If the investigation turns up a scenario worth keeping permanently (see
   "When to graduate a scenario" below), open a PR that adds **just that
   scenario** back into `tools/benchmark-management-commands` — not the rest
   of the investigation branch's throwaway code.
5. Any actual production fix the investigation motivates (e.g. an ORM query
   change) goes into its own normal feature branch off `dev`, following the
   project's regular contribution process — profiling evidence informs that
   PR's description, but the profiling code itself does not travel with it.

## Reading query-plan output

- **PostgreSQL/MariaDB** `EXPLAIN ANALYZE`: look for `Seq Scan` on a large
  table (missing index), a large gap between `rows=N` (planner's estimate)
  and the actual row count in parentheses (stale statistics or a bad
  cardinality estimate), and nested-loop joins driven by an outer relation
  with many rows (usually the N+1 pattern this tool exists to catch).
- **SQLite** `EXPLAIN QUERY PLAN`: no real timing/row-count data, only the
  chosen access path (`SCAN` vs `SEARCH`, which index if any). Useful for
  confirming an index is even being considered, not for judging real-world
  cost — corroborate any SQLite finding against Postgres/MariaDB before
  trusting it, since planner behavior differs meaningfully between them.
- Compare query **count**, not just timing, between before/after: a fix that
  keeps the same wall-clock time but drops query count from O(n) to O(1) is
  still a real, durable improvement — timing alone is noisy and
  environment-dependent, query count is not.

## When to graduate a one-off finding into a permanent scenario

Register a scenario (rather than leaving it as throwaway code on the
investigation branch) when **both** are true:

- The query pattern is one this codebase is likely to regress on again (e.g.
  it involves a permission-check join, a bulk operation, or anything else
  with an easy-to-reintroduce N+1) — not a one-time fluke specific to this
  investigation.
- Re-running it later, against a fresh seed, would still produce a
  meaningful signal (it doesn't depend on investigation-specific throwaway
  data or a fix that's already permanently landed and can't regress the same
  way).

If a finding doesn't meet both bars, keep it as disposable code on the
investigation branch and let the branch's evidence (captured in the PR
description of whatever production fix it motivates) be the permanent
record instead.
