"""WebSocket consumers for migration operations."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from paperless_migration.services.importer import ImportService
from paperless_migration.services.transform import TransformService

logger = logging.getLogger(__name__)


class MigrationConsumerBase(AsyncWebsocketConsumer):
    """Base consumer with common authentication and messaging logic."""

    async def connect(self) -> None:
        """Authenticate and accept or reject the connection."""
        user = self.scope.get("user")
        session = self.scope.get("session", {})

        if not user or not user.is_authenticated:
            logger.warning("WebSocket connection rejected: not authenticated")
            await self.close(code=4001)
            return

        if not user.is_superuser:
            logger.warning("WebSocket connection rejected: not superuser")
            await self.close(code=4003)
            return

        if not session.get("migration_code_ok"):
            logger.warning("WebSocket connection rejected: migration code not verified")
            await self.close(code=4002)
            return

        await self.accept()
        logger.info("WebSocket connection accepted for user: %s", user.username)

    async def disconnect(self, close_code: int) -> None:
        """Handle disconnection."""
        logger.debug("WebSocket disconnected with code: %d", close_code)

    async def receive(self, text_data: str | None = None, **kwargs: Any) -> None:
        """Handle incoming messages - triggers the operation."""
        if text_data is None:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON message")
            return

        action = data.get("action")
        if action == "start":
            await self.run_operation()
        else:
            await self.send_error(f"Unknown action: {action}")

    async def run_operation(self) -> None:
        """Override in subclasses to run the specific operation."""
        raise NotImplementedError

    async def send_message(self, msg_type: str, **kwargs: Any) -> None:
        """Send a typed JSON message to the client."""
        await self.send(text_data=json.dumps({"type": msg_type, **kwargs}))

    async def send_log(self, message: str, level: str = "info") -> None:
        """Send a log message."""
        await self.send_message("log", message=message, level=level)

    async def send_progress(
        self,
        current: int,
        total: int | None = None,
        label: str = "",
    ) -> None:
        """Send a progress update."""
        await self.send_message(
            "progress",
            current=current,
            total=total,
            label=label,
        )

    async def send_stats(self, stats: dict[str, Any]) -> None:
        """Send statistics update."""
        await self.send_message("stats", **stats)

    async def send_complete(
        self,
        duration: float,
        *,
        success: bool,
        **kwargs: Any,
    ) -> None:
        """Send completion message."""
        await self.send_message(
            "complete",
            success=success,
            duration=duration,
            **kwargs,
        )

    async def send_error(self, message: str) -> None:
        """Send an error message."""
        await self.send_message("error", message=message)


class TransformConsumer(MigrationConsumerBase):
    """WebSocket consumer for transform operations."""

    async def run_operation(self) -> None:
        """Run the transform operation."""
        input_path = Path(settings.MIGRATION_EXPORT_PATH)
        output_path = Path(settings.MIGRATION_TRANSFORMED_PATH)
        frequency = settings.MIGRATION_PROGRESS_FREQUENCY

        if not input_path.exists():
            await self.send_error(f"Export file not found: {input_path}")
            return

        if output_path.exists():
            await self.send_error(
                f"Output file already exists: {output_path}. "
                "Delete it first to re-run transform.",
            )
            return

        await self.send_log("Starting transform operation...")

        service = TransformService(
            input_path=input_path,
            output_path=output_path,
            update_frequency=frequency,
        )

        try:
            async for update in service.run_async():
                match update["type"]:
                    case "progress":
                        await self.send_progress(
                            current=update["completed"],
                            label=f"{update['completed']:,} rows processed",
                        )
                        if update.get("stats"):
                            await self.send_stats({"transformed": update["stats"]})
                    case "complete":
                        await self.send_complete(
                            success=True,
                            duration=update["duration"],
                            total_processed=update["total_processed"],
                            stats=update["stats"],
                            speed=update["speed"],
                        )
                    case "error":
                        await self.send_error(update["message"])
                    case "log":
                        await self.send_log(
                            update["message"],
                            update.get("level", "info"),
                        )
        except Exception as exc:
            logger.exception("Transform operation failed")
            await self.send_error(f"Transform failed: {exc}")


class ImportConsumer(MigrationConsumerBase):
    """WebSocket consumer for import operations."""

    async def run_operation(self) -> None:
        """Run the import operation (wipe, migrate, import)."""
        export_path = Path(settings.MIGRATION_EXPORT_PATH)
        transformed_path = Path(settings.MIGRATION_TRANSFORMED_PATH)
        imported_marker = Path(settings.MIGRATION_IMPORTED_PATH)
        source_dir = export_path.parent

        if not export_path.exists():
            await self.send_error("Export file not found. Upload or re-check export.")
            return

        if not transformed_path.exists():
            await self.send_error("Transformed file not found. Run transform first.")
            return

        await self.send_log("Preparing import operation...")

        # Backup original manifest and swap in transformed version
        backup_path: Path | None = None
        try:
            backup_fd, backup_name = tempfile.mkstemp(
                prefix="manifest.v2.",
                suffix=".json",
                dir=source_dir,
            )
            os.close(backup_fd)
            backup_path = Path(backup_name)
            shutil.copy2(export_path, backup_path)
            shutil.copy2(transformed_path, export_path)
            await self.send_log("Manifest files prepared")
        except Exception as exc:
            await self.send_error(f"Failed to prepare import manifest: {exc}")
            return

        service = ImportService(
            source_dir=source_dir,
            imported_marker=imported_marker,
        )

        try:
            async for update in service.run_async():
                match update["type"]:
                    case "phase":
                        await self.send_log(f"Phase: {update['phase']}", level="info")
                    case "log":
                        await self.send_log(
                            update["message"],
                            update.get("level", "info"),
                        )
                    case "complete":
                        await self.send_complete(
                            success=update["success"],
                            duration=update["duration"],
                        )
                    case "error":
                        await self.send_error(update["message"])
        except Exception as exc:
            logger.exception("Import operation failed")
            await self.send_error(f"Import failed: {exc}")
        finally:
            # Restore original manifest
            if backup_path and backup_path.exists():
                try:
                    shutil.move(str(backup_path), str(export_path))
                except Exception as exc:
                    logger.warning("Failed to restore backup manifest: %s", exc)
