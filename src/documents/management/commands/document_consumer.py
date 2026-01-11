"""
Document consumer management command.

Watches a consumption directory for new documents and queues them for processing.
Uses watchfiles for efficient file system monitoring with support for both
native OS notifications and polling fallback.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import monotonic
from typing import TYPE_CHECKING
from typing import Final

from django import db
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from watchfiles import Change
from watchfiles import DefaultFilter
from watchfiles import watch

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Tag
from documents.parsers import get_supported_file_extensions
from documents.tasks import consume_file

if TYPE_CHECKING:
    from collections.abc import Iterator


logger = logging.getLogger("paperless.management.consumer")


@dataclass
class TrackedFile:
    """Represents a file being tracked for stability."""

    path: Path
    last_event_time: float
    last_mtime: float | None = None
    last_size: int | None = None

    def update_stats(self) -> bool:
        """
        Update file stats. Returns True if file exists and stats were updated.
        """
        try:
            stat = self.path.stat()
            self.last_mtime = stat.st_mtime
            self.last_size = stat.st_size
            return True
        except (FileNotFoundError, PermissionError):
            return False

    def is_unchanged(self) -> bool:
        """
        Check if file stats match the previously recorded values.
        Returns False if file doesn't exist or stats changed.
        """
        try:
            stat = self.path.stat()
            return stat.st_mtime == self.last_mtime and stat.st_size == self.last_size
        except (FileNotFoundError, PermissionError):
            return False


class FileStabilityTracker:
    """
    Tracks file events and determines when files are stable for consumption.

    A file is considered stable when:
    1. No new events have been received for it within the stability delay
    2. Its size and modification time haven't changed
    3. It still exists as a regular file

    This handles various edge cases:
    - Network copies that write in chunks
    - Scanners that open/close files multiple times
    - Temporary files that get renamed
    - Files that are deleted before becoming stable
    """

    def __init__(self, stability_delay: float = 1.0) -> None:
        """
        Initialize the tracker.

        Args:
            stability_delay: Time in seconds a file must remain unchanged
                           before being considered stable.
        """
        self.stability_delay = stability_delay
        self._tracked: dict[Path, TrackedFile] = {}

    def track(self, path: Path, change: Change) -> None:
        """
        Register a file event.

        Args:
            path: The file path that changed.
            change: The type of change (added, modified, deleted).
        """
        path = path.resolve()

        match change:
            case Change.deleted:
                self._tracked.pop(path, None)
                logger.debug(f"Stopped tracking deleted file: {path}")
            case Change.added | Change.modified:
                current_time = monotonic()
                if path in self._tracked:
                    tracked = self._tracked[path]
                    tracked.last_event_time = current_time
                    tracked.update_stats()
                    logger.debug(f"Updated tracking for: {path}")
                else:
                    tracked = TrackedFile(path=path, last_event_time=current_time)
                    if tracked.update_stats():
                        self._tracked[path] = tracked
                        logger.debug(f"Started tracking: {path}")
                    else:
                        logger.debug(f"Could not stat file, not tracking: {path}")

    def get_stable_files(self) -> Iterator[Path]:
        """
        Yield files that have been stable for the configured delay.

        Files are removed from tracking once yielded or determined to be invalid.
        """
        current_time = monotonic()
        to_remove: list[Path] = []
        to_yield: list[Path] = []

        for path, tracked in self._tracked.items():
            time_since_event = current_time - tracked.last_event_time

            if time_since_event < self.stability_delay:
                continue

            # File has waited long enough, verify it's unchanged
            if not tracked.is_unchanged():
                # Stats changed or file gone - update and wait again
                if tracked.update_stats():
                    tracked.last_event_time = current_time
                    logger.debug(f"File changed during stability check: {path}")
                else:
                    # File no longer exists, remove from tracking
                    to_remove.append(path)
                    logger.debug(f"File disappeared during stability check: {path}")
                continue

            # File is stable - verify it's a regular file
            try:
                if path.is_file():
                    to_yield.append(path)
                    logger.info(f"File is stable: {path}")
                else:
                    # Not a regular file (directory, symlink, etc.)
                    to_remove.append(path)
                    logger.debug(f"Path is not a regular file: {path}")
            except (PermissionError, FileNotFoundError) as e:
                logger.warning(f"Cannot access {path}: {e}")
                to_remove.append(path)

        # Remove files that are no longer valid
        for path in to_remove:
            self._tracked.pop(path, None)

        # Remove and yield stable files
        for path in to_yield:
            self._tracked.pop(path, None)
            yield path

    def has_pending_files(self) -> bool:
        """Check if there are files waiting for stability check."""
        return len(self._tracked) > 0

    def clear(self) -> None:
        """Clear all tracked files."""
        self._tracked.clear()

    @property
    def pending_count(self) -> int:
        """Number of files being tracked."""
        return len(self._tracked)


class ConsumerFilter(DefaultFilter):
    """
    Custom filter for the document consumer.

    Filters files based on:
    - Supported file extensions
    - User-configured ignore patterns (regex)
    - Default ignore patterns for common system files
    """

    # Default regex patterns to ignore (matched against filename only)
    DEFAULT_IGNORE_PATTERNS: Final[frozenset[str]] = frozenset(
        {
            r"^\.DS_Store$",
            r"^\.DS_STORE$",
            r"^\._.*",
            r"^desktop\.ini$",
            r"^Thumbs\.db$",
        },
    )

    # Directories to always ignore (matched by name via DefaultFilter)
    DEFAULT_IGNORE_DIRS: Final[tuple[str, ...]] = (
        ".stfolder",
        ".stversions",
        ".localized",
        "@eaDir",
        ".Spotlight-V100",
        ".Trashes",
        "__MACOSX",
    )

    def __init__(
        self,
        *,
        supported_extensions: frozenset[str] | None = None,
        ignore_patterns: list[str] | None = None,
        consumption_dir: Path | None = None,
    ) -> None:
        """
        Initialize the consumer filter.

        Args:
            supported_extensions: Set of supported file extensions (e.g., {".pdf", ".png"}).
                                If None, uses get_supported_file_extensions().
            ignore_patterns: Additional regex patterns to ignore (matched against filename).
            consumption_dir: Base consumption directory (unused, kept for API compatibility).
        """
        # Combine default and user patterns
        all_patterns = set(self.DEFAULT_IGNORE_PATTERNS)
        if ignore_patterns:
            all_patterns.update(ignore_patterns)

        # Compile all patterns
        self._ignore_regexes: list[re.Pattern[str]] = [
            re.compile(pattern) for pattern in all_patterns
        ]

        # Get supported extensions
        if supported_extensions is None:
            supported_extensions = frozenset(get_supported_file_extensions())
        self._supported_extensions = supported_extensions

        # Call parent with directory ignore list
        # DefaultFilter.ignore_dirs matches directory names, not full paths
        super().__init__(
            ignore_dirs=self.DEFAULT_IGNORE_DIRS,
            ignore_entity_patterns=None,
            ignore_paths=None,
        )

    def __call__(self, change: Change, path: str) -> bool:
        """
        Filter function for watchfiles.

        Returns True if the path should be watched, False to ignore.
        """
        # Let parent filter handle directory ignoring and basic checks
        if not super().__call__(change, path):
            return False

        path_obj = Path(path)

        # For directories, parent filter already handled ignore_dirs
        if path_obj.is_dir():
            return True

        # For files, check extension
        if not self._has_supported_extension(path_obj):
            return False

        # Check filename against ignore patterns
        return not self._matches_ignore_pattern(path_obj.name)

    def _has_supported_extension(self, path: Path) -> bool:
        """Check if the file has a supported extension."""
        suffix = path.suffix.lower()
        return suffix in self._supported_extensions

    def _matches_ignore_pattern(self, filename: str) -> bool:
        """Check if the filename matches any ignore pattern."""
        for regex in self._ignore_regexes:
            if regex.match(filename):
                logger.debug(
                    f"Filename {filename} matched ignore pattern {regex.pattern}",
                )
                return True
        return False


def _tags_from_path(filepath: Path, consumption_dir: Path) -> list[int]:
    """
    Walk up the directory tree from filepath to consumption_dir
    and get or create Tag IDs for every directory.

    Returns list of Tag primary keys.
    """
    db.close_old_connections()
    tag_ids: set[int] = set()
    path_parts = filepath.relative_to(consumption_dir).parent.parts

    for part in path_parts:
        tag, _ = Tag.objects.get_or_create(
            name__iexact=part,
            defaults={"name": part},
        )
        tag_ids.add(tag.pk)

    return list(tag_ids)


def _consume_file(
    filepath: Path,
    consumption_dir: Path,
    *,
    subdirs_as_tags: bool,
) -> None:
    """
    Queue a file for consumption.

    Args:
        filepath: Path to the file to consume.
        consumption_dir: Base consumption directory.
        subdirs_as_tags: Whether to create tags from subdirectory names.
    """
    # Verify file still exists and is accessible
    try:
        if not filepath.is_file():
            logger.debug(f"Not consuming {filepath}: not a file or doesn't exist")
            return
    except (PermissionError, FileNotFoundError) as e:
        logger.warning(f"Not consuming {filepath}: {e}")
        return

    # Get tags from path if configured
    tag_ids: list[int] | None = None
    if subdirs_as_tags:
        try:
            tag_ids = _tags_from_path(filepath, consumption_dir)
        except Exception:  # pragma: nocover
            logger.exception(f"Error creating tags from path for {filepath}")

    # Queue for consumption
    try:
        logger.info(f"Adding {filepath} to the task queue")
        consume_file.delay(
            ConsumableDocument(
                source=DocumentSource.ConsumeFolder,
                original_file=filepath,
            ),
            DocumentMetadataOverrides(tag_ids=tag_ids),
        )
    except Exception:
        logger.exception(f"Error while queuing document {filepath}")


class Command(BaseCommand):
    """
    Watch a consumption directory and queue new documents for processing.

    Uses watchfiles for efficient file system monitoring. Supports both
    native OS notifications (inotify on Linux, FSEvents on macOS) and
    polling for network filesystems.
    """

    help = "Watch the consumption directory for new documents"

    # For testing - allows tests to stop the consumer
    stop_flag: Event = Event()

    # Testing timeout in seconds
    testing_timeout_s: Final[float] = 0.5

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "directory",
            default=None,
            nargs="?",
            help="The consumption directory (defaults to CONSUMPTION_DIR setting)",
        )
        parser.add_argument(
            "--oneshot",
            action="store_true",
            help="Process existing files and exit without watching",
        )
        parser.add_argument(
            "--testing",
            action="store_true",
            help="Enable testing mode with shorter timeouts",
            default=False,
        )

    def handle(self, *args, **options) -> None:
        # Resolve consumption directory
        directory = options.get("directory")
        if not directory:
            directory = settings.CONSUMPTION_DIR
        if not directory:
            raise CommandError("CONSUMPTION_DIR is not configured")

        directory = Path(directory).resolve()

        if not directory.exists():
            raise CommandError(f"Consumption directory does not exist: {directory}")

        if not directory.is_dir():
            raise CommandError(f"Consumption path is not a directory: {directory}")

        # Ensure scratch directory exists
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        # Get settings
        recursive: bool = settings.CONSUMER_RECURSIVE
        subdirs_as_tags: bool = settings.CONSUMER_SUBDIRS_AS_TAGS
        polling_interval: float = settings.CONSUMER_POLLING_INTERVAL
        stability_delay: float = settings.CONSUMER_STABILITY_DELAY
        ignore_patterns: list[str] = settings.CONSUMER_IGNORE_PATTERNS
        is_testing: bool = options.get("testing", False)
        is_oneshot: bool = options.get("oneshot", False)

        # Create filter
        consumer_filter = ConsumerFilter(
            ignore_patterns=ignore_patterns,
            consumption_dir=directory,
        )

        # Process existing files
        self._process_existing_files(
            directory=directory,
            recursive=recursive,
            subdirs_as_tags=subdirs_as_tags,
            consumer_filter=consumer_filter,
        )

        if is_oneshot:
            logger.info("Oneshot mode: processed existing files, exiting")
            return

        # Start watching
        self._watch_directory(
            directory=directory,
            recursive=recursive,
            subdirs_as_tags=subdirs_as_tags,
            consumer_filter=consumer_filter,
            polling_interval=polling_interval,
            stability_delay=stability_delay,
            is_testing=is_testing,
        )

        logger.debug("Consumer exiting")

    def _process_existing_files(
        self,
        *,
        directory: Path,
        recursive: bool,
        subdirs_as_tags: bool,
        consumer_filter: ConsumerFilter,
    ) -> None:
        """Process any existing files in the consumption directory."""
        logger.info(f"Processing existing files in {directory}")

        glob_pattern = "**/*" if recursive else "*"

        for filepath in directory.glob(glob_pattern):
            # Use filter to check if file should be processed
            if not filepath.is_file():
                continue

            if not consumer_filter(Change.added, str(filepath)):
                continue

            _consume_file(
                filepath=filepath,
                consumption_dir=directory,
                subdirs_as_tags=subdirs_as_tags,
            )

    def _watch_directory(
        self,
        *,
        directory: Path,
        recursive: bool,
        subdirs_as_tags: bool,
        consumer_filter: ConsumerFilter,
        polling_interval: float,
        stability_delay: float,
        is_testing: bool,
    ) -> None:
        """Watch directory for changes and process stable files."""
        use_polling = polling_interval > 0
        poll_delay_ms = int(polling_interval * 1000) if use_polling else 0

        if use_polling:
            logger.info(
                f"Watching {directory} using polling (interval: {polling_interval}s)",
            )
        else:
            logger.info(f"Watching {directory} using native file system events")

        # Create stability tracker
        tracker = FileStabilityTracker(stability_delay=stability_delay)

        # Calculate timeouts
        stability_timeout_ms = int(stability_delay * 1000)
        testing_timeout_ms = int(self.testing_timeout_s * 1000)

        # Start with no timeout (wait indefinitely for first event)
        # unless in testing mode
        timeout_ms = testing_timeout_ms if is_testing else 0

        self.stop_flag.clear()

        while not self.stop_flag.is_set():
            try:
                for changes in watch(
                    directory,
                    watch_filter=consumer_filter,
                    rust_timeout=timeout_ms,
                    yield_on_timeout=True,
                    force_polling=use_polling,
                    poll_delay_ms=poll_delay_ms,
                    recursive=recursive,
                    stop_event=self.stop_flag,
                ):
                    # Process each change
                    for change_type, path in changes:
                        path = Path(path).resolve()
                        logger.debug(f"Event: {change_type.name} for {path}")
                        tracker.track(path, change_type)

                    # Check for stable files
                    for stable_path in tracker.get_stable_files():
                        _consume_file(
                            filepath=stable_path,
                            consumption_dir=directory,
                            subdirs_as_tags=subdirs_as_tags,
                        )

                    # Exit watch loop to reconfigure timeout
                    break

                # Determine next timeout
                if tracker.has_pending_files():
                    # Check pending files at stability interval
                    timeout_ms = stability_timeout_ms
                elif is_testing:
                    # In testing, use short timeout to check stop flag
                    timeout_ms = testing_timeout_ms
                else:  # pragma: nocover
                    # No pending files, wait indefinitely
                    timeout_ms = 0

            except KeyboardInterrupt:  # pragma: nocover
                logger.info("Received interrupt, stopping consumer")
                self.stop_flag.set()
