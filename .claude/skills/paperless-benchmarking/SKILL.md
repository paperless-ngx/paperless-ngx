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
manage.py benchmark seed --tier {home,medium,large} [--reset --yes-i-know-this-wipes-the-database] [--seed N]
manage.py benchmark run --repeat 5 [--label baseline]
manage.py benchmark profile <scenario_name> [--repeat 5] [--explain]
manage.py benchmark list-scenarios
```

- **`seed`** builds a realistic dataset at one of three scales: `home` (500
  documents — fast, use this for iteration), `medium` (20,000 — the default
  when `--tier` is omitted; a multi-minute seed), `large` (360,000 — matches
  the scale reported in real large-install bug reports; slow, only use it
  when a finding needs confirming at real scale). `--reset` wipes any
  previously-seeded benchmark data first — but it is destructive and
  irreversible: it deletes **all** users, **all** groups, and **all**
  documents/tags/correspondents/document types/storage paths in the target
  database, not just benchmark-created rows. Only run it against a disposable
  benchmark database, never a real install. Because of that, `--reset` also
  requires passing `--yes-i-know-this-wipes-the-database` in the same
  invocation, or the command raises an error and does nothing. Omit both
  flags if you want to layer more data onto an existing seed instead. `seed`
  creates two named users, `perf_target` (mixed owned/shared documents,
  realistic guardian permission grants) and `perf_admin` (superuser), plus a
  general user/group pool with realistic permission-row ratios.
- **`run`** times the 3 built-in API endpoint benchmarks
  (`/api/documents/`, `/api/documents/?page_size=50`, `/api/tags/?page_size=100000`) for both
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

- **PostgreSQL** `EXPLAIN ANALYZE`: look for `Seq Scan` on a large table
  (missing index), a large gap between `rows=N` (planner's estimate) and the
  actual row count in parentheses (stale statistics or a bad cardinality
  estimate), and nested-loop joins driven by an outer relation with many
  rows (usually the N+1 pattern this tool exists to catch).
- **MariaDB**: verified against a real MariaDB 12.3 container that MariaDB
  does NOT accept MySQL 8.0.18+'s `EXPLAIN ANALYZE` syntax (it's a 1064
  syntax error) -- `capture_explain()` instead runs MariaDB's own
  `ANALYZE <statement>` form (no `EXPLAIN` keyword), which returns a
  tabular plan with real per-row execution columns: `rows` (estimate) vs.
  `r_rows` (actual), and `filtered` vs. `r_filtered`. A large gap between
  `rows` and `r_rows`, or `type: ALL` (full table scan) on a large table,
  are the signals to look for -- the same underlying concerns as Postgres's
  `Seq Scan`/estimate-vs-actual gap, just in MariaDB's column-based output
  instead of Postgres's nested-tree text format.
- **SQLite** `EXPLAIN QUERY PLAN`: no real timing/row-count data, only the
  chosen access path (`SCAN` vs `SEARCH`, which index if any). Useful for
  confirming an index is even being considered, not for judging real-world
  cost — corroborate any SQLite finding against Postgres/MariaDB before
  trusting it, since planner behavior differs meaningfully between them.
- Compare query **count**, not just timing, between before/after: a fix that
  keeps the same wall-clock time but drops query count from O(n) to O(1) is
  still a real, durable improvement — timing alone is noisy and
  environment-dependent, query count is not.

## Cleaning up after an interrupted run

If a `seed`/`run`/`profile` invocation gets killed mid-run (Ctrl-C, `kill -9`,
a timed-out SSH session, etc.), check whether it left anything behind before
trusting the next benchmark's numbers. This was verified for real: a
`benchmark seed --tier large --reset ...` was started against both a fresh
PostgreSQL 18 container and a fresh MariaDB 12.3 container and `kill -9`'d a
few seconds into document seeding. In both cases, the database-side
connection disappeared immediately -- no stuck backend, no lingering query,
no held lock was observed in either backend once the killed process's PID
was confirmed gone. That said, this was one interruption point (mid
bulk-seed, between chunks); a run killed mid-query, or a driver/network
hiccup that doesn't cleanly close the socket, could behave differently, so
still check before trusting a number if any run in the session was
interrupted:

- **PostgreSQL**: look for leftover connections against the benchmark
  database:

  ```sql
  SELECT pid, state, query, query_start
  FROM pg_stat_activity
  WHERE datname = current_database() AND pid <> pg_backend_pid();
  ```

  If a stuck backend shows up, clear it with:

  ```sql
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = current_database() AND pid <> pg_backend_pid();
  ```

- **MariaDB**: look for leftover connections/queries:

  ```sql
  SHOW FULL PROCESSLIST;
  ```

  If a stuck connection shows up (anything other than your current admin
  session), clear it with:

  ```sql
  KILL <id>;
  ```

A stray connection left running concurrently with a subsequent benchmark run
would add real, contaminating load (extra queries competing for the same
rows, possibly held locks slowing the next run's timings) -- cheap to rule
out, expensive to silently trust a number that was actually measured
alongside a zombie connection.

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
