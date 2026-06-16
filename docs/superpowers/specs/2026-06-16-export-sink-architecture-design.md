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
2. **Incremental options are folder-only, with a hard error on misuse.**
   `--compare-checksums`, `--compare-json`, and `--delete` are properties of the
   folder sink. Passing any of them together with `--zip` raises a `CommandError`
   up front (fail fast, not warn-and-ignore).
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

- `arcname` is relative and POSIX-style; the sink maps it to its own namespace
  (folder: joined under the target; zip: the entry name).
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

### `ZipExportSink(target, zip_name)`

- On open: open a `zipfile.ZipFile` at `<target>/<zip_name>.zip.tmp`
  (`ZIP_DEFLATED`, `allowZip64=True`).
- `add_file` / `add_json`: write the entry directly, first emitting directory
  marker entries for parent paths so every zip viewer shows the folder structure
  (today's `_ensure_zip_dirs`).
- `stream`: yields a handle writing to a single temp file in `SCRATCH_DIR`.
- `finalize()` (success only): add the spooled manifest temp file as its entry,
  close the zip, then atomically rename `.zip.tmp` → `.zip`.
- `abort()` (on exception): close the zip, unlink the `.zip.tmp`, delete the
  manifest temp file. **A `.zip` therefore exists only after a fully successful
  run.**
- Rejects `compare_*` / `delete` — but the command guards this before
  constructing the sink (see below), so the sink simply has no such parameters.

### Command changes (`document_exporter.py`)

- **`handle()`**: validate the target, then _up front_ raise `CommandError` if any
  of `--compare-checksums` / `--compare-json` / `--delete` is combined with
  `--zip`. Construct the appropriate sink. Run the export as
  `with sink: self.dump(sink)`. Delete the temp-dir / `shutil.make_archive`
  block entirely.
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
  ├─ validate target; reject incremental flags + --zip  → CommandError
  ├─ sink = DirectoryExportSink(...) | ZipExportSink(...)
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
  `abort()`. Zip: the `.zip.tmp` and the manifest temp file are deleted; **no
  `.zip` is produced.** Folder: in-flight `.tmp` files are discarded, existing
  files are left intact, and the stale-prune does not run.
- `finalize()` runs only on clean exit. For the zip that is the single
  `.zip.tmp` → `.zip` rename (atomic on the same filesystem). For the folder it
  is the optional stale-delete prune.
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
  `.zip` and no leftover `.zip.tmp`; a clean run yields exactly the `.zip` with
  directory marker entries present.
- **Stream contract**: opening a second concurrent `stream()` is rejected;
  `add_file`/`add_json` while a stream is open succeed.
- **Command guard**: `--zip` with each of `--compare-checksums` / `--compare-json`
  / `--delete` raises `CommandError`.

Existing `test_management_exporter.py` and `test_management_importer.py` stay
green unchanged — the export's external behavior (layout, manifest, round-trip
import) is preserved.

## Risks

- **Behavior drift in the folder path.** The incremental logic is subtle
  (mtime/size vs checksum, blake2b json compare, empty-dir cleanup). Mitigation:
  move it verbatim into the sink and lean on the unchanged command-level tests
  plus new focused sink tests.
- **Manifest interleaving in zip mode.** Relies on the spool-to-temp-file
  decision; the stream contract makes this explicit and the stream-contract test
  guards it.
