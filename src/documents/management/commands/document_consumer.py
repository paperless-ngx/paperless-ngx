"""
Document consumer management command.

Watches a consumption directory for new documents and queues them for processing.
Uses watchfiles for efficient file system monitoring with support for both
native OS notifications and polling fallback.
"""

from __future__ import annotations

import logging
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
        except OSError:
            return False

    def is_unchanged(self) -> bool:
        """
        Check if file stats match the previously recorded values.
        Returns False if file doesn't exist or stats changed.
        """
        try:
            stat = self.path.stat()
            return stat.st_mtime == self.last_mtime and stat.st_size == self.last_size
        except OSError:
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

            # File is stable, we can return it
            to_yield.append(path)
            logger.info(f"File is stable: {path}")

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

    @property
    def pending_count(self) -> int:
        """Number of files being tracked."""
        return len(self._tracked)


class ConsumerFilter(DefaultFilter):
    """
    Filter for watchfiles that accepts only supported document types
    and ignores system files/directories.

    Extends DefaultFilter leveraging its built-in filtering:
    - `ignore_dirs`: Directory names to ignore (and all their contents)
    - `ignore_entity_patterns`: Regex patterns matched against filename/dirname only

    We add custom logic for file extension filtering (only accept supported
    document types), which the library doesn't provide.
    """

    # Regex patterns for files to always ignore (matched against filename only)
    # These are passed to DefaultFilter.ignore_entity_patterns
    DEFAULT_IGNORE_PATTERNS: Final[tuple[str, ...]] = (
        r"^\.DS_Store$",
        r"^\.DS_STORE$",
        r"^\._.*",
        r"^desktop\.ini$",
        r"^Thumbs\.db$",
    )

    # Directories to always ignore (passed to DefaultFilter.ignore_dirs)
    # These are matched by directory name, not full path
    DEFAULT_IGNORE_DIRS: Final[tuple[str, ...]] = (
        ".stfolder",  # Syncthing
        ".stversions",  # Syncthing
        ".localized",  # macOS
        "@eaDir",  # Synology NAS
        ".Spotlight-V100",  # macOS
        ".Trashes",  # macOS
        "__MACOSX",  # macOS archive artifacts
    )

    def __init__(
        self,
        *,
        supported_extensions: frozenset[str] | None = None,
        ignore_patterns: list[str] | None = None,
        ignore_dirs: list[str] | None = None,
    ) -> None:
        """
        Initialize the consumer filter.

        Args:
            supported_extensions: Set of file extensions to accept (e.g., {".pdf", ".png"}).
                If None, uses get_supported_file_extensions().
            ignore_patterns: Additional regex patterns to ignore (matched against filename).
            ignore_dirs: Additional directory names to ignore (merged with defaults).
        """
        # Get supported extensions
        if supported_extensions is None:
            supported_extensions = frozenset(get_supported_file_extensions())
        self._supported_extensions = supported_extensions

        # Combine default and user patterns
        all_patterns: list[str] = list(self.DEFAULT_IGNORE_PATTERNS)
        if ignore_patterns:
            all_patterns.extend(ignore_patterns)

        # Combine default and user ignore_dirs
        all_ignore_dirs: list[str] = list(self.DEFAULT_IGNORE_DIRS)
        if ignore_dirs:
            all_ignore_dirs.extend(ignore_dirs)

        # Let DefaultFilter handle all the pattern and directory filtering
        super().__init__(
            ignore_dirs=tuple(all_ignore_dirs),
            ignore_entity_patterns=tuple(all_patterns),
            ignore_paths=(),
        )

    def __call__(self, change: Change, path: str) -> bool:
        """
        Filter function for watchfiles.

        Returns True if the path should be watched, False to ignore.

        The parent DefaultFilter handles:
        - Hidden files/directories (starting with .)
        - Directories in ignore_dirs
        - Files/directories matching ignore_entity_patterns

        We additionally filter files by extension.
        """
        # Let parent filter handle directory ignoring and pattern matching
        if not super().__call__(change, path):
            return False

        path_obj = Path(path)

        # For directories, parent filter already handled everything
        if path_obj.is_dir():
            return True

        # For files, check extension
        return self._has_supported_extension(path_obj)

    def _has_supported_extension(self, path: Path) -> bool:
        """Check if the file has a supported extension."""
        suffix = path.suffix.lower()
        return suffix in self._supported_extensions


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
    except OSError as e:
        logger.warning(f"Not consuming {filepath}: {e}")
        return

    # Get tags from path if configured
    tag_ids: list[int] | None = None
    if subdirs_as_tags:
        try:
            tag_ids = _tags_from_path(filepath, consumption_dir)
        except Exception:
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
            directory = getattr(settings, "CONSUMPTION_DIR", None)
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
        ignore_dirs: list[str] = settings.CONSUMER_IGNORE_DIRS
        is_testing: bool = options.get("testing", False)
        is_oneshot: bool = options.get("oneshot", False)

        # Create filter
        consumer_filter = ConsumerFilter(
            ignore_patterns=ignore_patterns,
            ignore_dirs=ignore_dirs,
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

        # Calculate appropriate timeout for watch loop
        # In polling mode, rust_timeout must be significantly longer than poll_delay_ms
        # to ensure poll cycles can complete before timing out
        if is_testing:
            if use_polling:
                # For polling: timeout must be at least 3x the poll interval to allow
                # multiple poll cycles. This prevents timeouts from interfering with
                # the polling mechanism.
                min_polling_timeout_ms = poll_delay_ms * 3
                timeout_ms = max(min_polling_timeout_ms, testing_timeout_ms)
            else:
                # For native watching, use short timeout to check stop flag
                timeout_ms = testing_timeout_ms
        else:
            # Not testing, wait indefinitely for first event
            timeout_ms = 0

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
                        if not path.is_file():
                            continue
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
                    # In testing, use appropriate timeout based on watch mode
                    if use_polling:
                        # For polling: ensure timeout allows polls to complete
                        min_polling_timeout_ms = poll_delay_ms * 3
                        timeout_ms = max(min_polling_timeout_ms, testing_timeout_ms)
                    else:
                        # For native watching, use short timeout to check stop flag
                        timeout_ms = testing_timeout_ms
                else:  # pragma: nocover
                    # No pending files, wait indefinitely
                    timeout_ms = 0

            except KeyboardInterrupt:  # pragma: nocover
                logger.info("Received interrupt, stopping consumer")
                self.stop_flag.set()
