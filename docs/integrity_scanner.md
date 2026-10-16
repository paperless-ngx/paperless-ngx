# Go file integrity scanner

The normal `document_sanity_checker` command and scheduled Celery sanity task
use `paperless-integrity-scanner` for media inventory, readability checks and
streaming SHA-256 checksums. Python retains ORM access, archive metadata pairing,
OCR-content checks, logging and Rich command output. There is no Python fallback.
The SHA-256 format is unchanged from compatibility commit
`d7a98944001b88567377e3e5bc9a7f4d3d3e1f2b`; no database migration or checksum
conversion is needed. Existing CLI options and the command's successful exit
after displaying document findings are unchanged. Infrastructure/protocol failures
raise `CommandError` (nonzero exit); the Celery task also fails rather than
claiming a clean archive.

## Linux installation

Docker builds compile the scanner in a pinned Go 1.26.9 multi-stage build and
install the static binary at `/usr/local/bin/paperless-integrity-scanner`.
The final image does not require a Go runtime. Buildx passes `TARGETOS` and
`TARGETARCH`, supporting the existing Linux amd64 and arm64 images.

For a source/bare-metal checkout, install Go 1.26.9 from
[the official downloads](https://go.dev/dl/) and verify its published SHA-256.
For Linux amd64, an unprivileged installation is:

```bash
mkdir -p "$HOME/.local"
curl --fail --location --silent --show-error \
  https://go.dev/dl/go1.26.9.linux-amd64.tar.gz \
  -o "$HOME/.local/go1.26.9.linux-amd64.tar.gz"
echo '42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d  '"$HOME/.local/go1.26.9.linux-amd64.tar.gz" | sha256sum --check
tar -xzf "$HOME/.local/go1.26.9.linux-amd64.tar.gz" -C "$HOME/.local"
export PATH="$HOME/.local/go/bin:$HOME/.local/bin:$PATH"

# From the repository root:
make -C native/integrity install
```

For Linux arm64 use `go1.26.9.linux-arm64.tar.gz`, whose published SHA-256 is
`4a97373d49fcacdcf3694fea368a500b00ee3e963974f3e7514132717632f052`.
The module has no third-party Go dependencies. Its toolchain version is pinned
in `native/integrity/go.mod`. Builds disable CGO, trim build paths and omit
the build ID for reproducible binaries with the same toolchain and target.
`make -C native/integrity install PREFIX=/usr/local` installs system-wide when
run by a user with the necessary write permissions.

Make the installed binary accessible to **both** management commands and Celery
workers. Service accounts may have a different PATH; set, for example:

```ini
PAPERLESS_INTEGRITY_SCANNER_BINARY=/opt/paperless/.local/bin/paperless-integrity-scanner
PAPERLESS_INTEGRITY_SCANNER_TIMEOUT=3600
```

The binary setting is one executable path, never a shell command or argument
string. Timeout is a positive integer in seconds (default 3600). Increase it for
very large archives or slow storage. Rebuild/reinstall after scanner source
updates and restart services after changing their configuration. Run as the
normal Paperless user: root can bypass file permissions and mask unreadability.

With the existing Python setup installed:

```bash
export PAPERLESS_SECRET_KEY=local-development-only
mkdir -p consume media
uv run --no-sync python src/manage.py document_sanity_checker --no-progress-bar
```

## Protocol version 1

Python starts the executable with an argument array, sends exactly one UTF-8 JSON
object on stdin and closes stdin. Paths are JSON strings (spaces/Unicode require
no shell escaping). Go emits exactly one JSON response on stdout; stderr is for
diagnostics. Unknown request fields, unsupported versions/algorithms, invalid
types, missing arrays, invalid IDs/kinds and additional JSON values are rejected.

Request fields:

| Field                | Type         | Meaning                                                    |
| -------------------- | ------------ | ---------------------------------------------------------- |
| `version`            | integer      | Must be `1`.                                               |
| `media_root`         | string       | Absolute media root; a configured root symlink is allowed. |
| `checksum_algorithm` | string       | Must be `sha256`.                                          |
| `files`              | array        | Expected-file entries described below.                     |
| `ignored_filenames`  | string array | Basenames from `IGNORABLE_FILES`; inventory only.          |
| `excluded_paths`     | string array | Media lock and configured logo paths; inventory only.      |

Each expected-file entry contains `document_id` (positive integer), `kind`
(`original`, `archive`, `thumbnail`), `path` (absolute under the configured root,
or relative to it) and `checksum` (stored checksum string; empty for thumbnails).
Python deliberately supplies unresolved file paths so Go can detect unsafe
symlinks. Expected files are still checked even when their names are ignored or
excluded from orphan detection. Inconsistent archive filename/checksum pairs
are handled in Python, exactly as before, without checking that archive file.

Example request:

```json
{
  "version": 1,
  "media_root": "/srv/paperless/media",
  "checksum_algorithm": "sha256",
  "files": [
    {
      "document_id": 7,
      "kind": "original",
      "path": "/srv/paperless/media/documents/originals/invoice 雪.pdf",
      "checksum": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    }
  ],
  "ignored_filenames": [".DS_Store"],
  "excluded_paths": ["/srv/paperless/media/media.lock"]
}
```

Response fields are `version` (integer `1`), `complete` (boolean), `checked_files`
(integer count of expected-file checks) and `findings` (array). Every finding has
all of these fields:

| Field             | Type            | Meaning                                                                                 |
| ----------------- | --------------- | --------------------------------------------------------------------------------------- |
| `code`            | string          | `missing`, `unreadable`, `checksum_mismatch`, `unsafe_path`, `orphan`, or `scan_error`. |
| `file_index`      | integer or null | Zero-based request file index; null for inventory findings.                             |
| `path`            | string          | Request path for file findings; inventory path otherwise.                               |
| `detail`          | string          | OS/change/safety diagnostic, or empty.                                                  |
| `actual_checksum` | string          | Lowercase SHA-256 for mismatches; empty otherwise.                                      |

Example clean response:

```json
{ "version": 1, "complete": true, "checked_files": 1, "findings": [] }
```

Ordinary file findings have exit status zero and `complete: true`, not a clean
verdict: Python maps missing/unreadable/mismatched files and unsafe paths to
errors, and orphans to global warnings using the existing messages. `scan_error`
(inaccessible directories, vanished inventory entries, interrupted traversal,
missing root) means `complete: false` and exit status 2. Invalid input or output
write failures also exit 2. Python rejects nonzero exits, malformed responses,
invalid finding references/checksums, unsupported versions, incomplete status
and unexpected checked-file counts. It never renders a clean result for these.

## Safety and concurrency

- The scanner opens files read-only; it does not repair, move, rewrite or delete.
- Inventory does not follow directory symlinks, matching the previous Python
  glob. Safe internal file aliases are canonicalized/deduplicated. External
  symlinks, parent escapes and symlink loops produce explicit `unsafe_path`
  errors. All file content and directory reads are rooted using Go `os.Root`,
  enforcing containment even if symlinks change between validation and opening.
- Special files are not read; nonblocking open and regular-file verification
  prevent a concurrent replacement with a FIFO from hanging the checker.
- Reads use a fixed 64 KiB buffer. Descriptor and path identity, size, mode,
  modification time and Linux change time are compared before/after reads;
  byte count and symlink target are checked too. Observable removal, replacement
  or change yields an unreadable finding or scan error, not a crash/clean result.
- This is not a filesystem snapshot: arbitrary writes after a completed check,
  or unobservable writes, cannot be made atomically consistent. Inventory and
  JSON memory scale with file/finding counts, not document byte size.
- SIGINT/SIGTERM cancel Go traversal/reads. Python terminates and reaps the
  subprocess on interruption/timeout, escalating to kill after five seconds.

## Tests and diagnostics

```bash
export PATH="$HOME/.local/go/bin:$HOME/.local/bin:$PATH"
make -C native/integrity test install
uv sync --frozen --python 3.12.13 --group testing --group lint --group typing
uv run --no-sync pytest src/documents/tests/test_integrity_scanner.py \
  src/documents/tests/test_sanity_check.py \
  src/documents/tests/management/test_management_sanity_checker.py \
  src/documents/tests/test_management_exporter.py src/documents/tests/test_tasks.py
```

The backend CI installs the pinned Go toolchain, runs race tests/vet/format checks
and installs the scanner before Python tests. Go tests use synthetic files,
including a sparse 128 MiB file with an allocation ceiling and synchronized
concurrent removal/replacement/change. Python integration tests execute the
real Go ELF binary through the command, and cover subprocess/protocol failures.

`Cannot start integrity scanner` means the binary is missing, not executable or
not available on the worker PATH. `Invalid integrity scanner response` usually
means the wrong/incompatible executable or truncated output. `scan incomplete`
includes scanner diagnostics: fix root/directory permissions or storage errors
and rerun. A timeout requires investigation or a larger timeout. Permission
regressions should be run unprivileged, since root bypasses permissions.
