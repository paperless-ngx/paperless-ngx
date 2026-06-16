# Export Zip Compression Control — Design

**Date:** 2026-06-16
**Branch base:** `dev`
**Status:** Draft — **depends on** `2026-06-16-export-sink-architecture-design.md`
being implemented first.

## Prerequisite

This builds directly on the export sink refactor. It assumes `ZipExportSink`
already exists and is the single place that owns `zipfile.ZipFile` creation and
entry writes. Do not start this until that refactor has landed; without it, the
change would have to touch the command's zip branches again.

## Problem

Zip export is hardwired to `ZIP_DEFLATED` at the library default level. Users
have no way to trade speed against archive size — a fast `ZIP_STORED` pass for a
quick local copy, or a maximal `ZIP_LZMA` pass for the smallest off-site backup.
The sink refactor turns "which compression" into a single constructor argument,
so exposing it is now a small, isolated change.

## Goal

Let the operator choose the zip compression method and level from the CLI, with
behavior identical to today when the flags are omitted. All knowledge of
compression stays inside `ZipExportSink`; the command only parses flags and maps
them to sink arguments.

## Scope

In scope:

- `ZipExportSink` gains `compression: int` and `compresslevel: int | None`
  constructor parameters (default `ZIP_DEFLATED`, `None` → library default),
  passed straight to `zipfile.ZipFile(...)`.
- New `document_exporter` flags: `--zip-compression` and
  `--zip-compression-level`, valid only with `--zip`.
- Validation: method availability, level range per method, and the
  requires-`--zip` guard.
- Import-side compatibility notes/tests (the importer already decompresses
  transparently via `ZipFile.extractall`).

Out of scope:

- Compression for any non-zip sink (folder has none; a future S3 sink would
  handle its own object storage compression separately).
- Changing the default. Omitting the flags must produce a byte-compatible-method
  archive to today's (`ZIP_DEFLATED`, default level).

## Design

### `ZipExportSink` changes

```python
def __init__(
    self,
    target: Path,
    zip_name: str,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    compresslevel: int | None = None,
) -> None:
    ...
    # opened in __enter__:
    self._zip = zipfile.ZipFile(
        self._tmp_path,
        "w",
        compression=compression,
        compresslevel=compresslevel,
        allowZip64=True,
    )
```

`ZipFile` applies `compression`/`compresslevel` as the default for every
`write`/`writestr`, so `add_file` / `add_json` / the manifest entry need no
changes. Directory marker entries are unaffected (they carry no data).

### CLI flags (`document_exporter`)

- `--zip-compression {stored,deflated,bzip2,lzma}` — and `zstd` **when the
  runtime supports it** (see below). Maps to the matching `zipfile.ZIP_*`
  constant. Default `deflated`.
- `--zip-compression-level N` — integer. Meaningful for `deflated` (0–9) and
  `bzip2` (1–9); ignored by `stored` and `lzma`; for `zstd` the accepted range
  follows the stdlib (negative … 22). Default: unset → library default.

Both flags require `--zip`; passing either without `--zip` raises a
`CommandError`, matching the incremental-flag rule from the base refactor.

### Validation (in `handle()`, before constructing the sink)

1. **Requires `--zip`.** Either flag without `--zip` → `CommandError`.
2. **Method availability.** `bzip2`/`lzma` need the `bz2`/`lzma` stdlib modules
   (normally present, but optional in some Python builds); `zstd` needs
   Python 3.14+. If the chosen method's module is unavailable, raise a
   `CommandError` naming the missing capability rather than failing deep in
   `zipfile`.
3. **Level range.** Reject an out-of-range `--zip-compression-level` for the
   chosen method with a clear message; accept-and-note that it is ignored for
   `stored`/`lzma`.

### zstd (Python 3.14+)

Python 3.14 adds Zstandard support to `zipfile` (`ZIP_ZSTANDARD`, backed by the
new `compression.zstd` module, PEP 784). Gate it at runtime:

```python
_ZSTD = getattr(zipfile, "ZIP_ZSTANDARD", None)  # None before 3.14
```

Only include `zstd` in the `--zip-compression` choices when `_ZSTD is not None`.
Because the project targets Python ≥3.11, the code must not import or reference
`compression.zstd` unconditionally.

### Import-side compatibility

`document_importer` reads zips with `ZipFile(self.source).extractall(...)`
(`document_importer.py:453`), which decompresses each entry transparently using
whatever method it was stored with — **provided the matching module exists on the
importing machine.** Consequences to document (and test):

- `deflated`/`stored`: universally importable.
- `bzip2`/`lzma`: importable wherever the `bz2`/`lzma` modules are present
  (essentially always).
- `zstd`: importable only on Python 3.14+. An archive compressed with `zstd` is
  **not** importable on older runtimes. Call this out in the docs/help text for
  the flag so users don't pick an archive format their import target can't read.

## Testing

New cases in the sink tests and an export→import round-trip
(pytest classes, factory-boy, `mocker`, `parametrize`, typed; run on the VM):

- **Round-trip per method.** Parametrize over the available methods (skip `zstd`
  below 3.14, skip `bzip2`/`lzma` if the module is somehow absent): export a
  small library, import it back, assert documents/manifest match.
- **Method is applied.** Assert each written entry's `compress_type` equals the
  requested method (read back via `ZipFile.infolist()`).
- **Level affects size.** For `deflated`, assert level 9 produces an archive no
  larger than level 1 on compressible content (loose `<=` to avoid flakiness).
- **Validation.** Each flag without `--zip` → `CommandError`; out-of-range level
  → `CommandError`; unavailable method (simulate via `mocker` patching the
  capability probe) → `CommandError`.
- **Default unchanged.** Omitting both flags yields entries with
  `compress_type == ZIP_DEFLATED`, identical to pre-feature behavior.

## Risks

- **Foot-gun archives.** A user could produce a `zstd`/`lzma` archive their
  import target can't read. Mitigation: explicit help text and the import-side
  notes above; the default stays the universally-readable `deflated`.
- **Optional-module assumptions.** Don't assume `bz2`/`lzma` are always compiled
  in; probe and error clearly. Mitigation: the availability validation step.
