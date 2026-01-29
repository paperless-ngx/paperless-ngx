"""Import service for loading transformed data into v3 database."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import TypedDict

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from collections.abc import Generator


class ProgressUpdate(TypedDict, total=False):
    """Progress update message structure."""

    type: str
    phase: str
    message: str
    level: str
    success: bool
    duration: float
    return_code: int


@dataclass
class ImportService:
    """Service for importing transformed data into v3 database.

    This service orchestrates the three-phase import process:
    1. Wipe the existing database
    2. Run Django migrations for v3 schema
    3. Import the transformed data
    """

    source_dir: Path
    imported_marker: Path
    manage_path: Path | None = None

    def __post_init__(self) -> None:
        if self.manage_path is None:
            # Default to manage.py in the src directory
            self.manage_path = (
                Path(__file__).resolve().parent.parent.parent / "manage.py"
            )

    def _get_env(self) -> dict[str, str]:
        """Get environment variables for subprocess calls."""
        import os

        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "paperless.settings"
        env["PAPERLESS_MIGRATION_MODE"] = "0"
        return env

    def _run_command(
        self,
        args: list[str],
        label: str,
    ) -> Generator[ProgressUpdate, None, int]:
        """Run a command and yield log lines. Returns the return code."""
        yield {"type": "log", "message": f"Running: {label}", "level": "info"}

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=self._get_env(),
        )

        try:
            if process.stdout:
                for line in process.stdout:
                    yield {
                        "type": "log",
                        "message": line.rstrip(),
                        "level": "info",
                    }
            process.wait()
            return process.returncode
        finally:
            if process.poll() is None:
                process.kill()

    def run_sync(self) -> Generator[ProgressUpdate, None, None]:
        """Run the import synchronously, yielding progress updates.

        This orchestrates:
        1. Database wipe
        2. Django migrations
        3. Document import
        """
        start_time = time.perf_counter()

        # Phase 1: Wipe database
        yield {"type": "phase", "phase": "wipe"}
        wipe_cmd = [
            sys.executable,
            "-m",
            "paperless_migration.services.wipe_db",
        ]
        wipe_code = yield from self._run_command(wipe_cmd, "Database wipe")

        if wipe_code != 0:
            yield {
                "type": "error",
                "message": f"Database wipe failed with code {wipe_code}",
            }
            return

        yield {"type": "log", "message": "Database wipe complete", "level": "info"}

        # Phase 2: Run migrations
        yield {"type": "phase", "phase": "migrate"}
        migrate_cmd = [
            sys.executable,
            str(self.manage_path),
            "migrate",
            "--noinput",
        ]
        migrate_code = yield from self._run_command(migrate_cmd, "Django migrations")

        if migrate_code != 0:
            yield {
                "type": "error",
                "message": f"Migrations failed with code {migrate_code}",
            }
            return

        yield {"type": "log", "message": "Migrations complete", "level": "info"}

        # Phase 3: Import data
        yield {"type": "phase", "phase": "import"}
        import_cmd = [
            sys.executable,
            str(self.manage_path),
            "document_importer",
            str(self.source_dir),
            "--data-only",
        ]
        import_code = yield from self._run_command(import_cmd, "Document import")

        if import_code != 0:
            yield {
                "type": "error",
                "message": f"Import failed with code {import_code}",
            }
            return

        # Mark import as complete
        try:
            self.imported_marker.parent.mkdir(parents=True, exist_ok=True)
            self.imported_marker.write_text("ok\n", encoding="utf-8")
        except Exception as exc:
            yield {
                "type": "log",
                "message": f"Warning: Could not write import marker: {exc}",
                "level": "warning",
            }

        end_time = time.perf_counter()
        duration = end_time - start_time

        yield {
            "type": "complete",
            "success": True,
            "duration": duration,
        }

    async def run_async(self) -> AsyncGenerator[ProgressUpdate, None]:
        """Run the import asynchronously, yielding progress updates.

        This wraps the synchronous implementation to work with async consumers.
        """
        import asyncio

        for update in self.run_sync():
            yield update
            # Yield control to the event loop
            await asyncio.sleep(0)
