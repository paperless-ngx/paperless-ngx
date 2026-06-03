# Usage Reporting — Technical Spec

Voluntary, opt-in usage reporting for paperless-ngx. The goal is to
understand how many instances are running a given release (especially
beta), which platforms and architectures are in use, and what features
are being deployed — without collecting any personal data or document
content.

---

## Guiding principles

- **Explicitly opt-in.** Nothing is sent automatically. The user runs
  the command and confirms before any network call is made.
- **Transparent.** The exact payload is shown before sending.
- **Anonymous.** The UUID is a random identifier with no link to
  identity, IP address, or hostname.
- **Graceful.** Network failures produce a friendly message, never a
  stack trace.

---

## Client — management command

### Name

```
manage.py send_usage_report
```

### Flags

| Flag        | Behaviour                                                 |
| ----------- | --------------------------------------------------------- |
| _(none)_    | Show payload, prompt for confirmation, send on `y`/`yes`  |
| `--dry-run` | Show payload, skip confirmation and network call entirely |

### UUID storage

A random UUID4 is generated on the first run and written to
`PAPERLESS_DATA_DIR/usage_uuid` (plain text, one line). Subsequent
runs reuse the same file. If the file is missing it is regenerated
(counts as a new install — acceptable).

### Confirmation flow

```
The following information will be sent to paperless-ngx to help
improve the project:

  Installation ID : a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Version         : 2.15.0
  Channel         : beta
  Commit          : bd86dca57  (built 2026-05-18T12:00:00Z)
  Install type    : docker
  Architecture    : x86_64
  Python          : 3.12.3
  Database        : postgresql
  Documents       : 1000–9999
  Multi-user      : yes
  Mail enabled    : yes
  AI enabled      : no

No personal data, document content, or IP address is stored.
More information: https://docs.paperless-ngx.com/usage-reporting/

Send this report? [y/N]:
```

Default answer is **N**. Anything other than `y`/`yes` aborts with
no network call and prints `Nothing sent.`

`--dry-run` skips the prompt entirely and prints `Dry run — nothing sent.`

### Network error handling

- Timeout: 10 seconds
- On any failure (timeout, DNS, HTTP error): print a single friendly
  line, exit 0 (not an error from the user's perspective)

```
Could not reach the reporting endpoint. Nothing was sent.
```

### Duplicate submission handling

The server returns `429` if the UUID was seen within the last 7 days,
with a JSON body:

```json
{
  "error": "already_submitted",
  "last_sent": "2026-05-15T10:00:00Z",
  "retry_after_days": 4
}
```

The command prints:

```
Already submitted 3 days ago. Nothing sent.
You can send again after 2026-05-19.
```

---

## Payload schema

All fields are strings unless noted. Fields marked _omit if absent_
are left out of the JSON entirely when the value is unavailable —
never sent as `null`.

| Field          | Source                                                    | Notes                                            |
| -------------- | --------------------------------------------------------- | ------------------------------------------------ |
| `uuid`         | `PAPERLESS_DATA_DIR/usage_uuid`                           | UUID4, random                                    |
| `version`      | `paperless/version.py` — `__full_version_str__`           | e.g. `"2.15.0"`                                  |
| `channel`      | `paperless/version.py` — `__channel__`                    | `"stable"` \| `"beta"` \| `"dev"`                |
| `commit`       | `paperless/build_info.py` — `SOURCE_COMMIT`               | Short SHA — _omit if absent_                     |
| `build_date`   | `paperless/build_info.py` — `BUILD_DATE`                  | ISO 8601 — _omit if absent_                      |
| `install_type` | Detected at runtime (see below)                           |                                                  |
| `arch`         | `platform.machine()`                                      | e.g. `"x86_64"`, `"aarch64"`                     |
| `python`       | `platform.python_version()`                               | e.g. `"3.12.3"`                                  |
| `database`     | Last segment of `settings.DATABASES["default"]["ENGINE"]` | e.g. `"postgresql"`, `"sqlite3"`                 |
| `doc_bucket`   | Bucketed document count (see below)                       |                                                  |
| `multi_user`   | boolean                                                   | `true` if more than one real user account exists |
| `feature_mail` | boolean                                                   | `true` if any mail account is configured         |
| `feature_ai`   | boolean                                                   | `true` if AI features are enabled in settings    |

### Document count buckets

| Range         | Value           |
| ------------- | --------------- |
| 0–99          | `"0-99"`        |
| 100–999       | `"100-999"`     |
| 1 000–9 999   | `"1000-9999"`   |
| 10 000–49 999 | `"10000-49999"` |
| 50 000+       | `"50000+"`      |

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
| `"source"`     | Fallback — dev checkout                                     |

Distro packagers (Debian, NixOS community, Unraid, etc.) can opt in
by shipping a `src/paperless/distro_info.py` containing:

```python
DISTRO = "debian"   # or "rpm", "homebrew", "unraid", etc.
```

When present the install type is reported as the `DISTRO` value rather
than `"distro"`.

### `version.py` additions

Add `__channel__` alongside the existing version fields:

```python
__channel__: Final[str] = "beta"   # "stable" | "beta" | "dev"
```

This is the canonical place to set the channel when preparing a
release. `"dev"` is the default for unreleased branches.

### `build_info.py`

Generated at build time, never committed (add to `.gitignore`).

```python
SOURCE_COMMIT = "bd86dca57"
BUILD_DATE = "2026-05-18T12:00:00Z"
```

---

## Server — Cloudflare Worker

Managed in a separate repository under the paperless-ngx GitHub org
(e.g. `paperless-ngx/telemetry`). Deployed via Wrangler.

### Endpoint

```
POST /report
Content-Type: application/json
```

Returns `204` on success. No response body.

### Timestamp

`received` is always set server-side. Any client-supplied timestamp
field is ignored.

### Validation

Reject with `400` if any of the following fail:

- `uuid` does not match UUID4 format
- `version` does not match `\d+\.\d+\.\d+`
- `channel` is not one of `stable`, `beta`, `dev`
- `install_type` is not in the known set
- `arch` is absent
- Payload is not valid JSON or exceeds 4 KB

Unknown extra fields are silently ignored (forward compatibility).

### Deduplication

Before inserting, query for the most recent submission from this UUID:

```sql
SELECT received FROM reports
WHERE uuid = ?
ORDER BY received DESC
LIMIT 1
```

If the result is within 7 days of now, return:

```
HTTP 429
{ "error": "already_submitted", "last_sent": "<iso>", "retry_after_days": <n> }
```

Otherwise insert and return `204`.

### D1 schema

```sql
CREATE TABLE reports (
  id            INTEGER PRIMARY KEY,
  received      TEXT    NOT NULL,   -- ISO 8601, server-side
  uuid          TEXT    NOT NULL,
  version       TEXT,
  channel       TEXT,
  commit        TEXT,
  build_date    TEXT,
  install_type  TEXT,
  arch          TEXT,
  python        TEXT,
  database      TEXT,
  doc_bucket    TEXT,
  multi_user    INTEGER,            -- 0 / 1
  feature_mail  INTEGER,            -- 0 / 1
  feature_ai    INTEGER             -- 0 / 1
);

CREATE INDEX idx_reports_uuid    ON reports(uuid);
CREATE INDEX idx_reports_channel ON reports(channel);
CREATE INDEX idx_reports_version ON reports(version);
```

---

## Useful queries

```sql
-- Distinct beta installs
SELECT COUNT(DISTINCT uuid)
FROM reports
WHERE channel = 'beta';

-- Installs by commit (beta only)
SELECT commit, COUNT(DISTINCT uuid) AS installs
FROM reports
WHERE channel = 'beta'
GROUP BY commit
ORDER BY installs DESC;

-- Architecture breakdown
SELECT arch, COUNT(DISTINCT uuid) AS installs
FROM reports
GROUP BY arch
ORDER BY installs DESC;

-- Install type split
SELECT install_type, COUNT(DISTINCT uuid) AS installs
FROM reports
GROUP BY install_type
ORDER BY installs DESC;

-- Database backend split
SELECT database, COUNT(DISTINCT uuid) AS installs
FROM reports
GROUP BY database
ORDER BY installs DESC;
```

---

## Out of scope (for now)

- Automatic or scheduled reporting
- Any opt-out settings flag
- Server-side dashboard (raw SQL is sufficient)
- Locale, timezone, or OS version fields
