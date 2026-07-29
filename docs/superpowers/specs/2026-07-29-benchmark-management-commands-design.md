# Benchmark management commands — design

## Goal

Replace the standalone root scripts (`run_benchmarks.py`, `seed_benchmark_data.py`) and
the Postgres-only `tools/profiling` branch harness (`profiling/harness.py`,
`profiling/seed.py`) with one Django management command suite that any contributor
can run against any of the 3 supported DB backends (PostgreSQL, MariaDB, SQLite)
without standalone-script env-var bootstrapping.

## Background

- **Root scripts** (`run_benchmarks.py`, `seed_benchmark_data.py`, currently untracked
  at repo root on `feature-vecstore-v2`): standalone scripts driven by `PAPERLESS_DB*`
  env vars. Seed tiered datasets (`home`/`medium`/`large`) using the project's
  factory-boy factories (`documents/tests/factories.py`) via `build_batch()` +
  `bulk_create()`, then time API endpoints (document list, tag list) with
  min/median/max wall-clock and SQL query counts, printed as a table.
- **`tools/profiling` branch** (`origin/tools/profiling`, ~130 commits behind `dev`):
  a pytest-based harness for one specific investigation — a guardian-permission N+1
  query pathology. `profiling/harness.py` provides `run_profile()` (repeat-timing +
  query-count capture) and `capture_explain_analyze()`; `profiling/seed.py` seeds a
  dataset with realistic ownership/permission-row ratios (from real bug reports
  #13276, #11950). Deliberately Postgres-only via `require_postgres()`, plus its own
  throwaway-container scripts (`run_with_postgres.sh`, `stop_postgres.sh`) and an
  append-only, git-tracked `profiling/results/history.jsonl`.

These are two genres of the same underlying need — reproducible, realistically-scaled
data plus query/timing instrumentation — that grew independently. This design merges
them into one tool.

## Decisions

1. **Unify into one benchmark command suite.** Cross-backend endpoint
   timing/query-count benchmarking is the primary mode; Postgres/MariaDB-only
   `EXPLAIN ANALYZE` profiling becomes an optional mode within the same structure
   (not a separate tool).
2. **One `benchmark` management command with subcommands** (`seed`, `run`, `profile`,
   `list-scenarios`) via argparse subparsers — one entry point, shared setup.
3. **Explain support is per-backend, not Postgres-only.** PostgreSQL and MariaDB both
   support `EXPLAIN ANALYZE` (real execution stats). SQLite only supports
   `EXPLAIN QUERY PLAN` (plan only, no real timing/row counts) — the `profile`
   subcommand runs on all three backends, with SQLite output clearly labeled as
   plan-only rather than being skipped.
4. **New app `paperless_benchmark`**, not folded into `documents/`. Lives in
   `src/paperless_benchmark/`, added unconditionally to `INSTALLED_APPS` in
   `paperless/settings/__init__.py` (required for `manage.py` to discover its
   commands — no models/migrations needed otherwise). No DEBUG/env gating; same
   footprint as any other management-command-only app as long as imports stay lazy
   inside command handlers.
5. **Profile scenarios are a pluggable registry**, not a single fixed investigation.
   The existing guardian-permission investigation becomes the first registered
   scenario (`guardian_permission_visibility`); future perf investigations register
   their own scenario function instead of editing a monolith.
6. **Results are local-only, gitignored.** Written to `benchmark_results/` at repo
   root (added to `.gitignore`), not committed — avoids checking in machine-specific
   timing numbers that go stale immediately. Structure (append-only JSONL history)
   is preserved from `profiling/harness.py`'s `append_profiling_history`, just
   relocated.
7. **Built as a fresh branch off current `dev`**, not by continuing `tools/profiling`'s
   history (which is ~130 commits stale with unrelated locale/UI/backend drift).
   Only the relevant logic is ported: `ScaleProfile` seeding ratios, `run_profile()`,
   `capture_explain_analyze()` (generalized per-backend), and the history-log format.
   `tools/profiling` itself is left untouched — not merged, not deleted.
8. **No formal pytest coverage required.** This is dev-only tooling, not shipped
   product code — skip the usual test-suite requirement for this branch of work.

## Architecture

```
src/paperless_benchmark/
├── __init__.py
├── apps.py                        # PaperlessBenchmarkConfig
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── benchmark.py           # entry point, argparse subparsers: seed / run / profile / list-scenarios
├── seeding.py                     # tiered dataset builder (merges seed_benchmark_data.py + profiling/seed.py)
├── endpoints.py                   # timed API-endpoint scenarios (from run_benchmarks.py)
├── db.py                          # per-backend reset/truncate + explain helpers (vendor-dispatched)
├── scenarios.py                   # pluggable profile-scenario registry
└── results.py                     # history.jsonl writer (from profiling/harness.py's append_profiling_history)
```

## Command surface

```
manage.py benchmark seed --tier {home,medium,large} [--reset] [--seed N]
manage.py benchmark run --repeat 5 [--label baseline]
manage.py benchmark profile <scenario_name> [--repeat 5] [--explain]
manage.py benchmark list-scenarios
```

- `seed`/`run`/`profile` operate against whatever DB backend Django is currently
  configured against (the normal `PAPERLESS_DB*` settings paperless already
  resolves at startup) — no separate env-var protocol is needed once this lives
  inside `manage.py`.
- Tiers: keep the `home`/`medium`/`large` naming from the root scripts, but adopt
  `profiling/seed.py`'s empirically-grounded counts and ratios (real ownership
  fractions, real guardian-permission-row ratios from issues #13276/#11950).

## Backend abstraction (`db.py`)

- `reset_benchmark_data()` — vendor-dispatched truncate:
  - **PostgreSQL**: `TRUNCATE ... CASCADE` (existing logic from `seed_benchmark_data.py`).
  - **MariaDB**: per-table `TRUNCATE` wrapped in `SET FOREIGN_KEY_CHECKS=0` /
    `=1`, since MariaDB's `TRUNCATE` doesn't support `CASCADE`.
  - **SQLite**: existing ORM-delete fallback (`Document.global_objects.all().delete()`, etc).
- `capture_explain(queryset)` — vendor-dispatched:
  - **PostgreSQL / MariaDB** → `EXPLAIN ANALYZE` (real execution stats).
  - **SQLite** → `EXPLAIN QUERY PLAN`, output prefixed
    `(plan only — no execution stats on SQLite)`.

## Scenario registry (`scenarios.py`)

```python
@dataclass(frozen=True)
class Scenario:
    name: str
    describe: str
    run: Callable[[], Any]                       # the query/operation under test
    queryset_for_explain: Callable[[], QuerySet] | None = None

_SCENARIOS: dict[str, Scenario] = {}

def register(scenario: Scenario) -> None: ...
def get(name: str) -> Scenario: ...               # raises CommandError on unknown name
def all_scenarios() -> Iterable[Scenario]: ...
```

The guardian-permission investigation from `tools/profiling` (Stage 1: raw
`get_objects_for_user_owner_aware` query count; Stage 2: loop-resolution fix)
registers as `guardian_permission_visibility`.

## Results storage

`benchmark_results/` at repo root, added to `.gitignore`. `run`/`profile` write:

1. A human-readable stdout table (existing format — user/endpoint/queries/min/median/max).
2. An appended JSON line to `benchmark_results/history.jsonl`: timestamp, code ref
   (`git rev-parse --short HEAD`), stage/scenario name, scale tier, best-seconds,
   query count — same shape as `profiling/harness.py`'s `append_profiling_history`.

## Migration / cleanup

- New branch off current `dev` (working name: `tools/benchmark-management-commands`),
  built in a fresh git worktree.
- Delete root `run_benchmarks.py` and `seed_benchmark_data.py` once their logic is
  ported into `seeding.py`/`endpoints.py`.
- Port `profiling/seed.py` (`ScaleProfile`, permission-ratio seeding) and
  `profiling/harness.py` (`run_profile`, `capture_explain_analyze`,
  `append_profiling_history`) logic into the new app.
- `tools/profiling` branch is left as-is — not merged, not deleted.
- `VECTOR_STORE_PERF_BACKLOG.md` / `VECTOR_STORE_TABLES_GATEWAY_SPEC.md` at repo
  root are unrelated (existing vector-store work on `feature-vecstore-v2`) — left
  untouched by this work.

## Out of scope

- Formal pytest coverage for the new app (explicitly waived — dev tooling).
- Any change to `tools/profiling`'s existing branch history.
- CI wiring (this tooling is not intended to run in CI, only ad hoc by developers).
