import io
import json
import os
import zipfile
from pathlib import Path

import pytest
import pytest_mock
from pytest_django.fixtures import SettingsWrapper

from documents.export.sinks import DirectoryExportSink
from documents.export.sinks import ExportSink
from documents.export.sinks import StreamingManifestWriter
from documents.export.sinks import ZipExportSink
from documents.export.sinks import _dumps


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    src: Path = tmp_path / "src" / "doc.pdf"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"PDF-CONTENT")
    return src


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


class TestZipExportSink:
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

    def test_exception_inside_stream_cleans_up_manifest_tmp(
        self,
        tmp_path: Path,
        source_file: Path,
        settings: SettingsWrapper,
    ) -> None:
        scratch_dir = tmp_path / "scratch"
        settings.SCRATCH_DIR = scratch_dir
        target: Path = tmp_path / "out"
        target.mkdir()
        with pytest.raises(RuntimeError):
            with ZipExportSink(target, "export", delete=False) as sink:
                sink.add_file(source_file, "doc.pdf")
                with sink.stream("manifest.json") as handle:
                    handle.write("[")
                    raise RuntimeError("boom")
        assert list(scratch_dir.glob("export-manifest-*")) == []
        assert not (target / "export.zip").exists()
        assert not (target / "export.zip.tmp").exists()

    def test_abort_after_manifest_written_cleans_up_pending_tmp(
        self,
        tmp_path: Path,
        settings: SettingsWrapper,
    ) -> None:
        scratch_dir = tmp_path / "scratch"
        settings.SCRATCH_DIR = scratch_dir
        target: Path = tmp_path / "out"
        target.mkdir()
        with pytest.raises(RuntimeError):
            with ZipExportSink(target, "export", delete=False) as sink:
                with sink.stream("manifest.json") as handle:
                    handle.write("[]")
                raise RuntimeError("boom")
        assert list(scratch_dir.glob("export-manifest-*")) == []
        assert not (target / "export.zip").exists()

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


class TestZipExportSinkCompression:
    @pytest.mark.parametrize(
        ("method", "constant"),
        [
            ("stored", zipfile.ZIP_STORED),
            ("deflated", zipfile.ZIP_DEFLATED),
            ("bzip2", zipfile.ZIP_BZIP2),
            ("lzma", zipfile.ZIP_LZMA),
        ],
    )
    def test_compression_and_level_forwarded_to_zipfile(
        self,
        mocker: pytest_mock.MockerFixture,
        tmp_path: Path,
        method: str,
        constant: int,
    ) -> None:
        # ZipExportSink's only responsibility here is forwarding the
        # constructor's compression/compresslevel to zipfile.ZipFile
        # unchanged; whether ZipFile actually compresses is Python's contract,
        # not ours, so this checks the call args rather than the archive.
        target: Path = tmp_path / "out"
        target.mkdir()
        zip_cls = mocker.patch("documents.export.sinks.zipfile.ZipFile")
        sink = ZipExportSink(target, "export", compression=constant, compresslevel=5)
        sink._open()
        zip_cls.assert_called_once_with(
            mocker.ANY,
            "w",
            compression=constant,
            compresslevel=5,
            allowZip64=True,
        )


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
