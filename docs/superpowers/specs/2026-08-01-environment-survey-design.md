# Opt-in environment survey design

## Problem

Since NumPy 2.4.0, official wheels require a minimum CPU baseline of
`x86-64-v2` (SSE4.2 and related instructions), with no runtime fallback.
Paperless-ngx depends on NumPy (via scikit-learn for the classifier, and via
ocrmypdf/fpdf2 during consumption itself), so any CPU below that baseline
crashes with SIGILL. This is documented in `docs/migration-v3.md`, with
`PAPERLESS_TRAIN_TASK_CRON=disable` given as the mitigation for classifier
training - but that mitigation turns out to be incomplete:

- [discussion #13325](https://github.com/paperless-ngx/paperless-ngx/discussions/13325)
  and [discussion #13235](https://github.com/paperless-ngx/paperless-ngx/discussions/13235)
  (2026) - SIGILL reports traced back to the SSE4.2 baseline, including a
  user on an Intel Core2 Quad Q9500.
- [#13429](https://github.com/paperless-ngx/paperless-ngx/issues/13429) (2026,
  open) - the SSE4.2 baseline also breaks document consumption itself (via
  ocrmypdf/fpdf2's use of NumPy), even with `PAPERLESS_TRAIN_TASK_CRON=disable`
  set. The only current workaround is unofficial and unsupported (manually
  downgrading to `numpy<2.4` inside the container). A maintainer is looking
  into whether upstream (NumPy) would be open to a fix, but nothing is
  settled yet.

The maintainers have no data on how many real installs actually fall below
this floor (roughly pre-2008 Intel / pre-2011 AMD hardware, though #13429's
reporter's Core2 Quad Q9500 - a 2008-era chip - shows the real-world edge is
fuzzier than the nominal cutoff) versus how many are unaffected. This design
proposes a way to gather that signal.

## Goals

- Give maintainers enough real-world hardware/deployment data to make an
  informed decision on the SSE4.2/x86-64-v2 NumPy baseline (and similar
  future ISA-dependent dependency choices), without guessing from bug report
  volume alone.
- Be maximally transparent and opt-in: no data leaves an instance without an
  admin explicitly running a command and confirming exactly what will be
  sent.
- Work correctly on the hardware most likely to be affected - detection must
  not itself crash on the CPUs it's trying to identify.
- Give participants a straightforward way to see what's stored about them
  and remove it.

## Non-goals

- This is not a recurring/background telemetry feature. There is no opt-in
  _setting_, no Celery schedule, no periodic check-in.
- This is not a public analytics dashboard. The data is internal input for
  maintainer decisions, not a published report (a public summary could be a
  future follow-up, but is out of scope here).
- This does not attempt to catalog every possible deployment variable. Scope
  is limited to what's plausibly relevant to ISA/hardware-driven
  compatibility decisions.
- No submission history/trend tracking. Only current state per participant.

## Client: standalone, not-installed-by-default app

Rather than a management command tucked into an existing app (which would
run every time regardless, just gated by which flags are passed), this lives
in its own Django app, e.g. `paperless_survey`, that is **not** in
`INSTALLED_APPS` unless explicitly enabled via an env var, e.g.
`PAPERLESS_ENVIRONMENT_SURVEY_ENABLED=true`, following the same conditional-
app pattern already used for `channels` (gated on `DEBUG`) and `cachalot`
(gated on its own settings) in `paperless/settings/__init__.py`.

This is a stronger opt-in signal than a command flag: with the env var unset
(the default), the app's code is never imported, the management command
doesn't exist, and it doesn't even appear in `manage.py help`. An admin has
to deliberately turn it on before any of this machinery is reachable at all.

The app contains a single management command, `collect_environment_info`,
in `paperless_survey/management/commands/`.

### Behavior

- Run with no flags: gathers the payload, prints a plain-English explanation
  of what the command does and why, then prints the full JSON payload. Does
  nothing else. No network activity.
- `--submit`: does the above, then prints the destination URL and asks for
  `y/N` confirmation before POSTing. `--yes` skips the interactive prompt
  (for scripted/automated use by an admin who has already reviewed the
  output once).
- `--forget`: deletes the local installation ID file (see below) and sends a
  delete request for that ID to the collection endpoint. Also confirms
  before acting, unless `--yes` is passed.

### CPU/hardware detection

Detection must not import `numpy`, `scipy`, or `scikit-learn` - those are
exactly the packages that can SIGILL on the hardware this survey is trying
to characterize, so importing any of them in the detection path would
silently exclude the worst-case machines from the dataset.

Instead, read `/proc/cpuinfo` directly via stdlib `open()`:

- x86: parse the `flags` line for `sse4_2`, `avx`, `avx2`, `avx512f`, etc.
- ARM: parse the `Features` line for `asimd`/`neon`, etc.
- If `/proc/cpuinfo` doesn't exist or isn't parseable (non-Linux host, odd
  container setup), the relevant fields are reported as `"undetected"`
  rather than raising.

Architecture comes from `platform.machine()`, core count from
`os.cpu_count()`, RAM from `/proc/meminfo` (same crash-safety reasoning as
CPU flags applies here too - stdlib only, no numpy).

### Payload fields

| Field               | Source                                                     | Notes                                                                |
| ------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------- |
| `installation_id`   | local ID file (see below)                                  | opaque UUID                                                          |
| `cpu_flags`         | `/proc/cpuinfo`                                            | sse4_2/avx/avx2/avx512f/neon presence, `"undetected"` if unavailable |
| `architecture`      | `platform.machine()`                                       | e.g. `x86_64`, `aarch64`                                             |
| `cpu_count`         | `os.cpu_count()`                                           |                                                                      |
| `ram_total_mb`      | `/proc/meminfo`                                            | rounded, not exact                                                   |
| `paperless_version` | package metadata                                           |                                                                      |
| `python_version`    | `platform.python_version()`                                |                                                                      |
| `db_backend`        | Django settings                                            | `postgresql`/`mysql`/`sqlite3`, no credentials                       |
| `install_method`    | best-effort inference, falls back to an interactive prompt | e.g. `docker`, `bare-metal`, `unknown`                               |
| `ai_enabled`        | settings                                                   | boolean                                                              |
| `embedding_backend` | settings                                                   | only meaningful if `ai_enabled`                                      |
| `doc_count_bucket`  | DB count, bucketed                                         | `<100`, `100-1k`, `1k-10k`, `10k+` - never an exact count            |

Explicitly excluded: IP address, document content, filenames, tags,
hostname, exact document count, usernames, any other PII.

### Installation ID

- A random UUID (`uuid4`), generated locally the first time `--submit` runs,
  written to a small local file (not the Django DB - a plain file makes
  deletion legible: delete the file, the ID is gone).
- Never derived from hardware identifiers, MAC address, or hostname - purely
  opaque, cannot itself be used as a fingerprint.
- Scoped narrowly to enabling update-in-place and self-service deletion, not
  for tracking or correlating behavior over time.
- Printed with a one-line explanation every time the payload preview is
  shown.

### Update semantics

Resubmitting with `--submit` while a local ID file already exists silently
upserts the existing server-side row (same ID) and bumps `last_updated`;
`first_seen` is set once and never changes. No history of prior submissions
is kept - only current state. The payload preview notes when this is an
update to an existing submission versus a first-time one.

## Server: Cloudflare Worker + D1

Lives outside the paperless-ngx repository, in maintainer-owned
infrastructure. Source is published in a public repo/gist so the collection
endpoint itself is independently auditable, reinforcing the "nothing
hidden" goal.

- **Storage:** Cloudflare D1 (SQL), single table keyed by `installation_id`.
  Chosen over KV (poor fit for aggregate querying) and Analytics Engine
  (built for high-volume/lossy writes; this is low-volume, opt-in, and
  needs exact upsert/delete semantics).
- **Endpoints:**
  - `POST /submit` - upserts a row by `installation_id`, validates the
    payload shape, rejects unexpected fields.
  - `DELETE /submit/{installation_id}` - deletes the row.
- **Abuse mitigation:** Cloudflare's built-in rate limiting. No auth token,
  since this is intentionally a public opt-in write/delete-by-id endpoint.
- **Logging:** the Worker must not log or persist source IP addresses
  alongside submissions.

## Rollout

- Add a new section to `docs/migration-v3.md`, adjacent to the existing
  "Minimum CPU Requirements (NumPy Baseline)" section, describing the survey,
  the `PAPERLESS_ENVIRONMENT_SURVEY_ENABLED` env var needed to turn it on,
  what it collects, and how to run/forget it.
- Open a pinned GitHub discussion inviting users - especially those on older
  hardware - to opt in, linking #13429, #13325, and #13235 for context.

## Testing

- Unit tests for payload construction: mock `/proc/cpuinfo` and
  `/proc/meminfo` contents (including a missing/unparsable case), mock
  `platform`/`os.cpu_count`, and Django settings, asserting the resulting
  payload shape and the `"undetected"` fallback behavior.
- Unit tests for the local installation ID file lifecycle: first-run
  creation, reuse on subsequent runs, and removal via `--forget`.
- No live HTTP call is exercised in the test suite; the `--submit`/`--forget`
  network path is smoke-tested manually against the Worker rather than
  mocked in CI, consistent with this repo's existing pattern of gating real
  external-service tests behind markers (`live`, `gotenberg`, etc.) rather
  than mocking network boundaries by default.
- The Cloudflare Worker has no test coverage in this repository; it is
  out-of-repo infrastructure.
