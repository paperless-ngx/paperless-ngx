"""Logical PostgreSQL backup to disk (pull-by-path producer contract).

Writes ``paperless-YYYY-MM-DD.dump`` (custom format) and ``paperless-YYYY-MM-DD.version``
under a configurable directory. See sibling extension docs / operator BACKUP-INTERFACE.
"""

from __future__ import annotations

import os
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from paperless import version

if TYPE_CHECKING:
    from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = (
        "Create a PostgreSQL database dump (pg_dump -Fc) for disaster recovery. "
        "Outputs paperless-YYYY-MM-DD.dump and .version under the backup directory."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output-dir",
            type=Path,
            default=None,
            help=(
                "Directory for dump files. "
                "Default: PAPERLESS_BACKUP_DIR if set, else DATA_DIR/backups."
            ),
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=None,
            help=(
                "Delete backup pairs (*.dump + *.version) older than this many days "
                "in the output directory. Default: no retention cleanup."
            ),
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip pg_restore --list check (not recommended for automation).",
        )

    def handle(self, *args, **options) -> None:
        db = settings.DATABASES["default"]
        engine = db["ENGINE"]
        if engine != "django.db.backends.postgresql":
            raise CommandError(
                "backup_db supports only PostgreSQL in this version; "
                f"configured engine is {engine!r}.",
            )

        out_dir: Path = options["output_dir"]
        if out_dir is None:
            env_dir = os.getenv("PAPERLESS_BACKUP_DIR")
            out_dir = Path(env_dir) if env_dir else Path(settings.DATA_DIR) / "backups"
        out_dir = out_dir.expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        date_str = timezone.localdate().isoformat()
        dump_path = out_dir / f"paperless-{date_str}.dump"
        version_path = out_dir / f"paperless-{date_str}.version"

        name = str(db["NAME"])
        user = str(db["USER"])
        password = str(db.get("PASSWORD") or "")
        host = db.get("HOST") or ""
        port = db.get("PORT")
        if port is not None and port != "":
            port = str(port)

        env = os.environ.copy()
        env["PGPASSWORD"] = password

        cmd: list[str] = ["pg_dump", "-U", user]
        if host:
            cmd.extend(["-h", host])
        if port:
            cmd.extend(["-p", port])
        cmd.extend(["-Fc", "-f", str(dump_path), name])

        self.stdout.write(f"Creating dump {dump_path} ...")
        try:
            completed = subprocess.run(
                cmd,
                env=env,
                check=False,
                capture_output=True,
            )
        except OSError as exc:  # e.g. pg_dump not found
            dump_path.unlink(missing_ok=True)
            raise CommandError(f"Could not run pg_dump: {exc}") from exc

        if completed.returncode != 0:
            dump_path.unlink(missing_ok=True)
            err = (completed.stderr or b"").decode(errors="replace")
            raise CommandError(f"pg_dump failed (exit {completed.returncode}): {err}")

        version_path.write_text(
            f"{version.__full_version_str__}\n",
            encoding="utf-8",
        )

        if not options["skip_validation"]:
            vcmd = ["pg_restore", "--list", str(dump_path)]
            try:
                vcompleted = subprocess.run(
                    vcmd,
                    check=False,
                    capture_output=True,
                )
            except OSError as exc:
                dump_path.unlink(missing_ok=True)
                version_path.unlink(missing_ok=True)
                raise CommandError(f"Could not run pg_restore: {exc}") from exc

            if vcompleted.returncode != 0:
                err = (vcompleted.stderr or b"").decode(errors="replace")
                dump_path.unlink(missing_ok=True)
                version_path.unlink(missing_ok=True)
                raise CommandError(f"Dump validation failed: {err}")

        self.stdout.write(self.style.SUCCESS(f"Backup complete: {dump_path.name}"))

        retention: int | None = options["retention_days"]
        if retention is not None and retention > 0:
            self._apply_retention(out_dir, retention)

    def _apply_retention(self, out_dir: Path, retention_days: int) -> None:
        cutoff_ts = (timezone.now() - timedelta(days=retention_days)).timestamp()
        removed = 0
        for dump in sorted(out_dir.glob("paperless-*.dump")):
            try:
                if dump.stat().st_mtime >= cutoff_ts:
                    continue
            except OSError:
                continue
            dump.unlink(missing_ok=True)
            ver = dump.with_name(f"{dump.stem}.version")
            ver.unlink(missing_ok=True)
            removed += 1
        if removed:
            self.stdout.write(f"Retention removed {removed} backup pair(s).")

