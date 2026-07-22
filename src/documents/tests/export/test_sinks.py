import io
import json
import os
from pathlib import Path

import pytest

from documents.export.sinks import DirectoryExportSink
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
