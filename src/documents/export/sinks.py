from __future__ import annotations

import abc
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from contextlib import AbstractContextManager
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


class ExportSink(AbstractContextManager, abc.ABC):
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

    @abc.abstractmethod
    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None: ...

    @abc.abstractmethod
    def add_json(self, content: list | dict, arcname: str) -> None: ...

    @abc.abstractmethod
    def stream(self, arcname: str) -> AbstractContextManager[TextIO]: ...

    def _open(self) -> None:
        """Hook called on context entry. Override as needed."""

    @abc.abstractmethod
    def _finalize(self) -> None:
        """Commit on clean exit."""

    @abc.abstractmethod
    def _abort(self) -> None:
        """Roll back on exception."""

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

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
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

    @staticmethod
    def _content_unchanged(target: Path, new_bytes: bytes) -> bool:
        """True if ``target`` already holds byte-identical content (BLAKE2b)."""
        return (
            hashlib.blake2b(target.read_bytes()).hexdigest()
            == hashlib.blake2b(new_bytes).hexdigest()
        )

    def add_json(self, content: list | dict, arcname: str) -> None:
        target = (self._target / arcname).resolve()
        json_str = _dumps(content)
        perform_write = True
        if target in self._snapshot:
            self._snapshot.discard(target)
            if self._compare_json and self._content_unchanged(
                target,
                json_str.encode("utf-8"),
            ):
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
            if self._compare_json and self._content_unchanged(
                target,
                tmp.read_bytes(),
            ):
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
        assert self._zip is not None
        dir_arc = ""
        for part in PurePosixPath(arcname).parts[:-1]:
            dir_arc += f"{part}/"
            if dir_arc not in self._dirs:
                self._dirs.add(dir_arc)
                self._zip.mkdir(dir_arc)

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
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
        handle = os.fdopen(fd, "w", encoding="utf-8")
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
        self._tmp_path.replace(self._zip_path)

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
