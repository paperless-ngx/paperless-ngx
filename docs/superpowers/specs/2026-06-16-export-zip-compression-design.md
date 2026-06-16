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
- Import-side: a pre-extract support check in `document_importer` that turns an
  unsupported codec into a clear `CommandError` (the importer otherwise decompresses
  transparently via `ZipFile.extractall`).
- Docs: add both flags and the zstd-portability caveat to `docs/administration.md`
  (the `document_exporter` option list, lines ~257-270 and the `-z`/`-zn` section,
  lines ~328-330). New flags are long-form only (`--zip-compression`,
  `--zip-compression-level`) — no short aliases, to avoid `-zc`/`-zl` collisions
  with the existing `-z`/`-zn`.

Out of scope:

- Compression for any non-zip sink (folder has none; a future S3 sink would
  handle its own object storage compression separately).
- Changing the default. Omitting the flags must produce a byte-compatible-method
  archive to today's (`ZIP_DEFLATED`, default level).

## Design

### `ZipExportSink` changes

The base sink's signature is `ZipExportSink(target, zip_name, *, delete)`; this
adds two keyword-only params after `delete`:

```python
def __init__(
    self,
    target: Path,
    zip_name: str,
    *,
    delete: bool = False,
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
`write`/`writestr` (verified: a `ZipFile(..., compression=ZIP_BZIP2)` yields
entries with `compress_type == ZIP_BZIP2` without per-call args), so `add_file` /
`add_json` / the manifest entry need no changes. Directory marker entries are
empty so their compressed payload is zero, but they are still _tagged_ with the
chosen `compress_type` — harmless, but tests that read `infolist()` should filter
or account for marker entries (see Testing).

### CLI flags (`document_exporter`)

- `--zip-compression {stored,deflated,bzip2,lzma}` — and `zstd` **when the
  runtime supports it** (see below). Maps to the matching `zipfile.ZIP_*`
  constant. Default `deflated`.
- `--zip-compression-level N` — integer. Meaningful for `deflated` (0–9; `zlib`
  also accepts `-1` meaning "default", which is the same as omitting the flag /
  `compresslevel=None`) and `bzip2` (1–9; `0` is invalid for bzip2). For `zstd`,
  **do not hardcode a numeric range** — defer to the stdlib and surface whatever
  it raises (the accepted zstd range has shifted across libzstd versions; see the
  zstd section). Combining the flag with `stored` or `lzma` (which ignore level)
  is a `CommandError`, not a silent accept — consistent with the base refactor's
  fail-fast posture. Default: unset → library default.

Both flags require `--zip`; passing either without `--zip` raises a
`CommandError`, matching the incremental-flag rule from the base refactor.

**Why validate up front (not let `zipfile` raise):** an invalid level does _not_
fail at `ZipFile(...)` construction — it fails at the **first `write`/`writestr`
call**, with an opaque message (`ValueError: Invalid initialization option` for
deflated > 9, or `compresslevel must be between 1 and 9` for bzip2), and inside a
`with ZipFile(...)` block that error is then _masked_ by a secondary
`ValueError: Can't close the ZIP file while there is an open writing handle` on
context exit. Up-front validation turns that into a clean `CommandError`.

### Validation (in `handle()`, before constructing the sink)

1. **Requires `--zip`.** Either flag without `--zip` → `CommandError`.
2. **Method availability — via a named, patchable seam.** Expose a module-level
   helper (e.g. `compression_available(method) -> bool` or a capability map) that
   does `try: import bz2 / import lzma except ImportError: return False` — **not**
   `importlib.util.find_spec`, which can report a stdlib C-extension as present
   when importing it actually fails. For `zstd`, the probe must also confirm the
   codec is usable on 3.14+ (constant present _and_ `compression.zstd`
   importable), not merely that the constant exists. Making this a named function
   is also what lets the test patch "method unavailable" with `mocker`. If the
   chosen method is unavailable, raise a `CommandError` naming the missing
   capability.
3. **Level range.** Reject an out-of-range `--zip-compression-level` for the
   chosen method with a clear `CommandError`; reject the flag entirely for
   `stored`/`lzma` (see above).

### zstd (Python 3.14+)

> ⚠️ **VERIFY before coding.** The following zstd specifics are stated from the
> assistant's knowledge of the 3.14 reorganization and were **not** verifiable in
> the dev environment (it runs 3.11, where `ZIP_ZSTANDARD` does not exist).
> Confirm each against the real Python 3.14 / PEP 784 docs before implementing:
> the exact constant name (`ZIP_ZSTANDARD` vs `ZIP_ZSTD`), the backing module
> path (`compression.zstd`), that `zipfile` actually routes zstd through it, and
> the accepted `compresslevel` bounds.

Python 3.14 is expected to add Zstandard support to `zipfile`
(`ZIP_ZSTANDARD`, backed by the new `compression.zstd` module, PEP 784). Gate it
at runtime so nothing zstd-related is imported or referenced on < 3.14 (the
project targets Python ≥ 3.11):

```python
_ZSTD = getattr(zipfile, "ZIP_ZSTANDARD", None)  # None before 3.14
```

Presence of the _constant_ does not guarantee the _codec_ is usable (same stripped
-build risk as `bz2`/`lzma`), so the availability probe (validation step 2) must
attempt the codec, not just check the constant. Do **not** hardcode a zstd level
range — pass the user's level through and let the stdlib raise, mapping any error
to a `CommandError`.

Keep `zstd` in the `--zip-compression` `choices` **always** (even on < 3.14), and
reject it in validation with a friendly "zstd requires Python 3.14+" message. If
it were dropped from `choices` on older runtimes, argparse would emit a generic
"invalid choice" that reads as though the option never existed — worse UX.

### Import-side compatibility

`document_importer` reads zips with `ZipFile(self.source).extractall(...)`
(`document_importer.py:453`), which decompresses each entry transparently using
whatever method it was stored with — **provided the matching module exists on the
importing machine.**

The failure mode when it doesn't is unfriendly and must be handled: a zstd (or
otherwise unsupported) entry raises a bare `NotImplementedError` **per-entry,
during `extractall`** — _not_ at `ZipFile(self.source)` open, and `is_zipfile()`
still returns true (a zstd archive is a valid zip container). So the importer
enters the zip branch, creates its temp dir, may partially extract other entries,
then blows up mid-extract with no context. **Mitigation (in scope here):** before
extracting, inspect `ZipFile(self.source).infolist()` compress types and, if any
is unsupported on this runtime, raise a `CommandError` naming the method and the
requirement (e.g. "this archive uses zstd, which needs Python 3.14+") instead of
letting `NotImplementedError` escape.

Per-method summary (document in help text + `administration.md`):

- `deflated`/`stored`: universally importable.
- `bzip2`/`lzma`: importable wherever the `bz2`/`lzma` modules are present
  (essentially always).
- `zstd`: importable only on Python 3.14+. An archive compressed with `zstd` is
  **not** importable on older runtimes.

## Testing

New cases in the sink tests and an export→import round-trip
(pytest classes, factory-boy, `mocker`, `parametrize`, typed; run on the VM):

- **Round-trip per method.** Parametrize over the available methods (skip `zstd`
  below 3.14, skip `bzip2`/`lzma` if the module is somehow absent): export a
  small library, import it back, assert documents/manifest match.
- **Method is applied.** Assert each written _file_ entry's `compress_type`
  equals the requested method (read back via `ZipFile.infolist()`), filtering out
  directory marker entries (which are tagged but empty).
- **Level affects size — robustly.** Do **not** compare deflate level 9 vs 1
  (on small or incompressible fixtures level 9 can equal or slightly exceed level
  1, causing flaky CI). Instead assert that a compressing method on a
  moderately-compressible fixture yields a total smaller than `stored`
  (`ZIP_STORED`), which is a stable invariant.
- **Validation.** Each flag without `--zip` → `CommandError`; out-of-range level
  (`--zip-compression-level 99`) → a clean `CommandError` from validation
  (asserting we never reach the `writestr` that would raise the masked
  `ValueError`); `--zip-compression-level` with `stored`/`lzma` → `CommandError`;
  unavailable method (patch the named availability seam with `mocker`) →
  `CommandError`; on < 3.14, `--zip-compression zstd` → the friendly
  "requires 3.14+" `CommandError`.
- **Import pre-check.** An archive containing an unsupported compress type
  produces a `CommandError` from the importer naming the method, not a raw
  `NotImplementedError` (simulate by patching the importer's support probe).
- **Default unchanged.** Omitting both flags yields file entries with
  `compress_type == ZIP_DEFLATED`, identical to pre-feature behavior.

## Risks

- **Foot-gun archives.** A user could produce a `zstd`/`lzma` archive their
  import target can't read. Mitigation: explicit help text and the import-side
  notes above; the default stays the universally-readable `deflated`.
- **Optional-module assumptions.** Don't assume `bz2`/`lzma` are always compiled
  in; probe and error clearly. Mitigation: the availability validation step.
