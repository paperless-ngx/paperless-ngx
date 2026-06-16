# Export Sink Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `document_exporter` so the export destination (folder vs zip) lives behind an `ExportSink` abstraction, making the command destination-agnostic and producing a zip only on full success.

**Architecture:** A new `documents/export/` package defines an `ExportSink` ABC with three verbs (`add_file`, `add_json`, `stream`) plus context-manager `finalize`/`abort`. `DirectoryExportSink` owns all incremental-sync logic (snapshot, compare, prune); `ZipExportSink` owns atomic `.tmp`→rename and manifest spooling. The command's `dump()` just declares relative POSIX arcnames and calls sink verbs.

**Tech Stack:** Python ≥3.11, Django, `zipfile`, pytest + pytest-mock + factory-boy. Backend tests run on the Linux VM (this is a Windows host); `ruff` runs locally.

**Spec:** `docs/superpowers/specs/2026-06-16-export-sink-architecture-design.md`

---

## Conventions for every task

- **Run backend tests on the VM** via the helper (never locally — the lockfile is linux/macOS only):
  ```bash
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<pytest targets/args>"
  ```
- **Lint locally** with the global ruff binary (not `uv run`):
  ```bash
  ruff check src/documents/export/ src/documents/management/commands/document_exporter.py
  ruff format src/documents/export/ src/documents/management/commands/document_exporter.py
  ```
- **Tests are pytest-style** (per CLAUDE.md): grouped in classes, `@pytest.mark.django_db` on the class _only where DB is needed_ (the sink unit tests are pure filesystem and need no DB), factory-boy factories, the `mocker` fixture, `@pytest.mark.parametrize`, full type annotations on fixtures and tests. Do **not** convert the existing `test_management_exporter.py` (Django `TestCase` style) — it is the regression net and stays as-is.

## File structure

- **Create** `src/documents/export/__init__.py` — package marker.
- **Create** `src/documents/export/sinks.py` — `ExportSink` ABC, `DirectoryExportSink`, `ZipExportSink`, `StreamingManifestWriter`, and the `_dumps` helper. One cohesive module (~300 lines): these types share the ABC and are always used together.
- **Create** `src/documents/tests/export/__init__.py` — test package marker.
- **Create** `src/documents/tests/export/test_sinks.py` — pure-filesystem unit tests for both sinks and the stream contract.
- **Modify** `src/documents/management/commands/document_exporter.py` — wire `handle()`/`dump()` to the sinks; delete `check_and_copy`, `check_and_write_json`, the local `StreamingManifestWriter`, the temp-dir/`make_archive` block, and the `files_in_export_dir` snapshot; switch arcnames to `.as_posix()`.
- **Modify** `src/documents/tests/test_management_exporter.py` — add one new test for the `--zip` + `--compare-*` guard (existing tests untouched).

---

## Task 1: Scaffold the export package, `_dumps`, and `StreamingManifestWriter`

**Files:**

- Create: `src/documents/export/__init__.py`
- Create: `src/documents/export/sinks.py`
- Create: `src/documents/tests/export/__init__.py`
- Test: `src/documents/tests/export/test_sinks.py`

- [ ] **Step 1: Create the package markers**

Create `src/documents/export/__init__.py` (empty) and `src/documents/tests/export/__init__.py` (empty).

- [ ] **Step 2: Write the failing test for `_dumps` and `StreamingManifestWriter`**

Create `src/documents/tests/export/test_sinks.py`. Each later task appends test
classes and **adds its new imports to this top-of-file block** (never mid-file —
ruff E402). Start with only what Task 1 needs:

```python
import io
import json

from documents.export.sinks import StreamingManifestWriter
from documents.export.sinks import _dumps


class TestDumps:
    def test_dumps_is_indented_unicode_json(self) -> None:
        result: str = _dumps({"a": "é", "b": 1})
        assert '"é"' in result  # ensure_ascii=False keeps unicode literal
        assert "\n" in result  # indent=2 produces newlines
        assert json.loads(result) == {"a": "é", "b": 1}


class TestStreamingManifestWriter:
    def test_writes_json_array_of_records(self) -> None:
        handle: io.StringIO = io.StringIO()
        writer: StreamingManifestWriter = StreamingManifestWriter(handle)
        writer.write_batch([{"pk": 1}, {"pk": 2}])
        writer.write_record({"pk": 3})
        writer.close()
        assert json.loads(handle.getvalue()) == [{"pk": 1}, {"pk": 2}, {"pk": 3}]

    def test_empty_manifest_is_valid_empty_array(self) -> None:
        handle: io.StringIO = io.StringIO()
        writer: StreamingManifestWriter = StreamingManifestWriter(handle)
        writer.close()
        assert json.loads(handle.getvalue()) == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py -v"`
Expected: FAIL with `ModuleNotFoundError: No module named 'documents.export.sinks'`.

- [ ] **Step 4: Implement `_dumps` and `StreamingManifestWriter` in `sinks.py`**

Create `src/documents/export/sinks.py` with the module header and these two pieces (the sink classes come in later tasks):

```python
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from documents.file_handling import delete_empty_directories
from documents.utils import compute_checksum
from documents.utils import copy_file_with_basic_stats

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import TextIO


def _dumps(content: list | dict) -> str:
    """Serialize export JSON consistently across all sinks."""
    return json.dumps(content, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)


class StreamingManifestWriter:
    """Incrementally writes a JSON array to a text handle, one record at a time.

    Knows nothing about folders or zips: it writes the array framing and records
    to whatever handle the sink's ``stream()`` yields. The sink owns the handle's
    lifecycle (atomic rename, compare, spooling).
    """

    def __init__(self, handle: TextIO) -> None:
        self._file = handle
        self._first = True
        self._file.write("[")

    def write_record(self, record: dict) -> None:
        if not self._first:
            self._file.write(",\n")
        else:
            self._first = False
        self._file.write(_dumps(record))

    def write_batch(self, records: list[dict]) -> None:
        for record in records:
            self.write_record(record)

    def close(self) -> None:
        """Write the closing bracket. Does NOT close the handle (the sink owns it)."""
        self._file.write("\n]")
```

Note: `_dumps` uses `indent=2` exactly like the old per-record `json.dumps`, so manifest bytes are unchanged.

- [ ] **Step 5: Run the test to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py -v"`
Expected: PASS (3 tests).

- [ ] **Step 6: Lint**

Run: `ruff check src/documents/export/ && ruff format src/documents/export/`
Expected: no errors (ruff may report unused imports `hashlib/shutil/tempfile/zipfile/...` — that is fine, they are consumed by the sink classes added in Tasks 2–3; if ruff fails the build on unused imports, add the sink class stubs from Task 2 first, or temporarily keep only the imports used so far and add the rest in Task 2).

To avoid the unused-import churn, **only include the imports actually used so far** in this task (`json`, `DjangoJSONEncoder`), and add each remaining import in the task that first uses it. The full import list above is the end state.

- [ ] **Step 7: Commit**

```bash
git add src/documents/export/__init__.py src/documents/export/sinks.py src/documents/tests/export/__init__.py src/documents/tests/export/test_sinks.py
git commit -m "Feature: add export package with StreamingManifestWriter and _dumps"
```

---

## Task 2: `ExportSink` ABC and `DirectoryExportSink`

**Files:**

- Modify: `src/documents/export/sinks.py`
- Test: `src/documents/tests/export/test_sinks.py`

- [ ] **Step 1: Write failing tests for `DirectoryExportSink`**

Add these imports to the top-of-file block (`json` and `StreamingManifestWriter`
are already imported from Task 1):

```python
import os
from pathlib import Path

import pytest

from documents.export.sinks import DirectoryExportSink
```

Then append the test class to `src/documents/tests/export/test_sinks.py`:

```python
class TestDirectoryExportSink:
    @pytest.fixture()
    def source_file(self, tmp_path: Path) -> Path:
        src: Path = tmp_path / "src" / "doc.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"PDF-CONTENT")
        return src

    def test_add_file_copies_to_relative_arcname(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=False,
        ) as sink:
            sink.add_file(source_file, "originals/doc.pdf")
        assert (target / "originals" / "doc.pdf").read_bytes() == b"PDF-CONTENT"

    def test_add_json_writes_file(self, tmp_path: Path) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=False,
        ) as sink:
            sink.add_json({"version": "x"}, "metadata.json")
        assert json.loads((target / "metadata.json").read_text()) == {"version": "x"}

    def test_stream_writes_manifest(self, tmp_path: Path) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=False,
        ) as sink:
            with sink.stream("manifest.json") as handle:
                writer: StreamingManifestWriter = StreamingManifestWriter(handle)
                writer.write_record({"pk": 1})
                writer.close()
        assert json.loads((target / "manifest.json").read_text()) == [{"pk": 1}]

    def test_add_file_skips_when_size_and_mtime_match(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        # Pre-existing target with identical size+mtime but DIFFERENT content:
        # if add_file skips (no compare-checksums), the old content survives.
        target: Path = tmp_path / "out"
        target.mkdir()
        existing: Path = target / "originals" / "doc.pdf"
        existing.parent.mkdir(parents=True)
        # Same byte length as the source but different content + matching mtime,
        # so a size/mtime comparison treats it as unchanged and skips the copy.
        existing.write_bytes(b"X" * len(b"PDF-CONTENT"))
        stat = source_file.stat()
        os.utime(existing, (stat.st_atime, stat.st_mtime))
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=False,
        ) as sink:
            sink.add_file(source_file, "originals/doc.pdf", checksum="abc")
        assert existing.read_bytes() == b"X" * len(b"PDF-CONTENT")  # skipped

    def test_add_file_recopies_when_compare_checksums_differ(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        existing: Path = target / "originals" / "doc.pdf"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"X" * len(b"PDF-CONTENT"))
        stat = source_file.stat()
        os.utime(existing, (stat.st_atime, stat.st_mtime))
        with DirectoryExportSink(
            target,
            compare_checksums=True,
            compare_json=False,
            delete=False,
        ) as sink:
            # wrong checksum forces recopy despite matching size/mtime
            sink.add_file(source_file, "originals/doc.pdf", checksum="not-the-real-sum")
        assert existing.read_bytes() == b"PDF-CONTENT"  # recopied

    def test_delete_prunes_unwritten_snapshot_files(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        stale: Path = target / "stale.pdf"
        stale.write_bytes(b"STALE")
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=True,
        ) as sink:
            sink.add_file(source_file, "originals/doc.pdf")
        assert not stale.exists()
        assert (target / "originals" / "doc.pdf").exists()

    def test_no_delete_keeps_unwritten_files(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        stale: Path = target / "stale.pdf"
        stale.write_bytes(b"STALE")
        with DirectoryExportSink(
            target,
            compare_checksums=False,
            compare_json=False,
            delete=False,
        ) as sink:
            sink.add_file(source_file, "originals/doc.pdf")
        assert stale.exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py::TestDirectoryExportSink -v"`
Expected: FAIL with `ImportError: cannot import name 'DirectoryExportSink'`.

- [ ] **Step 3: Implement the ABC and `DirectoryExportSink` in `sinks.py`**

Add after `StreamingManifestWriter` (and ensure the imports `abc` removed — we use a plain base with `NotImplementedError`, or `import abc`; here we use `abc`). Add `import abc` to the import block.

```python
class ExportSink:
    """Destination for a document export.

    The command declares export contents via three verbs; the sink decides how to
    persist each. ``arcname`` is always a relative POSIX path
    (e.g. ``"manifest.json"``, ``"originals/foo.pdf"``).

    Contract:
      * At most one ``stream()`` open at a time (it is the manifest);
        ``add_file``/``add_json`` may be called while it is open.
      * Context-manager: normal exit finalizes, an exception aborts. No partial or
        failed run leaves a complete-looking artifact.
    """

    def add_file(self, source: Path, arcname: str, *, checksum: str | None = None) -> None:
        raise NotImplementedError  # pragma: no cover

    def add_json(self, content: list | dict, arcname: str) -> None:
        raise NotImplementedError  # pragma: no cover

    def stream(self, arcname: str):  # -> contextmanager yielding TextIO
        raise NotImplementedError  # pragma: no cover

    def _open(self) -> None:
        """Hook called on context entry. Override as needed."""

    def _finalize(self) -> None:
        """Commit on clean exit."""
        raise NotImplementedError  # pragma: no cover

    def _abort(self) -> None:
        """Roll back on exception."""
        raise NotImplementedError  # pragma: no cover

    def __enter__(self) -> ExportSink:
        self._open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._abort()
        else:
            self._finalize()


class DirectoryExportSink(ExportSink):
    """Writes loose files into a target directory, with incremental sync.

    Owns the snapshot/skip/compare/prune machinery that used to live in the
    command (``files_in_export_dir``, ``check_and_copy``, ``check_and_write_json``,
    and the ``--delete`` pass).
    """

    def __init__(
        self,
        target: Path,
        *,
        compare_checksums: bool,
        compare_json: bool,
        delete: bool,
    ) -> None:
        self._target = target.resolve()
        self._compare_checksums = compare_checksums
        self._compare_json = compare_json
        self._delete = delete
        self._snapshot: set[Path] = set()
        self._stream_open = False

    def _open(self) -> None:
        for x in self._target.glob("**/*"):
            if x.is_file():
                self._snapshot.add(x.resolve())

    def add_file(self, source: Path, arcname: str, *, checksum: str | None = None) -> None:
        target = (self._target / arcname).resolve()
        self._snapshot.discard(target)
        perform_copy = False
        if target.exists():
            source_stat = source.stat()
            target_stat = target.stat()
            if self._compare_checksums and checksum:
                perform_copy = compute_checksum(target) != checksum
            elif (
                source_stat.st_mtime != target_stat.st_mtime
                or source_stat.st_size != target_stat.st_size
            ):
                perform_copy = True
        else:
            perform_copy = True
        if perform_copy:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file_with_basic_stats(source, target)

    def add_json(self, content: list | dict, arcname: str) -> None:
        target = (self._target / arcname).resolve()
        json_str = _dumps(content)
        perform_write = True
        if target in self._snapshot:
            self._snapshot.discard(target)
            if self._compare_json:
                target_checksum = hashlib.blake2b(target.read_bytes()).hexdigest()
                src_checksum = hashlib.blake2b(json_str.encode("utf-8")).hexdigest()
                if src_checksum == target_checksum:
                    perform_write = False
        if perform_write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json_str, encoding="utf-8")

    @contextmanager
    def stream(self, arcname: str) -> Iterator[TextIO]:
        if self._stream_open:
            raise RuntimeError("A stream is already open on this sink")
        target = (self._target / arcname).resolve()
        tmp = target.with_suffix(target.suffix + ".tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = tmp.open("w", encoding="utf-8")
        self._stream_open = True
        try:
            yield handle
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
        else:
            handle.close()
            self._commit_streamed_file(target, tmp)
        finally:
            self._stream_open = False

    def _commit_streamed_file(self, target: Path, tmp: Path) -> None:
        if target in self._snapshot:
            self._snapshot.discard(target)
            if self._compare_json:
                existing = hashlib.blake2b(target.read_bytes()).hexdigest()
                new = hashlib.blake2b(tmp.read_bytes()).hexdigest()
                if existing == new:
                    tmp.unlink()
                    return
        tmp.rename(target)

    def _finalize(self) -> None:
        if self._delete:
            for f in self._snapshot:
                f.unlink()
                delete_empty_directories(f.parent, self._target)

    def _abort(self) -> None:
        # Folder mode is in-place/incremental: streamed .tmp files are already
        # cleaned in stream(); leave everything else intact and skip the prune.
        return None
```

Add `import abc` is **not** needed (we use plain classes). Add the imports actually used now: `hashlib`, `contextmanager`, `PurePosixPath` is not yet used (used in Task 3) — only add what's used. The currently-used new imports: `hashlib`, `shutil` not yet, `contextmanager`, `delete_empty_directories`, `compute_checksum`, `copy_file_with_basic_stats`, `settings` not yet.

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py -v"`
Expected: PASS (all `TestDirectoryExportSink` + Task 1 tests).

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/export/ && ruff format src/documents/export/`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/export/sinks.py src/documents/tests/export/test_sinks.py
git commit -m "Feature: add ExportSink ABC and DirectoryExportSink"
```

---

## Task 3: `ZipExportSink`

**Files:**

- Modify: `src/documents/export/sinks.py`
- Test: `src/documents/tests/export/test_sinks.py`

- [ ] **Step 1: Write failing tests for `ZipExportSink`**

Add these imports to the top-of-file block:

```python
import zipfile

from documents.export.sinks import ExportSink
from documents.export.sinks import ZipExportSink
```

Then append the test classes to `src/documents/tests/export/test_sinks.py`:

```python
class TestZipExportSink:
    @pytest.fixture()
    def source_file(self, tmp_path: Path) -> Path:
        src: Path = tmp_path / "src" / "doc.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"PDF-CONTENT")
        return src

    def test_round_trip_files_json_and_stream(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with ZipExportSink(target, "export", delete=False) as sink:
            sink.add_file(source_file, "originals/doc.pdf")
            sink.add_json({"version": "x"}, "metadata.json")
            with sink.stream("manifest.json") as handle:
                writer = StreamingManifestWriter(handle)
                writer.write_record({"pk": 1})
                writer.close()
        zip_path: Path = target / "export.zip"
        assert zip_path.exists()
        assert not (target / "export.zip.tmp").exists()
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert {"originals/doc.pdf", "metadata.json", "manifest.json"} <= names
            assert zf.read("originals/doc.pdf") == b"PDF-CONTENT"
            assert json.loads(zf.read("manifest.json")) == [{"pk": 1}]

    def test_nested_arcname_emits_directory_marker(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with ZipExportSink(target, "export", delete=False) as sink:
            sink.add_file(source_file, "originals/doc.pdf")
        with zipfile.ZipFile(target / "export.zip") as zf:
            assert "originals/" in zf.namelist()

    def test_flat_arcname_has_no_directory_markers(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with ZipExportSink(target, "export", delete=False) as sink:
            sink.add_file(source_file, "doc.pdf")
        with zipfile.ZipFile(target / "export.zip") as zf:
            assert all(not n.endswith("/") for n in zf.namelist())

    def test_exception_leaves_no_zip_and_no_tmp(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with pytest.raises(RuntimeError):
            with ZipExportSink(target, "export", delete=False) as sink:
                sink.add_file(source_file, "doc.pdf")
                raise RuntimeError("boom")
        assert not (target / "export.zip").exists()
        assert not (target / "export.zip.tmp").exists()

    def test_delete_wipes_destination_on_success(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        (target / "preexisting.txt").write_text("old")
        (target / "olddir").mkdir()
        with ZipExportSink(target, "export", delete=True) as sink:
            sink.add_file(source_file, "doc.pdf")
        assert (target / "export.zip").exists()
        assert not (target / "preexisting.txt").exists()
        assert not (target / "olddir").exists()

    def test_abort_with_delete_does_not_wipe_destination(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        (target / "preexisting.txt").write_text("old")
        with pytest.raises(RuntimeError):
            with ZipExportSink(target, "export", delete=True) as sink:
                sink.add_file(source_file, "doc.pdf")
                raise RuntimeError("boom")
        assert (target / "preexisting.txt").exists()
        assert not (target / "export.zip").exists()


class TestStreamContract:
    @pytest.fixture(params=["dir", "zip"])
    def sink(self, request: pytest.FixtureRequest, tmp_path: Path) -> ExportSink:
        target: Path = tmp_path / "out"
        target.mkdir()
        if request.param == "dir":
            return DirectoryExportSink(
                target,
                compare_checksums=False,
                compare_json=False,
                delete=False,
            )
        return ZipExportSink(target, "export", delete=False)

    def test_second_concurrent_stream_is_rejected(self, sink: ExportSink) -> None:
        with sink:
            with sink.stream("manifest.json"):
                with pytest.raises(RuntimeError, match="already open"):
                    with sink.stream("other.json"):
                        pass
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py::TestZipExportSink -v"`
Expected: FAIL with `ImportError: cannot import name 'ZipExportSink'`.

- [ ] **Step 3: Implement `ZipExportSink` in `sinks.py`**

Now the imports `shutil`, `tempfile`, `zipfile`, `PurePosixPath`, and `settings` are used — make sure they are present in the import block. Add the class:

```python
class ZipExportSink(ExportSink):
    """Writes a single zip archive, produced atomically only on success.

    Builds into ``<target>/<zip_name>.zip.tmp`` and renames to ``.zip`` on clean
    finalize. The manifest stream is spooled to a temp file in SCRATCH_DIR and
    added as an entry at finalize (a zip entry cannot be interleaved with others).
    """

    def __init__(self, target: Path, zip_name: str, *, delete: bool = False) -> None:
        self._target = target.resolve()
        self._zip_path = (self._target / zip_name).with_suffix(".zip")
        self._tmp_path = self._zip_path.with_name(self._zip_path.name + ".tmp")
        self._delete = delete
        self._zip: zipfile.ZipFile | None = None
        self._dirs: set[str] = set()
        self._pending_manifest: tuple[Path, str] | None = None
        self._stream_open = False

    def _open(self) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._zip = zipfile.ZipFile(
            self._tmp_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        )

    def _ensure_dirs(self, arcname: str) -> None:
        parts = PurePosixPath(arcname).parts[:-1]
        for i in range(len(parts)):
            dir_arc = "/".join(parts[: i + 1]) + "/"
            if dir_arc not in self._dirs:
                self._dirs.add(dir_arc)
                assert self._zip is not None
                self._zip.mkdir(dir_arc)

    def add_file(self, source: Path, arcname: str, *, checksum: str | None = None) -> None:
        assert self._zip is not None
        self._ensure_dirs(arcname)
        self._zip.write(source, arcname=arcname)

    def add_json(self, content: list | dict, arcname: str) -> None:
        assert self._zip is not None
        self._ensure_dirs(arcname)
        self._zip.writestr(arcname, _dumps(content))

    @contextmanager
    def stream(self, arcname: str) -> Iterator[TextIO]:
        if self._stream_open:
            raise RuntimeError("A stream is already open on this sink")
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=settings.SCRATCH_DIR,
            prefix="export-manifest-",
            suffix=".json",
        )
        tmp = Path(tmp_name)
        handle = open(fd, "w", encoding="utf-8")
        self._stream_open = True
        try:
            yield handle
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
        else:
            handle.close()
            self._pending_manifest = (tmp, arcname)
        finally:
            self._stream_open = False

    def _finalize(self) -> None:
        assert self._zip is not None
        if self._pending_manifest is not None:
            tmp, arcname = self._pending_manifest
            self._ensure_dirs(arcname)
            self._zip.write(tmp, arcname=arcname)
            tmp.unlink(missing_ok=True)
            self._pending_manifest = None
        self._zip.close()
        self._zip = None
        if self._delete:
            self._wipe_destination()
        self._tmp_path.rename(self._zip_path)

    def _wipe_destination(self) -> None:
        skip = {self._zip_path.resolve(), self._tmp_path.resolve()}
        for item in self._target.glob("*"):
            if item.resolve() in skip:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def _abort(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        self._tmp_path.unlink(missing_ok=True)
        if self._pending_manifest is not None:
            self._pending_manifest[0].unlink(missing_ok=True)
            self._pending_manifest = None
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py -v"`
Expected: PASS (all sink tests, including `TestStreamContract` for both `dir` and `zip`).

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/export/ && ruff format src/documents/export/`
Expected: no errors, no unused imports remaining in `sinks.py`.

- [ ] **Step 6: Commit**

```bash
git add src/documents/export/sinks.py src/documents/tests/export/test_sinks.py
git commit -m "Feature: add ZipExportSink with atomic finalize and manifest spooling"
```

---

## Task 4: Wire the command to the sinks

This is the swap. The existing `test_management_exporter.py` suite is the regression contract — it must stay green. Make the edits, then run the full exporter + importer suites.

**Files:**

- Modify: `src/documents/management/commands/document_exporter.py`
- Test (regression): `src/documents/tests/test_management_exporter.py`, `src/documents/tests/test_management_importer.py`

- [ ] **Step 1: Replace the top-of-file `StreamingManifestWriter` with an import**

Delete the entire local `StreamingManifestWriter` class (currently `document_exporter.py:87-165`) and instead import the sink machinery. Near the other `documents.*` imports add:

```python
from documents.export.sinks import DirectoryExportSink
from documents.export.sinks import StreamingManifestWriter
from documents.export.sinks import ZipExportSink
```

- [ ] **Step 2: Rewrite `handle()`**

Replace the current `handle()` body (`document_exporter.py:302-358`) with:

```python
    def handle(self, *args, **options) -> None:
        self.target = Path(options["target"]).resolve()
        self.split_manifest: bool = options["split_manifest"]
        self.compare_checksums: bool = options["compare_checksums"]
        self.compare_json: bool = options["compare_json"]
        self.use_filename_format: bool = options["use_filename_format"]
        self.use_folder_prefix: bool = options["use_folder_prefix"]
        self.delete: bool = options["delete"]
        self.no_archive: bool = options["no_archive"]
        self.no_thumbnail: bool = options["no_thumbnail"]
        self.zip_export: bool = options["zip"]
        self.data_only: bool = options["data_only"]
        self.passphrase: str | None = options.get("passphrase")
        self.batch_size: int = options["batch_size"]

        self.exported_files: set[str] = set()

        if self.zip_export and (self.compare_checksums or self.compare_json):
            raise CommandError(
                "--compare-checksums and --compare-json have no effect when "
                "used with --zip",
            )

        if not self.target.exists():
            raise CommandError("That path doesn't exist")

        if not self.target.is_dir():
            raise CommandError("That path isn't a directory")

        if not os.access(self.target, os.W_OK):
            raise CommandError("That path doesn't appear to be writable")

        sink: DirectoryExportSink | ZipExportSink
        if self.zip_export:
            sink = ZipExportSink(
                self.target,
                options["zip_name"],
                delete=self.delete,
            )
        else:
            sink = DirectoryExportSink(
                self.target,
                compare_checksums=self.compare_checksums,
                compare_json=self.compare_json,
                delete=self.delete,
            )

        # Prevent any ongoing changes in the documents while exporting
        with FileLock(settings.MEDIA_LOCK), sink:
            self.dump(sink)
```

Note: `self.files_in_export_dir` is gone (the folder sink owns the snapshot). `self.exported_files` stays (used by `generate_base_name`).

- [ ] **Step 3: Rewrite `dump()` to take the sink**

Replace `def dump(self) -> None:` and its body (`document_exporter.py:360-559`) with the version below. The querysets dict and crypto-setup block are **unchanged** — keep them verbatim; only the snapshot loop, the manifest-writer wiring, the file-copy calls, the split-manifest call, the metadata write, and the delete pass change.

```python
    def dump(self, sink: DirectoryExportSink | ZipExportSink) -> None:
        # 1. Create manifest, containing all correspondents, types, tags, storage
        #    paths, note, documents and ui_settings
        _excluded_usernames = ["consumer", "AnonymousUser"]
        manifest_key_to_object_query: dict[str, QuerySet[Any]] = {
            # ... KEEP THE EXISTING DICT VERBATIM (correspondents ... authenticators) ...
        }

        if settings.AUDIT_LOG_ENABLED:
            manifest_key_to_object_query["log_entries"] = LogEntry.objects.all()

        # Crypto setup before streaming begins
        if self.passphrase:
            self.setup_crypto(passphrase=self.passphrase)
        elif MailAccount.objects.count() > 0 or SocialToken.objects.count() > 0:
            self.stdout.write(
                self.style.NOTICE(
                    "No passphrase was given, sensitive fields will be in plaintext",
                ),
            )

        document_manifest: list[dict] = []
        share_link_bundle_manifest: list[dict] = []

        with sink.stream("manifest.json") as handle:
            writer = StreamingManifestWriter(handle)
            with transaction.atomic():
                for key, qs in manifest_key_to_object_query.items():
                    if key == "documents":
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            document_manifest.extend(batch)
                    elif key == "share_link_bundles":
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            share_link_bundle_manifest.extend(batch)
                    elif self.split_manifest and key in (
                        "notes",
                        "custom_field_instances",
                    ):
                        pass
                    else:
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            writer.write_batch(batch)

            document_map: dict[int, Document] = {
                d.pk: d for d in Document.global_objects.order_by("id")
            }
            share_link_bundle_map: dict[int, ShareLinkBundle] = {
                b.pk: b
                for b in ShareLinkBundle.objects.order_by("id").prefetch_related(
                    "documents",
                )
            }

            # 2. Export files from each document
            for document_dict in self.track(
                document_manifest,
                description="Exporting documents...",
                total=len(document_manifest),
            ):
                document = document_map[document_dict["pk"]]

                base_name = self.generate_base_name(document)
                original_arc, thumbnail_arc, archive_arc = (
                    self.generate_document_targets(document, base_name, document_dict)
                )

                if not self.data_only:
                    self.copy_document_files(
                        document,
                        sink,
                        original_arc,
                        thumbnail_arc,
                        archive_arc,
                    )

                if self.split_manifest:
                    self._write_split_manifest(sink, document_dict, document, base_name)
                else:
                    writer.write_record(document_dict)

            for bundle_dict in share_link_bundle_manifest:
                bundle = share_link_bundle_map[bundle_dict["pk"]]
                bundle_arc = self.generate_share_link_bundle_target(
                    bundle,
                    bundle_dict,
                )
                if not self.data_only and bundle_arc is not None:
                    self.copy_share_link_bundle_file(bundle, sink, bundle_arc)
                writer.write_record(bundle_dict)

            writer.close()

        # 3. Write version (and crypto params) to metadata.json
        metadata: dict[str, str | int | dict[str, str | int]] = {
            "version": version.__full_version_str__,
        }
        if self.passphrase:
            metadata.update(self.get_crypt_params())
        sink.add_json(metadata, "metadata.json")
```

- [ ] **Step 4: Rewrite `generate_document_targets` to return POSIX arcnames**

Replace `generate_document_targets` (`document_exporter.py:582-615`):

```python
    def generate_document_targets(
        self,
        document: Document,
        base_name: Path,
        document_dict: dict,
    ) -> tuple[str, str | None, str | None]:
        """
        Generates the relative POSIX arcnames for a document's original, thumbnail
        and archive files (depending on settings), and records them in the manifest.
        """
        original_name = base_name
        if self.use_folder_prefix:
            original_name = Path("originals") / original_name
        original_arc = original_name.as_posix()
        document_dict[EXPORTER_FILE_NAME] = original_arc

        if not self.no_thumbnail:
            thumbnail_name = base_name.parent / (base_name.stem + "-thumbnail.webp")
            if self.use_folder_prefix:
                thumbnail_name = Path("thumbnails") / thumbnail_name
            thumbnail_arc = thumbnail_name.as_posix()
            document_dict[EXPORTER_THUMBNAIL_NAME] = thumbnail_arc
        else:
            thumbnail_arc = None

        if not self.no_archive and document.has_archive_version:
            archive_name = base_name.parent / (base_name.stem + "-archive.pdf")
            if self.use_folder_prefix:
                archive_name = Path("archive") / archive_name
            archive_arc = archive_name.as_posix()
            document_dict[EXPORTER_ARCHIVE_NAME] = archive_arc
        else:
            archive_arc = None

        return original_arc, thumbnail_arc, archive_arc
```

- [ ] **Step 5: Rewrite `copy_document_files` to call the sink**

Replace `copy_document_files` (`document_exporter.py:617-645`):

```python
    def copy_document_files(
        self,
        document: Document,
        sink: DirectoryExportSink | ZipExportSink,
        original_arc: str,
        thumbnail_arc: str | None,
        archive_arc: str | None,
    ) -> None:
        """
        Hands the document's files to the sink (original, thumbnail, archive).
        """
        sink.add_file(document.source_path, original_arc, checksum=document.checksum)

        if thumbnail_arc:
            sink.add_file(document.thumbnail_path, thumbnail_arc)

        if archive_arc:
            if TYPE_CHECKING:
                assert isinstance(document.archive_path, Path)
            sink.add_file(
                document.archive_path,
                archive_arc,
                checksum=document.archive_checksum,
            )
```

- [ ] **Step 6: Rewrite the share-link-bundle helpers to use arcnames + the sink**

Replace `generate_share_link_bundle_target` (`document_exporter.py:647-669`) and `copy_share_link_bundle_file` (`document_exporter.py:671-687`):

```python
    def generate_share_link_bundle_target(
        self,
        bundle: ShareLinkBundle,
        bundle_dict: dict,
    ) -> str | None:
        """
        Generates the relative POSIX arcname for a share link bundle file, if any.
        """
        if not bundle.file_path:
            return None

        stored_bundle_path = Path(bundle.file_path)
        portable_bundle_path = (
            stored_bundle_path
            if not stored_bundle_path.is_absolute()
            else Path(stored_bundle_path.name)
        )
        export_bundle_path = Path("share_link_bundles") / portable_bundle_path

        bundle_dict["fields"]["file_path"] = portable_bundle_path.as_posix()
        bundle_dict[EXPORTER_SHARE_LINK_BUNDLE_NAME] = export_bundle_path.as_posix()

        return export_bundle_path.as_posix()

    def copy_share_link_bundle_file(
        self,
        bundle: ShareLinkBundle,
        sink: DirectoryExportSink | ZipExportSink,
        bundle_arc: str,
    ) -> None:
        """
        Hands a share link bundle ZIP to the sink.
        """
        bundle_source_path = bundle.absolute_file_path
        if bundle_source_path is None:
            raise FileNotFoundError(f"Share link bundle {bundle.pk} has no file path")

        sink.add_file(bundle_source_path, bundle_arc)
```

- [ ] **Step 7: Rewrite `_write_split_manifest` to use the sink**

Replace `_write_split_manifest` (`document_exporter.py:701-726`):

```python
    def _write_split_manifest(
        self,
        sink: DirectoryExportSink | ZipExportSink,
        document_dict: dict,
        document: Document,
        base_name: Path,
    ) -> None:
        """Write per-document manifest file for --split-manifest mode."""
        content = [document_dict]
        content.extend(
            serializers.serialize(
                "python",
                Note.global_objects.filter(document=document),
            ),
        )
        content.extend(
            serializers.serialize(
                "python",
                CustomFieldInstance.global_objects.filter(document=document),
            ),
        )
        manifest_name = base_name.with_name(f"{base_name.stem}-manifest.json")
        if self.use_folder_prefix:
            manifest_name = Path("json") / manifest_name
        sink.add_json(content, manifest_name.as_posix())
```

- [ ] **Step 8: Delete the now-dead methods and imports**

Delete entirely:

- `check_and_write_json` (`document_exporter.py:728-765`)
- `check_and_copy` (`document_exporter.py:767-802`)

Then remove imports that are now unused (ruff will flag them): `hashlib`, `os` is still used (keep), `shutil`, `tempfile`, `DjangoJSONEncoder`, `delete_empty_directories`, `compute_checksum`, `copy_file_with_basic_stats`. Keep `json`? It is no longer used in the command — remove it too. Keep `Path`, `serializers`, `transaction`, `FileLock`, `version`, the `EXPORTER_*` names, and the models.

Run `ruff check src/documents/management/commands/document_exporter.py` and remove whatever it reports as unused.

- [ ] **Step 9: Run the full exporter + importer regression suites on the VM**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_exporter.py src/documents/tests/test_management_importer.py -v"`
Expected: PASS — every existing test green, including `test_export_zipped`, `test_export_zipped_with_delete`, `test_export_data_only`, the split-manifest tests, and the folder compare/delete tests. If `test_export_zipped`'s `len(namelist()) == 11` fails, a flat export is wrongly emitting directory markers — check `_ensure_dirs` only fires for arcnames with a parent.

- [ ] **Step 10: Lint and format both files**

Run: `ruff check src/documents/export/ src/documents/management/commands/document_exporter.py && ruff format src/documents/export/ src/documents/management/commands/document_exporter.py`
Expected: no errors.

- [ ] **Step 11: Commit**

```bash
git add src/documents/management/commands/document_exporter.py
git commit -m "Refactor: route document_exporter through ExportSink, direct-to-zip"
```

---

## Task 5: Add the `--zip` + `--compare-*` guard test

**Files:**

- Modify: `src/documents/tests/test_management_exporter.py`

- [ ] **Step 1: Write the failing test**

Add this method to the `TestExportImport` class in `src/documents/tests/test_management_exporter.py` (it uses the existing `self.target` from `setUp` and the `CommandError` already imported there):

```python
    def test_zip_with_compare_flags_raises(self) -> None:
        """
        GIVEN:
            - A request to export to a zip file
        WHEN:
            - --compare-checksums or --compare-json is also passed
        THEN:
            - A CommandError is raised (the flags are no-ops in zip mode)
        """
        for flag in ("--compare-checksums", "--compare-json"):
            with self.assertRaises(CommandError):
                call_command(
                    "document_exporter",
                    self.target,
                    "--zip",
                    flag,
                    skip_checks=True,
                )
```

- [ ] **Step 2: Run to verify it passes (the guard already exists from Task 4)**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_exporter.py::TestExportImport::test_zip_with_compare_flags_raises -v"`
Expected: PASS (the `CommandError` guard was added in Task 4 Step 2). If it FAILS, the guard in `handle()` is missing or misordered — fix `handle()`.

- [ ] **Step 3: Commit**

```bash
git add src/documents/tests/test_management_exporter.py
git commit -m "Test: guard --zip combined with --compare-* flags"
```

---

## Task 6: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full sink + exporter + importer suites together**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py src/documents/tests/test_management_exporter.py src/documents/tests/test_management_importer.py -v"`
Expected: PASS, no failures, no errors.

- [ ] **Step 2: Type-check on the VM (pyrefly)**

Sync and run (per CLAUDE.md, include the baseline):

```bash
tar czf - src pyproject.toml uv.lock .pyrefly-baseline.json | ssh -o BatchMode=yes -p 2244 trenton@localhost 'tar xzf - -C ~/projects/paperless-ngx'
ssh -o BatchMode=yes -p 2244 trenton@localhost 'bash -lc "cd ~/projects/paperless-ngx && uv run pyrefly check"'
```

Expected: no new type errors beyond the baseline.

- [ ] **Step 3: Final lint/format pass**

Run: `ruff check src/documents/export/ src/documents/management/commands/document_exporter.py src/documents/tests/test_management_exporter.py && ruff format --check src/documents/export/ src/documents/management/commands/document_exporter.py`
Expected: clean.

- [ ] **Step 4: Confirm the prior-attempt branch is superseded**

This refactor replaces the `feature-direct-zip-export` approach. No action in code — just note in the PR description that `feature-direct-zip-export` can be abandoned.

---

## Notes for the implementer

- **Why the existing `test_management_exporter.py` is the contract:** this is a refactor, not new behavior. The external result (folder layout, zip contents, manifest bytes, round-trip import, `--zip --delete`, `--data-only`, `--split-manifest`) must be byte-for-byte preserved. Those tests already encode it; keep them green at every commit.
- **POSIX arcnames matter on Windows only at runtime**, but the manifest stores the arcname as a portable value, so always use `.as_posix()` — never `str(Path(...))`.
- **The sinks never import `PaperlessCommand`, `track()`, or Rich.** Progress stays in the command's document loop; the sink is a plain I/O object. Do not add a progress dependency to the sinks.
- **Out of scope here:** zip compression control (method/level) — that is the deferred follow-up spec `2026-06-16-export-zip-compression-design.md`, gated on this landing and on verifying the Python 3.14 zstd facts.
