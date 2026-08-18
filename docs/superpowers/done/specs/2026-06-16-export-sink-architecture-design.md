# Export Sink Architecture — Design

**Date:** 2026-06-16
**Branch base:** `dev`
**Status:** Approved design, pending implementation plan

## Problem

The `document_exporter` management command can export to a folder or to a zip
file, but the zip support is bolted on rather than designed in:

- **Zip mode is a temp-dir detour.** `handle()` redirects `self.target` to a
  `tempfile.TemporaryDirectory` in `SCRATCH_DIR`, runs the entire export against
  that directory, then calls `shutil.make_archive` to zip the whole tree and
  cleans the temp dir up (`document_exporter.py:322-358`). The export is written
  to disk twice (loose files, then the zip).

- **An attempted "direct to zip" refactor leaks the destination everywhere.**
  The prior work on `feature-direct-zip-export` threads `if self.zip_export:`
  branches through `check_and_copy`, `check_and_write_json`,
  `_write_split_manifest`, `dump`, `handle`, and `StreamingManifestWriter`. Each
  write site grew a second code path plus a `.resolve().relative_to(self.target)`
  arcname dance. The destination became a cross-cutting concern smeared across
  the command.

- **The command owns logic that isn't about the export contents.** Incremental
  sync — the `files_in_export_dir` snapshot, the `--compare-checksums` /
  `--compare-json` skip-if-unchanged checks, and the `--delete` stale-file prune —
  is interleaved with the logic that decides _what_ to export. These behaviors
  only make sense for a folder destination, yet they live in the command body.

- **Atomicity is informal.** A backup must never look complete when it isn't.
  The temp-dir approach happens to be safe (the zip is built last), but there is
  no explicit "produce the archive only if the whole run succeeded" contract, and
  the direct-to-zip branch had to hand-manage a `.tmp` file inline.

## Goal

Separate **what** is exported (the command's job) from **where/how** it lands
(the destination's job), behind a small `ExportSink` abstraction. The command
declares files, JSON blobs, and a streamed manifest; the sink decides whether and
how to persist each one. Folder and zip become two interchangeable sinks, and a
future `S3ExportSink` is a third implementation rather than a fourth set of
branches. The zip is produced **only** if the entire export succeeds.

## Scope

In scope:

- New `documents/export/` package with the `ExportSink` ABC and two concrete
  sinks (`DirectoryExportSink`, `ZipExportSink`).
- Move all incremental-sync machinery (snapshot, compare, prune) out of the
  command and into `DirectoryExportSink`.
- Rewrite `document_exporter.handle()` / `dump()` to be destination-agnostic.
- Simplify `StreamingManifestWriter` to write to a sink-provided handle.
- Unit tests for each sink; keep existing command-level tests green.

Out of scope:

- `bulk_download.py` / `BulkArchiveStrategy` and share-link bundle zipping. Those
  select _which document files_ go in and stream to an HTTP response with no
  atomic-finalize requirement — a different axis from the backup sink. Untouched.
- Actually implementing an S3 (or any cloud) sink. The interface is designed to
  _allow_ one; we do not build one (YAGNI).
- Changing the export's on-disk/in-zip layout, manifest schema, crypto, or any
  CLI flag's meaning. Behavior is preserved; only the destination plumbing moves.
- Zip compression control (method / level). The `ZipExportSink` keeps today's
  fixed `ZIP_DEFLATED` here; making compression configurable is a follow-up —
  see `2026-06-16-export-zip-compression-design.md`, which depends on this
  refactor landing first. The sink is the single seam that makes it a small,
  isolated change.

## Decisions

These were settled during brainstorming:

1. **Scope is the `document_exporter` command only.** Design the interface so an
   S3 sink could be added later; do not refactor `bulk_download` or share bundles.
2. **`--compare-*` are folder-only (hard error with `--zip`); `--delete` is kept
   for both.** `--compare-checksums` / `--compare-json` are genuine no-ops in zip
   mode today (the temp dir is always empty, so the compare always copies), so
   combining either with `--zip` raises a `CommandError` up front. **`--delete`,
   however, is an existing tested feature in zip mode** — it wipes the destination
   directory of pre-existing files/dirs before the archive lands
   (`test_export_zipped_with_delete`). Its meaning differs by destination: folder
   `--delete` prunes stale exported files; zip `--delete` clears the target dir.
   Both are preserved — `--delete` is a parameter of _both_ sinks, not an error.
3. **The zip manifest spools to a temp file, not memory.** The sink exposes a
   streaming-write handle. The zip sink streams the manifest to a single temp
   file in `SCRATCH_DIR` and adds it as the manifest entry at finalize, keeping
   peak memory flat regardless of library size. The only "temp" artifact is one
   manifest file, not a whole export tree.

## Architecture

### The `ExportSink` interface

New module `documents/export/sinks.py`:

```python
class ExportSink(AbstractContextManager):
    """Destination for a document export.

    The command declares export contents via the three verbs below; the sink
    decides whether and how to persist each item. arcname is always a relative
    POSIX path (e.g. "manifest.json", "originals/foo.pdf").
    """

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
        """Persist an existing file at the relative arcname."""

    def add_json(self, content: list | dict, arcname: str) -> None:
        """Persist JSON-serializable content at the relative arcname."""

    def stream(self, arcname: str) -> ContextManager[TextIO]:
        """Yield a writable text handle for incrementally produced content.

        Reserved for the bulk manifest. At most one stream may be open at a
        time; add_file/add_json may be called freely while it is open.
        """

    # __enter__ opens the sink and returns self.
    # __exit__ calls finalize() on success, abort() on exception.
```

**Contract / invariants** (the checklist a future sink author honors):

- `arcname` is relative and **POSIX-style (forward slashes)**; the sink maps it to
  its own namespace (folder: joined under the target; zip: the entry name). The
  command must build arcnames with `Path(...).as_posix()` — `str(Path(...))`
  yields backslashes on Windows, which corrupts zip entry names and makes the
  manifest's stored paths non-portable. The same string is used both as the sink
  key and as the value stored in the manifest (`EXPORTER_FILE_NAME` etc.), so it
  must be POSIX at the point of construction. (The share-link bundle path already
  uses `.as_posix()`; the document targets currently do not and must be fixed.)
- At most one `stream()` is open at a time. It is the manifest. `add_file` /
  `add_json` may be interleaved with an open stream — implementations that can't
  interleave a real stream (zip, S3) must spool the stream to a side buffer and
  emit it at `finalize()`.
- The sink is a context manager. Normal exit finalizes; an exception aborts.
  **No partial or failed run may leave a "complete-looking" artifact.**

### `DirectoryExportSink(target, *, compare_checksums, compare_json, delete)`

Owns everything the command currently does for folder mode:

- On open: snapshot existing files under `target` (today's `files_in_export_dir`).
- `add_file`: the `check_and_copy` skip logic (mtime/size, or checksum when
  `compare_checksums`), then copy with stat preservation. Records the arcname as
  "seen this run".
- `add_json`: the `check_and_write_json` blake2b compare-or-write (honoring
  `compare_json`). Records the arcname as seen.
- `stream`: yields a handle writing to `<arcname>.tmp`; on context close, applies
  the `compare_json` blake2b compare and renames-or-discards (today's
  `StreamingManifestWriter` finalize). Records the arcname as seen.
- `finalize()` (success only): if `delete`, prune every snapshot file not seen
  this run and clean up emptied directories (today's stale-delete pass).
- `abort()` (on exception): discard any in-flight `.tmp`; leave existing files
  intact; do **not** run the prune.

The folder sink is inherently in-place/incremental, not atomic — that is its
nature and is unchanged. Its safety is the per-file `.tmp`+rename it already does.

### `ZipExportSink(target, zip_name, *, delete)`

- On open: ensure `SCRATCH_DIR` exists (`mkdir(parents=True, exist_ok=True)` —
  today's `handle()` does this before using it; the sink must do it now), then
  open a `zipfile.ZipFile` at `<target>/<zip_name>.zip.tmp` (`ZIP_DEFLATED`,
  `allowZip64=True`). The `.zip.tmp` lives in the same directory as the final
  `.zip` so the finalize rename is atomic (same filesystem).
- `add_file` / `add_json`: write the entry directly, first emitting directory
  marker entries for parent paths so every zip viewer shows the folder structure
  (today's `_ensure_zip_dirs`). A _flat_ export (no `--use-folder-prefix`, no
  nested arcnames) has no parent dirs, so it emits **zero** markers — matching
  today's `make_archive` output for flat trees (keeps the `namelist()` count
  assertions in `test_export_zipped` valid). Nested/prefixed exports gain marker
  entries; any count assertion on those must be audited.
- `stream`: yields a handle writing to a single temp file in `SCRATCH_DIR`.
- `finalize()` (success only): add the spooled manifest temp file as its entry,
  close the zip, then **if `delete`, wipe the destination directory** of every
  pre-existing file/dir except the in-progress `.zip.tmp` and any prior `.zip`
  (today's zip `--delete` behavior), then atomically rename `.zip.tmp` → `.zip`.
- `abort()` (on exception): close the zip, unlink the `.zip.tmp`, delete the
  manifest temp file. **A `.zip` therefore exists only after a fully successful
  run**, and on abort the destination is never wiped.
- Rejects `compare_*` (the command guards this before constructing the sink). It
  does **not** reject `delete` — that is a supported zip behavior (see above).

### Command changes (`document_exporter.py`)

- **`handle()`**: validate the target, then _up front_ raise `CommandError` if
  `--compare-checksums` or `--compare-json` is combined with `--zip` (those are
  no-ops in zip mode). `--delete` is **not** rejected — it is passed to whichever
  sink is built. Construct the appropriate sink (`delete=` passed to both). Run
  the export as `with sink: self.dump(sink)`. Delete the temp-dir /
  `shutil.make_archive` block entirely.
- **`--data-only`**: unchanged in meaning — it simply skips every `sink.add_file`
  call (no document/thumbnail/archive/bundle files) while the manifest stream and
  `metadata.json` are still written. Works identically for both sinks; no sink
  code is data-only-aware. (`test_export_data_only` and its zip equivalent stay
  green.)
- **`dump(sink)`**: destination-agnostic. Builds relative arcnames and calls
  `sink.add_file(...)`, `sink.add_json(...)`, and `sink.stream("manifest.json")`.
  `self.files_in_export_dir`, `check_and_copy`, `check_and_write_json`, and the
  stale-delete pass are removed (their logic now lives in the folder sink).
- **`generate_document_targets`**: returns relative arcnames
  (`originals/<name>`, `<name>-thumbnail.webp`, `archive/<name>-archive.pdf`)
  instead of absolute `self.target / ...` paths. It already writes the relative
  name into `document_dict[EXPORTER_FILE_NAME]` etc.; we just drop the absolute
  half.
- **`StreamingManifestWriter`**: simplified to write JSON-array records to the
  text handle returned by `sink.stream("manifest.json")`. It no longer knows
  folder vs zip, owns no `.tmp` logic, and has no compare/zip parameters — that
  behavior moved into each sink's `stream()`.
- **Crypto / passphrase** handling stays in the command: it transforms record
  _contents_ before they reach the sink, which is independent of destination.
- **Progress tracking stays in the command — the sinks know nothing about it.**
  `PaperlessCommand.track()` wraps the _document iterable_ in `dump()` and ticks
  the Rich bar once per document. That loop stays in the command; each iteration
  calls `sink.add_file(...)`, so the per-document progress is preserved
  unchanged. The sinks deliberately do **not** depend on `PaperlessCommand`,
  `track()`, or Rich — coupling the destination abstraction to the command
  framework would defeat the isolation goal and make the sinks impossible to unit
  -test without a full command. (A sink is a plain context-managed I/O object; it
  is constructed by `handle()` and exercised directly in `test_sinks.py`.) If
  finer-grained progress is ever wanted for a single very large file, that is a
  future enhancement layered via an optional callback — not a `PaperlessCommand`
  dependency, and out of scope here.

### How `--split-manifest` fits (no sink special-casing)

`--split-manifest` is purely a command-level choice and touches no sink code:

- The single bulk `manifest.json` is always the one and only `sink.stream(...)`
  handle. In split mode it simply carries fewer record types (document records,
  notes, and custom-field-instances are redirected out).
- Per-document `<base>-manifest.json` files are small _complete_ JSON blobs — they
  were never streamed. `_write_split_manifest` collapses to building the content
  list and one `sink.add_json(content, "<base>-manifest.json")` call, exactly
  like `metadata.json`.

Because the manifest stream is backed by its own handle (a `.tmp` file in the
folder sink, a `SCRATCH_DIR` temp file in the zip sink) and never an open zip
entry, the per-document `add_json` / `add_file` calls made _while the bulk
manifest stream is open_ never collide with it.

## Data flow

```
handle(options)
  ├─ validate target; reject --compare-* + --zip  → CommandError  (--delete allowed)
  ├─ sink = DirectoryExportSink(..., delete=…) | ZipExportSink(..., delete=…)
  └─ with FileLock(MEDIA_LOCK), sink:
       dump(sink)
         ├─ with sink.stream("manifest.json") as mh:
         │    writer = StreamingManifestWriter(mh)
         │    ├─ global querysets        → writer.write_batch(...)   (encrypted inline)
         │    ├─ per document:
         │    │    ├─ sink.add_file(source, "originals/…", checksum=…)
         │    │    ├─ sink.add_file(thumb,  "…-thumbnail.webp")
         │    │    ├─ sink.add_file(archive,"archive/…-archive.pdf", checksum=…)
         │    │    └─ split? sink.add_json(doc_bundle, "…-manifest.json")
         │    │            : writer.write_record(doc_record)
         │    └─ per share-link bundle: sink.add_file(...) + writer.write_record(...)
         └─ sink.add_json(metadata, "metadata.json")
  (success → sink.finalize();  exception → sink.abort())
```

## Error handling & atomicity

- Any exception in `dump()` propagates through `with sink:` → `__exit__` →
  `abort()`. Zip: the `.zip.tmp` and the manifest temp file are deleted, and the
  destination is **not** wiped; **no `.zip` is produced.** Folder: in-flight
  `.tmp` files are discarded, existing files are left intact, and the stale-prune
  does not run.
- `finalize()` runs only on clean exit, after all contents are written. For the
  zip: optionally wipe the destination (`--delete`), then the single `.zip.tmp` →
  `.zip` rename (atomic on the same filesystem). For the folder: the optional
  stale-delete prune.
- **Honest limits of the atomicity guarantee.** The guarantee is "no
  _complete-looking_ `.zip` after a failed run," not "no leftovers." If the
  process is `SIGKILL`ed or the rename itself fails _after_ the zip is closed, a
  `.zip.tmp` may be orphaned — that is the safe direction (no false-complete
  `.zip`), but stale `.zip.tmp` files are **not** auto-cleaned on a later run
  (matching the prior branch). `KeyboardInterrupt` is a `BaseException` but
  `__exit__` still runs, so `abort()` fires normally. The rename being atomic and
  these runs not racing each other both rely on `FileLock(settings.MEDIA_LOCK)`,
  which serializes exports; concurrent same-`--zip-name` runs are out of scope.
- The `FileLock(settings.MEDIA_LOCK)` wrapping is unchanged.

## Testing

New `documents/export/tests/test_sinks.py`, unit-testing each sink in isolation
(pytest classes, factory-boy factories, the `mocker` fixture, `parametrize`, full
type annotations; run on the Linux VM):

- **Round-trip** (both sinks, parametrized): `add_file` + `add_json` + a streamed
  manifest produce the expected files/entries with correct relative arcnames.
- **Folder incremental**: unchanged file is skipped under `compare_checksums` and
  under `compare_json`; `delete` prunes a snapshot file not written this run and
  removes emptied directories; without `delete`, stale files remain.
- **Zip atomicity**: injecting an exception mid-export (via `mocker`) leaves no
  `.zip` and no leftover `.zip.tmp`, and does not wipe the destination even with
  `--delete`; a clean run yields exactly the `.zip`. A nested/prefixed export has
  directory marker entries; a flat export has none.
- **Zip `--delete`**: a clean `--zip --delete` run wipes pre-existing
  files/dirs in the destination and produces the `.zip` (preserves
  `test_export_zipped_with_delete`).
- **POSIX arcnames**: nested arcnames are stored with forward slashes in both the
  zip entry names and the manifest values, regardless of host OS (guards the
  Windows backslash bug).
- **`--data-only`**: both sinks produce only `manifest.json` + `metadata.json`,
  no document files.
- **Stream contract**: opening a second concurrent `stream()` is rejected;
  `add_file`/`add_json` while a stream is open succeed.
- **Command guard**: `--zip` with `--compare-checksums` or `--compare-json`
  raises `CommandError`; `--zip --delete` does **not** error.

Existing `test_management_exporter.py` and `test_management_importer.py` stay
green unchanged — the export's external behavior (layout, manifest, round-trip
import, `--zip --delete`, `--data-only`) is preserved.

## Risks

- **Behavior drift in the folder path.** The incremental logic is subtle
  (mtime/size vs checksum, blake2b json compare, empty-dir cleanup). Mitigation:
  move it verbatim into the sink and lean on the unchanged command-level tests
  plus new focused sink tests.
- **Manifest interleaving in zip mode.** Relies on the spool-to-temp-file
  decision; the stream contract makes this explicit and the stream-contract test
  guards it.
