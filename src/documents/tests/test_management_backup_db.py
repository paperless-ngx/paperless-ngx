import shutil
import tempfile
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin


@pytest.mark.management
class TestBackupDb(DirectoriesMixin, TestCase):
    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
        },
    )
    def test_rejects_non_postgresql(self) -> None:
        with self.assertRaises(CommandError) as cm:
            call_command("backup_db", skip_checks=True)
        self.assertIn("backup_db supports only PostgreSQL", str(cm.exception))

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "paperless",
                "USER": "paperless",
                "PASSWORD": "secret",
                "HOST": "db",
                "PORT": "5432",
            },
        },
    )
    def test_happy_path_invokes_pg_dump_and_pg_restore(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        backup_root = tmp / "backups"

        def fake_run(cmd: list[str], **kwargs):  # noqa: ANN003
            binary = cmd[0]
            if binary == "pg_dump":
                out = Path(cmd[cmd.index("-f") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"fake-dump")
                return CompletedProcess(cmd, 0, b"", b"")
            if binary == "pg_restore":
                return CompletedProcess(cmd, 0, b"", b"")
            return CompletedProcess(cmd, 1, b"", b"unknown")

        out = StringIO()
        with mock.patch("documents.management.commands.backup_db.subprocess.run", fake_run):
            with mock.patch(
                "documents.management.commands.backup_db.timezone.localdate",
                return_value=__import__("datetime").date(2099, 1, 1),
            ):
                call_command(
                    "backup_db",
                    "--output-dir",
                    str(backup_root),
                    stdout=out,
                    stderr=StringIO(),
                    skip_checks=True,
                )

        written = backup_root / "paperless-2099-01-01.dump"
        ver = backup_root / "paperless-2099-01-01.version"
        self.assertTrue(written.is_file())
        self.assertTrue(ver.is_file())
        self.assertIn("Backup complete", out.getvalue())

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "paperless",
                "USER": "u",
                "PASSWORD": "p",
                "HOST": "",
                "PORT": "",
            },
        },
    )
    def test_pg_dump_failure_removes_partial(self) -> None:
        def fake_run(cmd: list[str], **kwargs):  # noqa: ANN003
            if cmd[0] == "pg_dump":
                out = Path(cmd[cmd.index("-f") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"partial")
                return CompletedProcess(cmd, 1, b"", b"pg_dump: error")
            return CompletedProcess(cmd, 0, b"", b"")

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        backup_root = tmp / "bk"
        with mock.patch("documents.management.commands.backup_db.subprocess.run", fake_run):
            with mock.patch(
                "documents.management.commands.backup_db.timezone.localdate",
                return_value=__import__("datetime").date(2099, 6, 15),
            ):
                with self.assertRaises(CommandError):
                    call_command(
                        "backup_db",
                        "--output-dir",
                        str(backup_root),
                        stdout=StringIO(),
                        stderr=StringIO(),
                        skip_checks=True,
                    )

        self.assertEqual(list(backup_root.glob("paperless-*.dump")), [])
