# Export Zip Compression Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--zip-compression {stored,deflated,bzip2,lzma,zstd}` and `--zip-compression-level N` flags to `document_exporter`, threaded into `ZipExportSink`, with import-side safety for codecs the running Python can't read.

**Architecture:** A new pure-data module `documents/export/compression.py` owns the method↔constant map, per-method level bounds, the runtime availability probe, and a compress-type readability check. `ZipExportSink` gains `compression`/`compresslevel` constructor params. The command validates flags up front (fail-fast `CommandError`) and constructs the sink; the importer pre-checks entry compress types before extracting.

**Tech Stack:** Python ≥3.11 (zstd only on 3.14+), `zipfile`, `compression.zstd` (PEP 784), pytest + pytest-mock + factory-boy. Backend tests run on the Linux VM (Python 3.11 — zstd positive tests are `skipif`-guarded); `ruff` runs locally.

**Spec:** `docs/superpowers/specs/2026-06-16-export-zip-compression-design.md`

**PREREQUISITE:** The base refactor `docs/superpowers/plans/2026-06-16-export-sink-architecture.md` MUST be merged first. This plan assumes `src/documents/export/sinks.py` exists with `ZipExportSink(target, zip_name, *, delete=False)` opening its `ZipFile` in `_open()`.

---

## Verified facts (CPython 3.14.3, via `uv run --python 3.14 --no-project`)

- Constants: `ZIP_STORED=0`, `ZIP_DEFLATED=8`, `ZIP_BZIP2=12`, `ZIP_LZMA=14`, `ZIP_ZSTANDARD=93` (zstd added 3.14; absent on < 3.14).
- `ZipFile(file, "w", compression=…, compresslevel=…)` applies both as the default for every `write`/`writestr` — no per-entry args needed (verified).
- Level bounds: `deflated` 0–9, `bzip2` 1–9, `lzma`/`stored` ignore level, `zstd` -131072…22 (`compression.zstd.CompressionParameter.compression_level.bounds() == (-131072, 22)`).
- An invalid level fails at the **first write** (`ValueError: Invalid initialization option` / `compresslevel must be between 1 and 9`), plus GC-time `AttributeError` noise on close — hence up-front validation.
- zstd is backed by `compression.zstd`; `zipfile` raises `RuntimeError` if it's unavailable.

## Conventions for every task

- **Run backend tests on the VM:** `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<targets>"` (never locally).
- **Lint locally:** `ruff check <paths> && ruff format <paths>` (global ruff, not `uv run`).
- **Tests are pytest-style:** classes, `@pytest.mark.django_db` on the class only where DB is needed (the `compression.py` and sink tests need no DB), factory-boy, `mocker`, `parametrize`, full type annotations.
- The VM runs Python 3.11, so **zstd positive tests must be `@pytest.mark.skipif(...)`-guarded**; they will simply not run there. zstd _rejection_ tests (the < 3.14 path) DO run on the VM.

## File structure

- **Create** `src/documents/export/compression.py` — method map, CLI choices, level bounds, `compression_available()`, `level_error()`, `compress_type_readable()`, `unreadable_method_names()`. Pure, no Django.
- **Create** `src/documents/tests/export/test_compression.py` — unit tests for the above.
- **Modify** `src/documents/export/sinks.py` — `ZipExportSink.__init__` gains `compression`/`compresslevel`; `_open()` passes them to `ZipFile`.
- **Modify** `src/documents/tests/export/test_sinks.py` — assert the chosen `compress_type` is applied.
- **Modify** `src/documents/management/commands/document_exporter.py` — add the two CLI flags, up-front validation, and pass resolved values to `ZipExportSink`.
- **Modify** `src/documents/tests/test_management_exporter.py` — flag validation + default-unchanged tests.
- **Modify** `src/documents/management/commands/document_importer.py` — pre-extract compress-type check.
- **Modify** `src/documents/tests/test_management_importer.py` — unsupported-codec → `CommandError`.
- **Modify** `docs/administration.md` — document both flags + zstd portability caveat.

---

## Task 1: `documents/export/compression.py` (pure compression policy)

**Files:**

- Create: `src/documents/export/compression.py`
- Test: `src/documents/tests/export/test_compression.py`

- [ ] **Step 1: Write the failing tests**

Create `src/documents/tests/export/test_compression.py`:

```python
import sys
import zipfile

import pytest

from documents.export import compression


class TestCompressionMethods:
    def test_choices_always_include_zstd(self) -> None:
        # zstd is offered regardless of runtime; availability is checked separately
        assert compression.COMPRESSION_CHOICES == (
            "stored",
            "deflated",
            "bzip2",
            "lzma",
            "zstd",
        )

    @pytest.mark.parametrize(
        ("name", "constant"),
        [
            ("stored", zipfile.ZIP_STORED),
            ("deflated", zipfile.ZIP_DEFLATED),
            ("bzip2", zipfile.ZIP_BZIP2),
            ("lzma", zipfile.ZIP_LZMA),
        ],
    )
    def test_method_maps_to_zipfile_constant(self, name: str, constant: int) -> None:
        assert compression.COMPRESSION_METHODS[name] == constant

    def test_stored_and_deflated_always_available(self) -> None:
        assert compression.compression_available("stored")
        assert compression.compression_available("deflated")

    def test_zstd_availability_tracks_runtime(self) -> None:
        expected: bool = sys.version_info >= (3, 14)
        assert compression.compression_available("zstd") == expected


class TestLevelError:
    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("deflated", 0),
            ("deflated", 9),
            ("bzip2", 1),
            ("bzip2", 9),
            ("deflated", None),
            ("stored", None),
        ],
    )
    def test_valid_levels_return_none(self, method: str, level: int | None) -> None:
        assert compression.level_error(method, level) is None

    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("deflated", 10),
            ("deflated", -1),
            ("bzip2", 0),
            ("bzip2", 10),
        ],
    )
    def test_out_of_range_levels_return_message(
        self,
        method: str,
        level: int,
    ) -> None:
        msg: str | None = compression.level_error(method, level)
        assert msg is not None
        assert "between" in msg

    @pytest.mark.parametrize("method", ["stored", "lzma"])
    def test_level_on_levelless_method_is_rejected(self, method: str) -> None:
        msg: str | None = compression.level_error(method, 5)
        assert msg is not None
        assert "no effect" in msg


class TestCompressTypeReadable:
    @pytest.mark.parametrize("ct", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_stored_and_deflated_always_readable(self, ct: int) -> None:
        assert compression.compress_type_readable(ct)

    def test_zstd_compress_type_readability_tracks_runtime(self) -> None:
        # 93 = ZIP_ZSTANDARD; 20 = legacy zstd method id (read-only)
        expected: bool = sys.version_info >= (3, 14)
        assert compression.compress_type_readable(93) == expected
        assert compression.compress_type_readable(20) == expected

    def test_unknown_compress_type_is_unreadable(self) -> None:
        assert not compression.compress_type_readable(9999)

    def test_unreadable_method_names_lists_methods(self) -> None:
        # An unknown method id maps to no name and is reported generically.
        names: set[str] = compression.unreadable_method_names({9999})
        assert names == {"method 9999"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_compression.py -v"`
Expected: FAIL with `ModuleNotFoundError: No module named 'documents.export.compression'`.

- [ ] **Step 3: Implement `compression.py`**

Create `src/documents/export/compression.py`:

```python
from __future__ import annotations

import importlib
import zipfile

# ZIP_ZSTANDARD exists only on Python 3.14+ (PEP 784). None elsewhere.
ZSTD: int | None = getattr(zipfile, "ZIP_ZSTANDARD", None)

# CLI choices are fixed across runtimes so argparse never hides zstd; runtime
# availability is enforced separately in compression_available().
COMPRESSION_CHOICES: tuple[str, ...] = (
    "stored",
    "deflated",
    "bzip2",
    "lzma",
    "zstd",
)

# Method name -> zipfile compression constant (zstd only when supported).
COMPRESSION_METHODS: dict[str, int] = {
    "stored": zipfile.ZIP_STORED,
    "deflated": zipfile.ZIP_DEFLATED,
    "bzip2": zipfile.ZIP_BZIP2,
    "lzma": zipfile.ZIP_LZMA,
}
if ZSTD is not None:
    COMPRESSION_METHODS["zstd"] = ZSTD

# Inclusive (min, max) level bounds per method; None => level not applicable.
# Verified on CPython 3.14.3.
LEVEL_BOUNDS: dict[str, tuple[int, int] | None] = {
    "stored": None,
    "deflated": (0, 9),
    "bzip2": (1, 9),
    "lzma": None,
    "zstd": (-131072, 22),
}

# zipfile compress_type id -> method name. 93 = current zstd id, 20 = legacy
# zstd id that zipfile can still read.
_COMPRESS_TYPE_TO_METHOD: dict[int, str] = {
    zipfile.ZIP_STORED: "stored",
    zipfile.ZIP_DEFLATED: "deflated",
    zipfile.ZIP_BZIP2: "bzip2",
    zipfile.ZIP_LZMA: "lzma",
    93: "zstd",
    20: "zstd",
}


def compression_available(method: str) -> bool:
    """Whether the running interpreter can actually use the given method."""
    if method in ("stored", "deflated"):
        # zlib is a hard CPython dependency; stored needs nothing.
        return True
    if method == "bzip2":
        return _module_importable("bz2")
    if method == "lzma":
        return _module_importable("lzma")
    if method == "zstd":
        return ZSTD is not None and _module_importable("compression.zstd")
    return False


def _module_importable(name: str) -> bool:
    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


def level_error(method: str, level: int | None) -> str | None:
    """Return a human message if (method, level) is invalid, else None."""
    if level is None:
        return None
    bounds = LEVEL_BOUNDS[method]
    if bounds is None:
        return f"--zip-compression-level has no effect for '{method}'"
    low, high = bounds
    if not (low <= level <= high):
        return (
            f"--zip-compression-level for '{method}' must be between "
            f"{low} and {high}"
        )
    return None


def compress_type_readable(compress_type: int) -> bool:
    """Whether this interpreter can decompress an entry of the given type."""
    method = _COMPRESS_TYPE_TO_METHOD.get(compress_type)
    if method is None:
        return False
    return compression_available(method)


def unreadable_method_names(compress_types: set[int]) -> set[str]:
    """Map a set of compress_type ids to human method names for error messages."""
    names: set[str] = set()
    for ct in compress_types:
        names.add(_COMPRESS_TYPE_TO_METHOD.get(ct, f"method {ct}"))
    return names
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_compression.py -v"`
Expected: PASS (on the 3.11 VM, `test_zstd_availability_tracks_runtime` and `test_zstd_compress_type_readability_tracks_runtime` assert `False`).

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/export/compression.py src/documents/tests/export/test_compression.py && ruff format src/documents/export/compression.py src/documents/tests/export/test_compression.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/export/compression.py src/documents/tests/export/test_compression.py
git commit -m "Feature: add export compression policy module"
```

---

## Task 2: `ZipExportSink` accepts compression method + level

**Files:**

- Modify: `src/documents/export/sinks.py`
- Test: `src/documents/tests/export/test_sinks.py`

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/export/test_sinks.py` (the top-of-file block already imports `zipfile`, `Path`, `pytest`, `ZipExportSink`, `StreamingManifestWriter` from the base-refactor plan):

```python
class TestZipExportSinkCompression:
    @pytest.fixture()
    def source_file(self, tmp_path: Path) -> Path:
        src: Path = tmp_path / "src" / "doc.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"PDF-CONTENT" * 100)
        return src

    @pytest.mark.parametrize(
        ("method", "constant"),
        [
            ("stored", zipfile.ZIP_STORED),
            ("deflated", zipfile.ZIP_DEFLATED),
            ("bzip2", zipfile.ZIP_BZIP2),
            ("lzma", zipfile.ZIP_LZMA),
        ],
    )
    def test_compression_method_is_applied_to_file_entries(
        self,
        tmp_path: Path,
        source_file: Path,
        method: str,
        constant: int,
    ) -> None:
        target: Path = tmp_path / "out"
        target.mkdir()
        with ZipExportSink(
            target,
            "export",
            delete=False,
            compression=constant,
        ) as sink:
            sink.add_file(source_file, "doc.pdf")
        with zipfile.ZipFile(target / "export.zip") as zf:
            info = zf.getinfo("doc.pdf")
            assert info.compress_type == constant

    def test_compressing_method_beats_stored(
        self,
        tmp_path: Path,
        source_file: Path,
    ) -> None:
        # Robust size invariant: a compressing method must be <= stored on
        # compressible content (avoids flaky level-9-vs-level-1 comparisons).
        sizes: dict[str, int] = {}
        for name, constant in (("stored", zipfile.ZIP_STORED), ("deflated", zipfile.ZIP_DEFLATED)):
            target: Path = tmp_path / name
            target.mkdir()
            with ZipExportSink(target, "export", delete=False, compression=constant) as sink:
                sink.add_file(source_file, "doc.pdf")
            sizes[name] = (target / "export.zip").stat().st_size
        assert sizes["deflated"] <= sizes["stored"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py::TestZipExportSinkCompression -v"`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'compression'`.

- [ ] **Step 3: Add the params to `ZipExportSink`**

In `src/documents/export/sinks.py`, change `ZipExportSink.__init__` to accept the new keyword-only params and store them, and pass them in `_open()`:

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
        self._target = target.resolve()
        self._zip_path = (self._target / zip_name).with_suffix(".zip")
        self._tmp_path = self._zip_path.with_name(self._zip_path.name + ".tmp")
        self._delete = delete
        self._compression = compression
        self._compresslevel = compresslevel
        self._zip: zipfile.ZipFile | None = None
        self._dirs: set[str] = set()
        self._pending_manifest: tuple[Path, str] | None = None
        self._stream_open = False
```

And in `_open()`:

```python
    def _open(self) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._zip = zipfile.ZipFile(
            self._tmp_path,
            "w",
            compression=self._compression,
            compresslevel=self._compresslevel,
            allowZip64=True,
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/test_sinks.py -v"`
Expected: PASS (all sink tests, including the four method params and the size invariant). `bzip2`/`lzma` are present on the VM's CPython, so those params pass.

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/export/sinks.py && ruff format src/documents/export/sinks.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/export/sinks.py src/documents/tests/export/test_sinks.py
git commit -m "Feature: ZipExportSink accepts compression method and level"
```

---

## Task 3: Wire CLI flags + validation into `document_exporter`

**Files:**

- Modify: `src/documents/management/commands/document_exporter.py`
- Test: `src/documents/tests/test_management_exporter.py`

- [ ] **Step 1: Add the argparse flags**

In `document_exporter.py`, add the import near the other `documents.export` import:

```python
from documents.export.compression import COMPRESSION_CHOICES
from documents.export.compression import COMPRESSION_METHODS
from documents.export.compression import compression_available
from documents.export.compression import level_error
from documents.export.compression import ZSTD
```

In `add_arguments`, after the `--zip-name` argument, add:

```python
        parser.add_argument(
            "--zip-compression",
            choices=COMPRESSION_CHOICES,
            default=None,
            help=(
                "Compression method for the export zip (requires --zip). "
                "Default: deflated. 'zstd' requires Python 3.14+ on both the "
                "exporting and importing machine."
            ),
        )

        parser.add_argument(
            "--zip-compression-level",
            type=int,
            default=None,
            help=(
                "Compression level for the export zip (requires --zip). "
                "deflated: 0-9, bzip2: 1-9, zstd: -131072..22; ignored for "
                "stored/lzma."
            ),
        )
```

- [ ] **Step 2: Read + validate the flags in `handle()`**

In `handle()`, after the existing `--compare-*` + `--zip` guard, add the compression flag handling. Insert before the sink construction:

```python
        zip_compression: str | None = options["zip_compression"]
        zip_compression_level: int | None = options["zip_compression_level"]

        if not self.zip_export and (
            zip_compression is not None or zip_compression_level is not None
        ):
            raise CommandError(
                "--zip-compression and --zip-compression-level require --zip",
            )

        compression_method = zip_compression or "deflated"
        if self.zip_export:
            if not compression_available(compression_method):
                if compression_method == "zstd" and ZSTD is None:
                    raise CommandError(
                        "zstd compression requires Python 3.14 or newer",
                    )
                raise CommandError(
                    f"Compression method '{compression_method}' is not "
                    f"available on this Python runtime",
                )
            level_msg = level_error(compression_method, zip_compression_level)
            if level_msg is not None:
                raise CommandError(level_msg)
```

- [ ] **Step 3: Pass the resolved values into `ZipExportSink`**

Change the `ZipExportSink(...)` construction in `handle()` to:

```python
        if self.zip_export:
            sink = ZipExportSink(
                self.target,
                options["zip_name"],
                delete=self.delete,
                compression=COMPRESSION_METHODS[compression_method],
                compresslevel=zip_compression_level,
            )
        else:
            sink = DirectoryExportSink(
                self.target,
                compare_checksums=self.compare_checksums,
                compare_json=self.compare_json,
                delete=self.delete,
            )
```

- [ ] **Step 4: Write the command-level tests**

Add to the `TestExportImport` class in `src/documents/tests/test_management_exporter.py` (imports `call_command`, `CommandError`, `ZipFile`, `timezone` already present):

```python
    def test_compression_flags_require_zip(self) -> None:
        for args in (
            ["--zip-compression", "lzma"],
            ["--zip-compression-level", "5"],
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "document_exporter",
                    self.target,
                    *args,
                    skip_checks=True,
                )

    def test_zip_compression_level_out_of_range_raises(self) -> None:
        with self.assertRaises(CommandError):
            call_command(
                "document_exporter",
                self.target,
                "--zip",
                "--zip-compression",
                "deflated",
                "--zip-compression-level",
                "99",
                skip_checks=True,
            )

    def test_zip_compression_level_rejected_for_stored(self) -> None:
        with self.assertRaises(CommandError):
            call_command(
                "document_exporter",
                self.target,
                "--zip",
                "--zip-compression",
                "stored",
                "--zip-compression-level",
                "5",
                skip_checks=True,
            )

    def test_zip_lzma_compression_round_trips(self) -> None:
        call_command(
            "document_exporter",
            self.target,
            "--zip",
            "--zip-compression",
            "lzma",
            skip_checks=True,
        )
        expected = str(
            self.target / f"export-{timezone.localdate().isoformat()}.zip",
        )
        self.assertIsFile(expected)
        with ZipFile(expected) as zip_file:
            info = zip_file.getinfo("manifest.json")
            # manifest.json carries the chosen method; deflated is the default
            self.assertEqual(info.compress_type, 14)  # ZIP_LZMA

    def test_default_zip_uses_deflate(self) -> None:
        call_command(
            "document_exporter",
            self.target,
            "--zip",
            skip_checks=True,
        )
        expected = str(
            self.target / f"export-{timezone.localdate().isoformat()}.zip",
        )
        with ZipFile(expected) as zip_file:
            info = zip_file.getinfo("manifest.json")
            self.assertEqual(info.compress_type, 8)  # ZIP_DEFLATED
```

- [ ] **Step 5: Run the tests**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_exporter.py -v"`
Expected: PASS — the new tests plus all existing exporter tests stay green.

- [ ] **Step 6: Lint**

Run: `ruff check src/documents/management/commands/document_exporter.py src/documents/tests/test_management_exporter.py && ruff format src/documents/management/commands/document_exporter.py src/documents/tests/test_management_exporter.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/documents/management/commands/document_exporter.py src/documents/tests/test_management_exporter.py
git commit -m "Feature: add --zip-compression and --zip-compression-level flags"
```

---

## Task 4: Importer pre-check for unreadable codecs

**Files:**

- Modify: `src/documents/management/commands/document_importer.py`
- Test: `src/documents/tests/test_management_importer.py`

- [ ] **Step 1: Write the failing test**

The importer test file `src/documents/tests/test_management_importer.py` is
`TestCase`-style (`class TestCommandImport(... TestCase)`, `self.assertRaises`,
`DirectoriesMixin` gives `self.dirs.scratch_dir`). Match that style. Add this
method to `TestCommandImport`. It builds a valid zip and patches the readability
probe so the check fires deterministically on any runtime:

```python
    def test_import_rejects_unreadable_compression(self) -> None:
        """
        GIVEN:
            - A zip archive with an entry whose compression this Python can't read
        WHEN:
            - Import is attempted
        THEN:
            - A CommandError naming the issue is raised, before extraction
        """
        import zipfile
        from unittest import mock

        archive = Path(self.dirs.scratch_dir) / "export.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("manifest.json", "[]")

        with mock.patch(
            "documents.management.commands.document_importer.compress_type_readable",
            return_value=False,
        ):
            with self.assertRaises(CommandError) as e:
                call_command(
                    "document_importer",
                    str(archive),
                    "--no-progress-bar",
                    skip_checks=True,
                )
        self.assertIn("compression", str(e.exception))
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_importer.py -k unreadable_compression -v"`
Expected: FAIL — no pre-check exists yet, so the import proceeds (or fails with a different error).

- [ ] **Step 3: Implement the pre-check**

In `document_importer.py`, add the import:

```python
from documents.export.compression import compress_type_readable
from documents.export.compression import unreadable_method_names
```

Find the zip-handling block (around `document_importer.py:453`):

```python
                with ZipFile(self.source) as zf:
                    zf.extractall(tmp_dir)
```

Replace it with a pre-check before extraction:

```python
                with ZipFile(self.source) as zf:
                    unsupported = {
                        info.compress_type
                        for info in zf.infolist()
                        if not compress_type_readable(info.compress_type)
                    }
                    if unsupported:
                        names = ", ".join(sorted(unreadable_method_names(unsupported)))
                        raise CommandError(
                            f"This archive uses compression this Python cannot "
                            f"read ({names}). zstd archives require Python 3.14+.",
                        )
                    zf.extractall(tmp_dir)
```

Confirm `CommandError` is imported in `document_importer.py` (it is used elsewhere; if not, add `from django.core.management.base import CommandError`).

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_importer.py -v"`
Expected: PASS — the new test plus all existing importer tests (normal deflated/stored archives still import).

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/management/commands/document_importer.py src/documents/tests/test_management_importer.py && ruff format src/documents/management/commands/document_importer.py src/documents/tests/test_management_importer.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/documents/management/commands/document_importer.py src/documents/tests/test_management_importer.py
git commit -m "Feature: importer rejects archives with unreadable compression"
```

---

## Task 5: Document the flags

**Files:**

- Modify: `docs/administration.md`

- [ ] **Step 1: Add the flags to the option list**

In `docs/administration.md`, update the usage block (around line 257) to include the new flags:

```
document_exporter target [-c] [-d] [-f] [-na] [-nt] [-p] [-sm] [-z]

optional arguments:
-c,  --compare-checksums
-cj, --compare-json
-d,  --delete
-f,  --use-filename-format
-na, --no-archive
-nt, --no-thumbnail
-p,  --use-folder-prefix
-sm, --split-manifest
-z,  --zip
-zn, --zip-name
--zip-compression
--zip-compression-level
--data-only
--no-progress-bar
--passphrase
```

- [ ] **Step 2: Add the prose**

After the `-z`/`--zip` paragraph (around line 330), add:

```markdown
The compression method for the zip can be set with `--zip-compression`
(`stored`, `deflated` (default), `bzip2`, `lzma`, or `zstd`) and tuned with
`--zip-compression-level` (deflated: 0–9, bzip2: 1–9, zstd: -131072–22; ignored
for `stored` and `lzma`). Both options require `--zip`.

!!! warning

    `zstd` compression requires Python 3.14 or newer on **both** the machine
    creating the export and any machine importing it. An archive compressed with
    `zstd` (or `lzma`/`bzip2` where those modules are unavailable) cannot be
    imported on a runtime that lacks the codec; the importer will refuse it with
    a clear error. The default `deflated` is universally readable.
```

- [ ] **Step 3: Verify the docs build is not broken (lint markdown)**

Run: `ruff check docs/ 2>/dev/null; echo "docs are markdown; rely on prettier pre-commit"`
(No code to test. The prettier pre-commit hook will reformat on commit.)

- [ ] **Step 4: Commit**

```bash
git add docs/administration.md
git commit -m "Docs: document --zip-compression and --zip-compression-level"
```

---

## Task 6: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full backend suites on the VM**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/export/ src/documents/tests/test_management_exporter.py src/documents/tests/test_management_importer.py -v"`
Expected: PASS, no failures.

- [ ] **Step 2: Spot-check the zstd happy path on Python 3.14 (cannot run under Django on the 3.11 VM)**

The zstd positive round-trip can't run in the 3.11 test env. Confirm the policy module behaves on a real 3.14 interpreter with a standalone check (no Django needed):

Run:

```bash
uv run --python 3.14 --no-project python -c "import sys; sys.path.insert(0,'src'); import django; print('skip')" 2>/dev/null || \
uv run --python 3.14 --no-project python -c "
import zipfile, io
from compression.zstd import CompressionParameter as CP
print('zstd const', zipfile.ZIP_ZSTANDARD, 'bounds', CP.compression_level.bounds())
buf = io.BytesIO()
with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_ZSTANDARD,compresslevel=19) as zf:
    zf.writestr('a.txt','x'*1000)
with zipfile.ZipFile(buf) as zf:
    assert zf.getinfo('a.txt').compress_type == zipfile.ZIP_ZSTANDARD
    assert zf.read('a.txt') == b'x'*1000
print('zstd round-trip OK')
"
```

Expected: prints `zstd const 93 bounds (-131072, 22)` and `zstd round-trip OK`. This validates the constant, bounds, and that a zstd archive round-trips — the parts the 3.11 CI cannot exercise.

- [ ] **Step 3: Type-check on the VM (pyrefly)**

```bash
tar czf - src pyproject.toml uv.lock .pyrefly-baseline.json | ssh -o BatchMode=yes -p 2244 trenton@localhost 'tar xzf - -C ~/projects/paperless-ngx'
ssh -o BatchMode=yes -p 2244 trenton@localhost 'bash -lc "cd ~/projects/paperless-ngx && uv run pyrefly check"'
```

Expected: no new type errors beyond the baseline. (Note: `import compression.zstd` is guarded behind `importlib.import_module`, so it is never statically resolved on the 3.11 baseline.)

- [ ] **Step 4: Final lint**

Run: `ruff check src/documents/export/ src/documents/management/commands/document_exporter.py src/documents/management/commands/document_importer.py && ruff format --check src/documents/export/ src/documents/management/commands/document_exporter.py src/documents/management/commands/document_importer.py`
Expected: clean.

---

## Notes for the implementer

- **Default behavior is unchanged:** with no flags, the sink is constructed with `compression=ZIP_DEFLATED, compresslevel=None` — byte-method-identical to today (`shutil.make_archive` used `ZIP_DEFLATED` with no level). `test_default_zip_uses_deflate` pins this.
- **zstd availability is gated three ways and never imported statically:** the constant via `getattr`, the codec via `importlib.import_module("compression.zstd")`, and the CLI value rejected with a friendly message on < 3.14. The choices list always contains `zstd` so argparse doesn't hide it.
- **The importer pre-check is the safety net** for portability foot-guns — without it an unreadable entry raises a bare `NotImplementedError` mid-`extractall`. The check runs on `infolist()` (metadata only) before any extraction.
- **Why `--zip-compression` defaults to `None`, not `"deflated"`:** so `handle()` can detect "user passed it without `--zip`" and fail fast. The effective default is resolved as `zip_compression or "deflated"`.
