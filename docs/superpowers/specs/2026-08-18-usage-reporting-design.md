# Usage & Environment Reporting Design

Consolidates two prior specs that independently proposed overlapping
opt-in "phone home" designs: `telemetry-spec.md` (general version/platform/
feature adoption reporting) and `2026-08-01-environment-survey-design.md`
(hardware-capability data for ISA-dependent dependency decisions, motivated
by NumPy's SSE4.2/x86-64-v2 baseline). Both are superseded by this document.

## Problem

Paperless-ngx has no visibility into its install base today: which
versions/channels are actually running, what platforms and databases are in
use, which optional features (mail, AI) are enabled, or what hardware is
underneath. Two motivating threads:

- **General adoption/support signal.** Maintainers currently have no data on
  how many instances run a given release (especially beta), what platforms
  and architectures are in use, or which optional features are deployed -
  informed guesses only, from bug report volume.
- **Hardware-capability decisions.** NumPy 2.4.0+ official wheels require an
  `x86-64-v2` (SSE4.2) CPU baseline with no runtime fallback; paperless-ngx
  depends on NumPy via scikit-learn (classifier) and ocrmypdf/fpdf2
  (consumption). [Discussion #13325](https://github.com/paperless-ngx/paperless-ngx/discussions/13325),
  [discussion #13235](https://github.com/paperless-ngx/paperless-ngx/discussions/13235),
  and [issue #13429](https://github.com/paperless-ngx/paperless-ngx/issues/13429)
  all trace SIGILL crashes to this baseline, including a user on a 2008-era
  Intel Core2 Quad Q9500. **#13429 is now closed as fixed** (bumping fpdf2 to
  2.8.8, shipping in 3.1) - the specific fire that originally motivated this
  design is out. The underlying need is not: the same class of ISA-dependent
  dependency decision will come up again, and maintainers will again have no
  real-world hardware distribution data to inform it when it does.

This design combines both needs into one opt-in reporting mechanism rather
than shipping two separate, overlapping ones.

## Goals

- Give maintainers real install-base data: version/channel adoption,
  platform/install method, database backend, feature usage (mail, AI +
  embedding backend), multi-user usage, document-count scale - without
  guessing from bug report volume alone.
- Give maintainers real-world hardware/CPU-capability data for future
  ISA-dependent dependency decisions (the NumPy baseline case being the
  first, not the last, example of this class of decision).
- Explicitly opt-in at every layer, not just one: the reporting code isn't
  even installed by default; the command's default behavior is fully inert
  regardless of how it's invoked or scripted; and even the explicit send
  path defaults to declining. All three independent gates (see "Three
  independent opt-in gates" below) must be deliberately crossed before any
  data leaves an instance.
- Detection must not itself crash on the hardware it's trying to
  characterize - the CPU/environment detection path must not import
  `numpy`, `scipy`, or `scikit-learn`.
- Anonymous: an opaque UUID, never derived from hardware identifiers, IP, or
  hostname.
- Participants can see current stored state and remove it on demand.

## Non-goals

- No automatic or scheduled reporting. There is no opt-in _setting_, no
  Celery schedule, no periodic check-in - purely a manually-invoked command.
- No opt-out settings flag - there's no "on" state to opt out of.
- No public analytics dashboard. The data is internal input for maintainer
  decisions (a future public summary is possible, out of scope here).
- No submission-history/trend tracking. Each installation is one current-
  state row, upserted on every submission - not a time series.
- Not a general crash-reporting/analytics pipeline. Scope stays to the
  fields listed below.

## Client: standalone, not-installed-by-default app

Lives in its own Django app, `paperless_survey`, **not** in `INSTALLED_APPS`
unless explicitly enabled via `PAPERLESS_ENVIRONMENT_SURVEY_ENABLED=true`,
following the same conditional-app pattern already used for `channels`
(gated on `DEBUG`) and `cachalot` (gated on its own settings) in
`paperless/settings/__init__.py`.

With the env var unset (the default), the app's code is never imported, the
management command doesn't exist, and it doesn't appear in `manage.py
help`. An admin has to deliberately enable it before any of this machinery
is reachable at all - a stronger opt-in signal than "a command exists but
you have to know to run it."

The app contains a single management command, `send_usage_report`, in
`paperless_survey/management/commands/`.

### Three independent opt-in gates

No data can leave an instance without all three of these being true:

1. **The app is enabled at all** - `PAPERLESS_ENVIRONMENT_SURVEY_ENABLED=true`
   must be set, or the command doesn't exist.
2. **The send path is explicitly requested** - running the command with no
   arguments (or `--dry-run`) is the default and is fully inert: it prints
   the payload and explanation and does nothing else, no matter how it's
   invoked or scripted. The `y/N` confirmation prompt and the network call
   only become reachable at all when `--submit` is passed explicitly. There
   is no combination of default behavior or flag that sends data by
   accident.
3. **The prompt is explicitly accepted** - even with `--submit`, the
   confirmation defaults to **N**; only `y`/`yes` proceeds.

`--yes` (skip the interactive prompt, for scripted use by an admin who has
already reviewed the output once) only has an effect combined with
`--submit` - alone, or combined with the inert default/`--dry-run` mode,
there is nothing to confirm, so it's a no-op.

### Flags

| Flag        | Behaviour                                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------ |
| _(none)_    | Gather payload, print plain-English explanation + full payload. No prompt, no network call.                        |
| `--dry-run` | Identical to no flags - explicit alias, for scripts that want to state their intent unambiguously.                 |
| `--submit`  | Required to reach the confirmation prompt and network call at all. Prompts `y/N`, sends only on yes.               |
| `--yes`     | Skip the interactive confirmation prompt - only meaningful combined with `--submit`; otherwise a no-op.            |
| `--forget`  | Delete stored data for this installation - see below. Has its own `y/N` confirmation, also skippable with `--yes`. |

Default answer to the `--submit` confirmation prompt is **N**. Anything
other than `y`/`yes` aborts with no network call and prints `Nothing sent.`

### Confirmation flow

Shown only when `--submit` is passed (`manage.py send_usage_report --submit`):

```
The following information will be sent to paperless-ngx to help
improve the project:

  Installation ID  : a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Version          : 2.15.0
  Channel          : beta
  Commit           : bd86dca57  (built 2026-05-18T12:00:00Z)
  Install type     : docker
  Architecture     : x86_64
  CPU flags        : sse4_2, avx2
  CPU count        : 8
  RAM (MB)         : 16384
  Python           : 3.12.3
  Database         : postgresql
  Documents        : 1000-9999
  Multi-user       : yes
  Mail enabled     : yes
  AI enabled       : no

No personal data, document content, IP address, or hostname is stored.
More information: https://docs.paperless-ngx.com/usage-reporting/

Send this report? [y/N]:
```

This is a first-time submission for installation ID a1b2c3d4-... - if a
local ID file already exists, the preview instead reads "This will update
your existing report" (see Update semantics below).

### Network error handling

- Timeout: 10 seconds.
- On any failure (timeout, DNS, HTTP error): print a single friendly line,
  exit 0 (not an error from the user's perspective).

```
Could not reach the reporting endpoint. Nothing was sent.
```

### CPU/hardware detection

Detection must not import `numpy`, `scipy`, or `scikit-learn` - those are
exactly the packages that can SIGILL on the hardware this data is meant to
characterize, so importing any of them in the detection path would silently
exclude the worst-case machines from the dataset.

Instead, read `/proc/cpuinfo` directly via stdlib `open()`:

- x86: parse the `flags` line for `sse4_2`, `avx`, `avx2`, `avx512f`, etc.
- ARM: parse the `Features` line for `asimd`/`neon`, etc.
- If `/proc/cpuinfo` doesn't exist or isn't parseable (non-Linux host, odd
  container setup), the relevant fields are reported as `"undetected"`
  rather than raising.

Architecture comes from `platform.machine()`, core count from
`os.cpu_count()`, RAM from `/proc/meminfo` (same crash-safety reasoning
applies - stdlib only, no numpy).

### Install type detection

Evaluated in order; first match wins.

| Value          | Detection                                                   |
| -------------- | ----------------------------------------------------------- |
| `"kubernetes"` | `KUBERNETES_SERVICE_HOST` env var is set                    |
| `"podman"`     | `container` env var equals `"podman"`                       |
| `"docker"`     | `Path("/.dockerenv").exists()`                              |
| `"nixos"`      | `"/nix/store/"` in `sys.executable`                         |
| `"snap"`       | `SNAP` env var is set                                       |
| `"flatpak"`    | `FLATPAK_ID` env var is set                                 |
| `"distro"`     | `paperless/distro_info.py` exists (set by distro packagers) |
| `"release"`    | `paperless/build_info.py` exists (none of the above)        |
| `"source"`     | Fallback - dev checkout                                     |

Distro packagers (Debian, NixOS community, Unraid, etc.) can opt in by
shipping a `src/paperless/distro_info.py` containing:

```python
DISTRO = "debian"   # or "rpm", "homebrew", "unraid", etc.
```

When present, install type is reported as the `DISTRO` value rather than
`"distro"`.

### Payload schema

All fields are strings/numbers unless noted. Fields marked _omit if absent_
are left out of the JSON entirely when unavailable - never sent as `null`.

| Field               | Source                                                        | Notes                                                                      |
| ------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `installation_id`   | local ID file (see below)                                     | opaque UUID4                                                               |
| `paperless_version` | `paperless/version.py` - `__full_version_str__`               | e.g. `"2.15.0"`                                                            |
| `channel`           | `paperless/version.py` - `__channel__` (new field, see below) | `"stable"` \| `"beta"` \| `"dev"`                                          |
| `commit`            | `paperless/build_info.py` - `SOURCE_COMMIT`                   | Short SHA - _omit if absent_                                               |
| `build_date`        | `paperless/build_info.py` - `BUILD_DATE`                      | ISO 8601 - _omit if absent_                                                |
| `install_type`      | Detected at runtime (see above)                               |                                                                            |
| `architecture`      | `platform.machine()`                                          | e.g. `"x86_64"`, `"aarch64"`                                               |
| `cpu_flags`         | `/proc/cpuinfo`                                               | sse4_2/avx/avx2/avx512f/neon presence, `"undetected"` if unavailable       |
| `cpu_count`         | `os.cpu_count()`                                              |                                                                            |
| `ram_total_mb`      | `/proc/meminfo`                                               | rounded, not exact                                                         |
| `python_version`    | `platform.python_version()`                                   | e.g. `"3.12.3"`                                                            |
| `db_backend`        | last segment of `settings.DATABASES["default"]["ENGINE"]`     | e.g. `"postgresql"`, `"sqlite3"`                                           |
| `doc_count_bucket`  | bucketed document count (see below)                           |                                                                            |
| `multi_user`        | boolean                                                       | `true` if more than one real user account exists                           |
| `feature_mail`      | boolean                                                       | `true` if any mail account is configured                                   |
| `feature_ai`        | boolean                                                       | `true` if AI features are enabled in settings                              |
| `embedding_backend` | settings                                                      | only meaningful/present if `feature_ai` is true - _omit if not applicable_ |

Explicitly excluded: IP address, document content, filenames, tags,
hostname, exact document count, usernames, any other PII.

### Document count buckets

| Range         | Value           |
| ------------- | --------------- |
| 0-99          | `"0-99"`        |
| 100-999       | `"100-999"`     |
| 1 000-9 999   | `"1000-9999"`   |
| 10 000-49 999 | `"10000-49999"` |
| 50 000+       | `"50000+"`      |

### Installation ID

- A random UUID4, generated locally the first time it's needed (`--submit`
  or first `--forget`), written to a small local file (not the Django DB -
  a plain file makes deletion legible: delete the file, the ID is gone).
- Never derived from hardware identifiers, MAC address, or hostname -
  purely opaque, cannot itself be used as a fingerprint.
- Printed with a one-line explanation every time the payload preview is
  shown.
- If the file is missing on a resubmission, it's regenerated (counts as a
  new install server-side - acceptable, consistent with the file being the
  sole source of truth for identity).

### `--forget`

Deletes stored data for this installation:

1. If no local ID file exists, print `Nothing to forget.` and exit - no
   network call.
2. Otherwise, confirm (unless `--yes`), then send
   `DELETE /submit/{installation_id}` to the collection endpoint.
3. On success (`204`): delete the local ID file, print
   `Deleted. Nothing more is stored for this installation.`
4. On network failure: print the same friendly network-error message as
   `--submit` uses, and **do not** delete the local file - the user can
   retry `--forget` later. Deleting the local file before confirming the
   server-side delete succeeded would orphan the ID with no way to retry
   the deletion request against it.

### `version.py` additions

Add `__channel__` alongside the existing version fields:

```python
__channel__: Final[str] = "beta"   # "stable" | "beta" | "dev"
```

This is the canonical place to set the channel when preparing a release.
`"dev"` is the default for unreleased branches.

### `build_info.py`

Generated at build time, never committed (add to `.gitignore`).

```python
SOURCE_COMMIT = "bd86dca57"
BUILD_DATE = "2026-05-18T12:00:00Z"
```

### Update semantics

Resubmitting with no flags (or `--yes`) while a local ID file already
exists upserts the existing server-side row (same ID) and bumps
`last_updated`; `first_seen` is set once and never changes. No history of
prior submissions is kept - only current state. The payload preview notes
whether this is a first-time submission or an update to an existing one.

## Server: Cloudflare Worker + D1

Lives outside the paperless-ngx repository, in maintainer-owned
infrastructure (e.g. `paperless-ngx/telemetry`), deployed via Wrangler.
Source is published in a public repo/gist so the collection endpoint itself
is independently auditable.

### Endpoints

- **`POST /submit`** - upserts a row by `installation_id`. Returns `204` on
  success, no response body.
- **`DELETE /submit/{installation_id}`** - deletes the row. Returns `204`
  whether or not the row existed (idempotent).

### Timestamps

`received`/`last_updated` are always set server-side. Any client-supplied
timestamp field is ignored. `first_seen` is set on first insert only, never
overwritten on subsequent upserts.

### Validation

Reject with `400` if any of the following fail:

- `installation_id` does not match UUID4 format
- `paperless_version` does not match `\d+\.\d+\.\d+`
- `channel` is not one of `stable`, `beta`, `dev` (when present)
- `install_type` is not in the known set
- `architecture` is absent
- Payload is not valid JSON or exceeds 4 KB

Unknown extra fields are silently ignored (forward compatibility).

### Abuse mitigation

Cloudflare's built-in rate limiting. No auth token, since this is
intentionally a public opt-in upsert/delete-by-id endpoint. No
application-level duplicate-submission throttle is needed - unlike a
per-submission insert model, an upsert is idempotent, so there's no
"spam" risk from resubmitting; repeated identical submissions just
re-write the same row.

### Logging

The Worker must not log or persist source IP addresses alongside
submissions.

### D1 schema

```sql
CREATE TABLE reports (
  installation_id   TEXT PRIMARY KEY,
  first_seen        TEXT    NOT NULL,   -- ISO 8601, server-side, set once
  last_updated       TEXT    NOT NULL,   -- ISO 8601, server-side, bumped on every upsert
  paperless_version TEXT,
  channel           TEXT,
  commit            TEXT,
  build_date        TEXT,
  install_type      TEXT,
  architecture      TEXT,
  cpu_flags         TEXT,
  cpu_count         INTEGER,
  ram_total_mb      INTEGER,
  python_version    TEXT,
  db_backend        TEXT,
  doc_count_bucket  TEXT,
  multi_user        INTEGER,            -- 0 / 1
  feature_mail      INTEGER,            -- 0 / 1
  feature_ai        INTEGER,            -- 0 / 1
  embedding_backend TEXT
);

CREATE INDEX idx_reports_channel ON reports(channel);
CREATE INDEX idx_reports_version ON reports(paperless_version);
```

### Useful queries

```sql
-- Distinct beta installs
SELECT COUNT(*) FROM reports WHERE channel = 'beta';

-- Installs by commit (beta only)
SELECT commit, COUNT(*) AS installs
FROM reports
WHERE channel = 'beta'
GROUP BY commit
ORDER BY installs DESC;

-- Architecture / CPU-flag breakdown (e.g. how many installs lack sse4_2)
SELECT architecture, cpu_flags, COUNT(*) AS installs
FROM reports
GROUP BY architecture, cpu_flags
ORDER BY installs DESC;

-- Install type split
SELECT install_type, COUNT(*) AS installs
FROM reports
GROUP BY install_type
ORDER BY installs DESC;

-- Database backend split
SELECT db_backend, COUNT(*) AS installs
FROM reports
GROUP BY db_backend
ORDER BY installs DESC;
```

## Rollout

- Add a new section to `docs/migration-v3.md`, adjacent to the existing
  "Minimum CPU Requirements (NumPy Baseline)" section (which should also be
  updated separately to reflect #13429's resolution via fpdf2 2.8.8 -
  independent of this rollout), describing the reporting tool, the
  `PAPERLESS_ENVIRONMENT_SURVEY_ENABLED` env var needed to enable it, what
  it collects, and how to run/forget it.
- Optionally open a pinned GitHub discussion inviting users - especially
  those on older hardware - to opt in, linking the historical #13429/
  #13325/#13235 threads as context for why hardware data specifically is
  useful.

## Testing

- Unit tests for payload construction: mock `/proc/cpuinfo` and
  `/proc/meminfo` contents (including a missing/unparsable case), mock
  `platform`/`os.cpu_count`, package/version metadata, and Django settings,
  asserting the resulting payload shape and the `"undetected"` fallback
  behavior.
- Unit tests for the local installation ID file lifecycle: first-run
  creation, reuse on subsequent runs, and removal via `--forget` (including
  the "no local file, `--forget` is a no-op" and "network failure during
  `--forget` keeps the local file" cases).
- Unit tests for the confirmation flow: default-N abort, `y`/`yes`
  acceptance, `--dry-run` never prompting/never sending, `--yes` skipping
  the prompt.
- Unit test for the network-failure path: mocked timeout/DNS/HTTP error
  produces the friendly message and exits 0, not a stack trace.
- No live HTTP call is exercised in the test suite; the network path is
  smoke-tested manually against the Worker rather than mocked in CI,
  consistent with this repo's existing pattern of gating real
  external-service tests behind markers (`live`, `gotenberg`, etc.) rather
  than mocking network boundaries by default.
- The Cloudflare Worker has no test coverage in this repository; it is
  out-of-repo infrastructure.
