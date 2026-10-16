"""Exercise the mandatory Go process and fail-closed protocol boundary."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.core.management import CommandError
from django.core.management import call_command

from documents.integrity import IntegrityScanError
from documents.integrity import Manifest
from documents.integrity import scan_files
from documents.sanity_checker import SanityCheckFailedException
from documents.sanity_checker import check_sanity
from paperless.models import ApplicationConfiguration

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings
    from pytest_mock import MockerFixture

    from documents.models import Document
    from paperless_testing.dirs import PaperlessDirs


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    return Manifest(
        version=1,
        media_root=str(tmp_path),
        checksum_algorithm="sha256",
        files=[],
        ignored_filenames=[],
        excluded_paths=[],
    )


def executable(tmp_path: Path, settings: Settings, script: str) -> Path:
    binary = tmp_path / "scanner with spaces 雪"
    binary.write_text(f"#!{sys.executable}\n{script}\n")
    binary.chmod(0o755)
    settings.INTEGRITY_SCANNER_BINARY = str(binary)
    return binary


@pytest.mark.django_db
class TestIntegratedScanner:
    def test_command_really_uses_go(
        self,
        sample_doc: Document,
        mocker: MockerFixture,
    ) -> None:
        spy = mocker.spy(subprocess, "Popen")
        mocker.patch(
            "documents.utils.compute_checksum",
            side_effect=AssertionError("Python checksum must not run"),
        )
        out = StringIO()
        call_command(
            "document_sanity_checker",
            "--no-progress-bar",
            stdout=out,
            skip_checks=True,
        )
        assert "No issues detected" in out.getvalue()
        assert spy.call_count == 1
        args = spy.call_args.args[0]
        assert len(args) == 1
        binary = shutil.which(args[0])
        assert binary is not None
        assert Path(binary).read_bytes()[:4] == b"\x7fELF"
        assert spy.call_args.kwargs.get("shell", False) is False

    def test_unicode_and_long_filename(self, sample_doc: Document) -> None:
        original = sample_doc.source_path
        sample_doc.filename = "目录 with spaces/" + "a" * 170 + " 雪.pdf"
        target = original.parent / sample_doc.filename
        target.parent.mkdir()
        original.rename(target)
        sample_doc.save()
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning

    @pytest.mark.parametrize("from_config", [False, True])
    def test_exclusions(
        self,
        sample_doc: Document,
        paperless_dirs: PaperlessDirs,
        settings: Settings,
        *,
        from_config: bool,
    ) -> None:
        name = "/logo/test.svg" if from_config else "/logo with spaces 雪.svg"
        logo = paperless_dirs.media_dir / name.lstrip("/")
        logo.parent.mkdir(exist_ok=True)
        logo.touch()
        paperless_dirs.media_lock.touch()
        for ignored in settings.IGNORABLE_FILES:
            (paperless_dirs.originals_dir / ignored).touch()
        if from_config:
            config = ApplicationConfiguration.objects.first()
            assert config is not None
            config.app_logo = name.lstrip("/")
            config.save(update_fields=["app_logo"])
        else:
            settings.APP_LOGO = name
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning

    @pytest.mark.parametrize("kind", ["original", "archive", "thumbnail"])
    def test_external_symlink(
        self,
        sample_doc: Document,
        tmp_path: Path,
        kind: str,
    ) -> None:
        path = getattr(
            sample_doc,
            {
                "original": "source_path",
                "archive": "archive_path",
                "thumbnail": "thumbnail_path",
            }[kind],
        )
        outside = tmp_path / "outside document"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        messages = check_sanity()
        assert messages.has_error
        assert any("Unsafe path" in m["message"] for m in messages[sample_doc.pk])
        assert not any(
            "Checksum mismatch" in m["message"] for m in messages[sample_doc.pk]
        )

    def test_internal_alias(self, sample_doc: Document) -> None:
        source = sample_doc.source_path
        actual = source.with_name("actual.pdf")
        source.rename(actual)
        source.symlink_to(actual)
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning

    def test_global_unsafe_path_never_prints_clean(
        self,
        sample_doc: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        (paperless_dirs.media_dir / "loop").symlink_to("loop")
        out = StringIO()
        call_command(
            "document_sanity_checker",
            "--no-progress-bar",
            stdout=out,
            skip_checks=True,
        )
        assert "Unsafe path" in out.getvalue()
        assert "global error(s)" in out.getvalue()
        assert "No issues" not in out.getvalue()
        from documents.tasks import sanity_check

        with pytest.raises(SanityCheckFailedException, match="global error"):
            sanity_check()

    def test_missing_binary_command_fails(
        self,
        sample_doc: Document,
        settings: Settings,
        tmp_path: Path,
    ) -> None:
        settings.INTEGRITY_SCANNER_BINARY = str(tmp_path / "absent")
        out = StringIO()
        with pytest.raises(CommandError, match="Cannot start integrity scanner"):
            call_command(
                "document_sanity_checker",
                "--no-progress-bar",
                stdout=out,
                skip_checks=True,
            )
        assert "No issues" not in out.getvalue()


class TestProtocolFailures:
    def test_real_scanner_sha256(self, manifest: Manifest) -> None:
        path = Path(manifest["media_root"]) / "original"
        path.write_bytes(b"abc")
        manifest["files"] = [
            {
                "document_id": 123,
                "kind": "original",
                "path": str(path),
                "checksum": "wrong",
            },
        ]
        findings = scan_files(manifest)
        assert findings == [
            {
                "code": "checksum_mismatch",
                "file_index": 0,
                "path": str(path),
                "detail": "",
                "actual_checksum": hashlib.sha256(b"abc").hexdigest(),
            },
        ]

    @pytest.mark.parametrize(
        "payload",
        [
            "not JSON",
            "{}",
            "[]",
            "null",
            '{"version":2,"complete":true,"checked_files":0,"findings":[]}',
            '{"version":true,"complete":true,"checked_files":0,"findings":[]}',
            '{"version":1,"complete":false,"checked_files":0,"findings":[]}',
            '{"version":1,"complete":true,"checked_files":1,"findings":[]}',
            '{"version":1,"complete":true,"checked_files":0,"findings":null}',
            '{"version":1,"complete":true,"checked_files":0,"findings":[{}]}',
            '{"version":1,"complete":true,"checked_files":0,"findings":[{"code":"missing","file_index":9,"path":"x","detail":"","actual_checksum":""}]}',
        ],
    )
    def test_malformed_response(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
        payload: str,
    ) -> None:
        executable(tmp_path, settings, f"import sys\nsys.stdout.write({payload!r})")
        with pytest.raises(
            IntegrityScanError,
            match="Invalid integrity scanner response",
        ):
            scan_files(manifest)

    def test_crash(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
    ) -> None:
        executable(
            tmp_path,
            settings,
            "import sys\nsys.stderr.write('scanner crashed')\nsys.exit(7)",
        )
        with pytest.raises(IntegrityScanError, match=r"exit 7.*scanner crashed"):
            scan_files(manifest)

    def test_signal_failure(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
    ) -> None:
        executable(
            tmp_path,
            settings,
            "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)",
        )
        with pytest.raises(IntegrityScanError, match=f"exit {-signal.SIGTERM}"):
            scan_files(manifest)

    @pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
    def test_real_go_interrupts_blocked_stdin(
        self,
        settings: Settings,
        sig: signal.Signals,
    ) -> None:
        process = subprocess.Popen(
            [str(settings.INTEGRITY_SCANNER_BINARY)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assert process.stdin is not None
            process.stdin.write(b"{")
            process.stdin.flush()
            threading.Event().wait(0.2)
            process.send_signal(sig)
            assert process.wait(timeout=5) != 0
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_invalid_utf8(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
    ) -> None:
        executable(tmp_path, settings, "import sys\nsys.stdout.buffer.write(b'\\xff')")
        with pytest.raises(
            IntegrityScanError,
            match="Invalid integrity scanner response",
        ):
            scan_files(manifest)

    def test_incomplete_inventory(self, manifest: Manifest) -> None:
        manifest["media_root"] += "/missing"
        with pytest.raises(IntegrityScanError, match="scan incomplete"):
            scan_files(manifest)

    def test_invalid_manifest_rejected_by_go(self, manifest: Manifest) -> None:
        manifest["checksum_algorithm"] = "md5"
        with pytest.raises(
            IntegrityScanError,
            match="Invalid integrity scanner manifest",
        ):
            scan_files(manifest)

    def test_timeout_reaps_real_process(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
    ) -> None:
        pidfile = tmp_path / "pid"
        executable(
            tmp_path,
            settings,
            f"import os, time\nfrom pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(60)",
        )
        settings.INTEGRITY_SCANNER_TIMEOUT = 0.5
        with pytest.raises(IntegrityScanError, match="timed out"):
            scan_files(manifest)
        with pytest.raises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)

    def test_interrupt_terminates_process(
        self,
        manifest: Manifest,
        mocker: MockerFixture,
    ) -> None:
        process = mocker.Mock()
        process.communicate.side_effect = [KeyboardInterrupt, (b"", b"")]
        mocker.patch("documents.integrity.subprocess.Popen", return_value=process)
        with pytest.raises(KeyboardInterrupt):
            scan_files(manifest)
        process.terminate.assert_called_once()
        assert process.communicate.call_count == 2

    def test_uncooperative_child_is_killed(
        self,
        manifest: Manifest,
        mocker: MockerFixture,
    ) -> None:
        process = mocker.Mock()
        timeout = subprocess.TimeoutExpired("scanner", 1)
        process.communicate.side_effect = [timeout, timeout, (b"", b"")]
        mocker.patch("documents.integrity.subprocess.Popen", return_value=process)
        with pytest.raises(IntegrityScanError, match="timed out"):
            scan_files(manifest)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        assert process.communicate.call_count == 3

    def test_response_uses_manifest_file_identity(
        self,
        manifest: Manifest,
        tmp_path: Path,
        settings: Settings,
    ) -> None:
        manifest["files"] = [
            {"document_id": 1, "kind": "original", "path": "expected", "checksum": ""},
        ]
        payload = {
            "version": 1,
            "complete": True,
            "checked_files": 1,
            "findings": [
                {
                    "code": "missing",
                    "file_index": 0,
                    "path": "different",
                    "detail": "",
                    "actual_checksum": "",
                },
            ],
        }
        executable(
            tmp_path,
            settings,
            f"import sys\nsys.stdout.write({json.dumps(payload)!r})",
        )
        with pytest.raises(IntegrityScanError, match="does not match manifest"):
            scan_files(manifest)
