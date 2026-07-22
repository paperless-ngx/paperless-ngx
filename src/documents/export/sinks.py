from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.core.serializers.json import DjangoJSONEncoder

from documents.file_handling import delete_empty_directories
from documents.utils import compute_checksum
from documents.utils import copy_file_with_basic_stats

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
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

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
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
