"""
Tests for the document consumer management command.

Tests are organized into classes by component:
- TestFileStabilityTracker: Unit tests for FileStabilityTracker
- TestConsumerFilter: Unit tests for ConsumerFilter
- TestConsumeFile: Unit tests for the _consume_file function
- TestTagsFromPath: Unit tests for _tags_from_path
- TestCommandValidation: Tests for command argument validation
- TestCommandOneshot: Tests for oneshot mode
- TestCommandWatch: Integration tests for the watch loop
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from threading import Thread
from time import monotonic
from time import sleep
from typing import TYPE_CHECKING

import pytest
from django import db
from django.core.management import CommandError
from django.db import DatabaseError
from django.test import override_settings
from watchfiles import Change

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.management.commands.document_consumer import Command
from documents.management.commands.document_consumer import ConsumerFilter
from documents.management.commands.document_consumer import FileStabilityTracker
from documents.management.commands.document_consumer import TrackedFile
from documents.management.commands.document_consumer import _consume_file
from documents.management.commands.document_consumer import _tags_from_path
from documents.models import Tag

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator
    from unittest.mock import MagicMock

    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture


@pytest.fixture
def stability_tracker() -> FileStabilityTracker:
    """Create a FileStabilityTracker with a short delay for testing."""
    return FileStabilityTracker(stability_delay=0.1)


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create a temporary file for testing."""
    file_path = tmp_path / "test_file.pdf"
    file_path.write_bytes(b"test content")
    return file_path


@pytest.fixture
def consumption_dir(tmp_path: Path) -> Path:
    """Create a temporary consumption directory for testing."""
    consume_dir = tmp_path / "consume"
    consume_dir.mkdir()
    return consume_dir


@pytest.fixture
def scratch_dir(tmp_path: Path) -> Path:
    """Create a temporary scratch directory for testing."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return scratch


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample PDF file."""
    pdf_content = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def consumer_filter() -> ConsumerFilter:
    """Create a ConsumerFilter for testing."""
    return ConsumerFilter(
        supported_extensions=frozenset({".pdf", ".png", ".jpg"}),
        ignore_patterns=[r"^custom_ignore"],
    )


@pytest.fixture
def mock_consume_file_delay(mocker: MockerFixture) -> MagicMock:
    """Mock the consume_file.delay celery task."""
    mock_task = mocker.patch(
        "documents.management.commands.document_consumer.consume_file",
    )
    mock_task.delay = mocker.MagicMock()
    return mock_task


@pytest.fixture
def mock_supported_extensions(mocker: MockerFixture) -> MagicMock:
    """Mock get_supported_file_extensions to return only .pdf."""
    return mocker.patch(
        "documents.management.commands.document_consumer.get_supported_file_extensions",
        return_value={".pdf"},
    )


def wait_for_mock_call(
    mock_obj: MagicMock,
    timeout_s: float = 5.0,
    poll_interval_s: float = 0.1,
) -> bool:
    """
    Actively wait for a mock to be called.

    Args:
        mock_obj: The mock object to check (e.g., mock.delay)
        timeout_s: Maximum time to wait in seconds
        poll_interval_s: How often to check in seconds

    Returns:
        True if mock was called within timeout, False otherwise
    """
    start_time = monotonic()
    while monotonic() - start_time < timeout_s:
        if mock_obj.called:
            return True
        sleep(poll_interval_s)
    return False


class TestTrackedFile:
    """Tests for the TrackedFile dataclass."""

    def test_update_stats_existing_file(self, temp_file: Path) -> None:
        """Test update_stats succeeds for existing file."""
        tracked = TrackedFile(path=temp_file, last_event_time=monotonic())
        assert tracked.update_stats() is True
        assert tracked.last_mtime is not None
        assert tracked.last_size is not None
        assert tracked.last_size == len(b"test content")

    def test_update_stats_nonexistent_file(self, tmp_path: Path) -> None:
        """Test update_stats fails for nonexistent file."""
        tracked = TrackedFile(
            path=tmp_path / "nonexistent.pdf",
            last_event_time=monotonic(),
        )
        assert tracked.update_stats() is False
        assert tracked.last_mtime is None
        assert tracked.last_size is None

    def test_is_unchanged_same_stats(self, temp_file: Path) -> None:
        """Test is_unchanged returns True when stats haven't changed."""
        tracked = TrackedFile(path=temp_file, last_event_time=monotonic())
        tracked.update_stats()
        assert tracked.is_unchanged() is True

    def test_is_unchanged_modified_file(self, temp_file: Path) -> None:
        """Test is_unchanged returns False when file is modified."""
        tracked = TrackedFile(path=temp_file, last_event_time=monotonic())
        tracked.update_stats()
        temp_file.write_bytes(b"modified content that is longer")
        assert tracked.is_unchanged() is False

    def test_is_unchanged_deleted_file(self, temp_file: Path) -> None:
        """Test is_unchanged returns False when file is deleted."""
        tracked = TrackedFile(path=temp_file, last_event_time=monotonic())
        tracked.update_stats()
        temp_file.unlink()
        assert tracked.is_unchanged() is False


class TestFileStabilityTracker:
    """Tests for the FileStabilityTracker class."""

    def test_track_new_file(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test tracking a new file adds it to pending."""
        stability_tracker.track(temp_file, Change.added)
        assert stability_tracker.pending_count == 1
        assert stability_tracker.has_pending_files() is True

    def test_track_modified_file(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test tracking a modified file updates its event time."""
        stability_tracker.track(temp_file, Change.added)
        sleep(0.05)
        stability_tracker.track(temp_file, Change.modified)
        assert stability_tracker.pending_count == 1

    def test_track_deleted_file(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test tracking a deleted file removes it from pending."""
        stability_tracker.track(temp_file, Change.added)
        assert stability_tracker.pending_count == 1
        stability_tracker.track(temp_file, Change.deleted)
        assert stability_tracker.pending_count == 0
        assert stability_tracker.has_pending_files() is False

    def test_track_nonexistent_file(
        self,
        stability_tracker: FileStabilityTracker,
        tmp_path: Path,
    ) -> None:
        """Test tracking a nonexistent file doesn't add it."""
        nonexistent = tmp_path / "nonexistent.pdf"
        stability_tracker.track(nonexistent, Change.added)
        assert stability_tracker.pending_count == 0

    def test_get_stable_files_before_delay(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test get_stable_files returns nothing before delay expires."""
        stability_tracker.track(temp_file, Change.added)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 0
        assert stability_tracker.pending_count == 1

    def test_get_stable_files_after_delay(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test get_stable_files returns file after delay expires."""
        stability_tracker.track(temp_file, Change.added)
        sleep(0.15)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 1
        assert stable[0] == temp_file
        assert stability_tracker.pending_count == 0

    def test_get_stable_files_modified_during_check(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test file is not returned if modified during stability check."""
        stability_tracker.track(temp_file, Change.added)
        sleep(0.12)
        temp_file.write_bytes(b"modified content")
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 0
        assert stability_tracker.pending_count == 1

    def test_get_stable_files_deleted_during_check(self, temp_file: Path) -> None:
        """Test deleted file is not returned during stability check."""
        tracker = FileStabilityTracker(stability_delay=0.1)
        tracker.track(temp_file, Change.added)
        sleep(0.12)
        temp_file.unlink()
        stable = list(tracker.get_stable_files())
        assert len(stable) == 0
        assert tracker.pending_count == 0

    def test_get_stable_files_error_during_check(
        self,
        temp_file: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test a file which has become inaccessible is removed from tracking"""

        mocker.patch.object(Path, "stat", side_effect=PermissionError("denied"))

        tracker = FileStabilityTracker(stability_delay=0.1)
        tracker.track(temp_file, Change.added)
        stable = list(tracker.get_stable_files())
        assert len(stable) == 0
        assert tracker.pending_count == 0

    def test_multiple_files_tracking(
        self,
        stability_tracker: FileStabilityTracker,
        tmp_path: Path,
    ) -> None:
        """Test tracking multiple files independently."""
        file1 = tmp_path / "file1.pdf"
        file2 = tmp_path / "file2.pdf"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")

        stability_tracker.track(file1, Change.added)
        sleep(0.05)
        stability_tracker.track(file2, Change.added)

        assert stability_tracker.pending_count == 2

        sleep(0.06)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 1
        assert stable[0] == file1

        sleep(0.06)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 1
        assert stable[0] == file2

    def test_track_resolves_path(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test that tracking resolves paths consistently."""
        stability_tracker.track(temp_file, Change.added)
        stability_tracker.track(temp_file.resolve(), Change.modified)
        assert stability_tracker.pending_count == 1


class TestConsumerFilter:
    """Tests for the ConsumerFilter class."""

    @pytest.mark.parametrize(
        ("filename", "should_accept"),
        [
            pytest.param("document.pdf", True, id="supported_pdf"),
            pytest.param("image.png", True, id="supported_png"),
            pytest.param("photo.jpg", True, id="supported_jpg"),
            pytest.param("document.PDF", True, id="case_insensitive"),
            pytest.param("document.xyz", False, id="unsupported_ext"),
            pytest.param("document", False, id="no_extension"),
            pytest.param(".DS_Store", False, id="ds_store"),
            pytest.param(".DS_STORE", False, id="ds_store_upper"),
            pytest.param("._document.pdf", False, id="macos_resource_fork"),
            pytest.param("._hidden", False, id="macos_resource_no_ext"),
            pytest.param("Thumbs.db", False, id="thumbs_db"),
            pytest.param("desktop.ini", False, id="desktop_ini"),
            pytest.param("custom_ignore_this.pdf", False, id="custom_pattern"),
            pytest.param("stfolder.pdf", True, id="similar_to_ignored"),
            pytest.param("my_document.pdf", True, id="normal_with_underscore"),
        ],
    )
    def test_file_filtering(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
        filename: str,
        should_accept: bool,  # noqa: FBT001
    ) -> None:
        """Test filter correctly accepts or rejects files."""
        test_file = tmp_path / filename
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is should_accept

    @pytest.mark.parametrize(
        ("dirname", "should_accept"),
        [
            pytest.param(".stfolder", False, id="syncthing_stfolder"),
            pytest.param(".stversions", False, id="syncthing_stversions"),
            pytest.param("@eaDir", False, id="synology_eadir"),
            pytest.param(".Spotlight-V100", False, id="macos_spotlight"),
            pytest.param(".Trashes", False, id="macos_trashes"),
            pytest.param("__MACOSX", False, id="macos_archive"),
            pytest.param(".localized", False, id="macos_localized"),
            pytest.param("documents", True, id="normal_dir"),
            pytest.param("invoices", True, id="normal_dir_2"),
        ],
    )
    def test_directory_filtering(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
        dirname: str,
        should_accept: bool,  # noqa: FBT001
    ) -> None:
        """Test filter correctly accepts or rejects directories."""
        test_dir = tmp_path / dirname
        test_dir.mkdir()
        assert consumer_filter(Change.added, str(test_dir)) is should_accept

    def test_default_patterns_are_valid_regex(self) -> None:
        """Test that default patterns are valid regex."""
        for pattern in ConsumerFilter.DEFAULT_IGNORE_PATTERNS:
            re.compile(pattern)

    def test_custom_ignore_dirs(self, tmp_path: Path) -> None:
        """Test filter respects custom ignore_dirs."""
        filter_obj = ConsumerFilter(
            supported_extensions=frozenset({".pdf"}),
            ignore_dirs=["custom_ignored_dir"],
        )

        # Custom ignored directory should be rejected
        custom_dir = tmp_path / "custom_ignored_dir"
        custom_dir.mkdir()
        assert filter_obj(Change.added, str(custom_dir)) is False

        # Normal directory should be accepted
        normal_dir = tmp_path / "normal_dir"
        normal_dir.mkdir()
        assert filter_obj(Change.added, str(normal_dir)) is True

        # Default ignored directories should still be ignored
        stfolder = tmp_path / ".stfolder"
        stfolder.mkdir()
        assert filter_obj(Change.added, str(stfolder)) is False


class TestConsumerFilterDefaults:
    """Tests for ConsumerFilter with default settings."""

    def test_filter_with_mocked_extensions(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test filter works when using mocked extensions from parser."""
        mocker.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf", ".png"},
        )
        filter_obj = ConsumerFilter()
        test_file = tmp_path / "document.pdf"
        test_file.touch()
        assert filter_obj(Change.added, str(test_file)) is True


class TestConsumeFile:
    """Tests for the _consume_file function."""

    def test_consume_queues_file(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
    ) -> None:
        """Test _consume_file queues a valid file."""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        _consume_file(
            filepath=target,
            consumption_dir=consumption_dir,
            subdirs_as_tags=False,
        )

        mock_consume_file_delay.delay.assert_called_once()
        call_args = mock_consume_file_delay.delay.call_args
        consumable_doc = call_args[0][0]
        assert isinstance(consumable_doc, ConsumableDocument)
        assert consumable_doc.original_file == target
        assert consumable_doc.source == DocumentSource.ConsumeFolder

    def test_consume_nonexistent_file(
        self,
        consumption_dir: Path,
        mock_consume_file_delay: MagicMock,
    ) -> None:
        """Test _consume_file handles nonexistent files gracefully."""
        _consume_file(
            filepath=consumption_dir / "nonexistent.pdf",
            consumption_dir=consumption_dir,
            subdirs_as_tags=False,
        )
        mock_consume_file_delay.delay.assert_not_called()

    def test_consume_directory(
        self,
        consumption_dir: Path,
        mock_consume_file_delay: MagicMock,
    ) -> None:
        """Test _consume_file ignores directories."""
        subdir = consumption_dir / "subdir"
        subdir.mkdir()

        _consume_file(
            filepath=subdir,
            consumption_dir=consumption_dir,
            subdirs_as_tags=False,
        )
        mock_consume_file_delay.delay.assert_not_called()

    def test_consume_with_permission_error(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Test _consume_file handles permission errors."""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        mocker.patch.object(Path, "is_file", side_effect=PermissionError("denied"))
        _consume_file(
            filepath=target,
            consumption_dir=consumption_dir,
            subdirs_as_tags=False,
        )
        mock_consume_file_delay.delay.assert_not_called()

    def test_consume_with_tags_error(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Test _consume_file handles errors during tag creation"""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        mocker.patch(
            "documents.management.commands.document_consumer._tags_from_path",
            side_effect=DatabaseError("Something happened"),
        )

        _consume_file(
            filepath=target,
            consumption_dir=consumption_dir,
            subdirs_as_tags=True,
        )
        mock_consume_file_delay.delay.assert_called_once()
        call_args = mock_consume_file_delay.delay.call_args
        overrides = call_args[0][1]
        assert overrides.tag_ids is None


@pytest.mark.django_db
class TestTagsFromPath:
    """Tests for the _tags_from_path function."""

    def test_creates_tags_from_subdirectories(self, consumption_dir: Path) -> None:
        """Test tags are created for each subdirectory."""
        subdir = consumption_dir / "Invoice" / "2024"
        subdir.mkdir(parents=True)
        target = subdir / "document.pdf"
        target.touch()

        tag_ids = _tags_from_path(target, consumption_dir)

        assert len(tag_ids) == 2
        assert Tag.objects.filter(name="Invoice").exists()
        assert Tag.objects.filter(name="2024").exists()

    def test_reuses_existing_tags(self, consumption_dir: Path) -> None:
        """Test existing tags are reused (case-insensitive)."""
        existing_tag = Tag.objects.create(name="existing")

        subdir = consumption_dir / "EXISTING"
        subdir.mkdir(parents=True)
        target = subdir / "document.pdf"
        target.touch()

        tag_ids = _tags_from_path(target, consumption_dir)

        assert len(tag_ids) == 1
        assert existing_tag.pk in tag_ids
        assert Tag.objects.filter(name__iexact="existing").count() == 1

    def test_no_tags_for_root_file(self, consumption_dir: Path) -> None:
        """Test no tags created for files directly in consumption dir."""
        target = consumption_dir / "document.pdf"
        target.touch()

        tag_ids = _tags_from_path(target, consumption_dir)

        assert len(tag_ids) == 0


class TestCommandValidation:
    """Tests for command argument validation."""

    def test_raises_for_missing_consumption_dir(
        self,
        settings: SettingsWrapper,
    ) -> None:
        """Test command raises error when directory is not provided."""
        settings.CONSUMPTION_DIR = None
        with pytest.raises(CommandError, match="not configured"):
            cmd = Command()
            cmd.handle(directory=None, oneshot=True, testing=False)

    def test_raises_for_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test command raises error for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(CommandError, match="does not exist"):
            cmd = Command()
            cmd.handle(directory=str(nonexistent), oneshot=True, testing=False)

    def test_raises_for_file_instead_of_directory(self, sample_pdf: Path) -> None:
        """Test command raises error when path is a file, not directory."""
        with pytest.raises(CommandError, match="not a directory"):
            cmd = Command()
            cmd.handle(directory=str(sample_pdf), oneshot=True, testing=False)


@pytest.mark.usefixtures("mock_supported_extensions")
class TestCommandOneshot:
    """Tests for oneshot mode."""

    def test_processes_existing_files(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        settings: SettingsWrapper,
    ) -> None:
        """Test oneshot mode processes existing files."""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        settings.SCRATCH_DIR = scratch_dir
        settings.CONSUMER_IGNORE_PATTERNS = []

        cmd = Command()
        cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_called_once()

    def test_processes_recursive(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        settings: SettingsWrapper,
    ) -> None:
        """Test oneshot mode processes files recursively."""
        subdir = consumption_dir / "subdir"
        subdir.mkdir()
        target = subdir / "document.pdf"
        shutil.copy(sample_pdf, target)

        settings.SCRATCH_DIR = scratch_dir
        settings.CONSUMER_RECURSIVE = True
        settings.CONSUMER_IGNORE_PATTERNS = []

        cmd = Command()
        cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_called_once()

    def test_ignores_unsupported_extensions(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        mock_consume_file_delay: MagicMock,
        settings: SettingsWrapper,
    ) -> None:
        """Test oneshot mode ignores unsupported file extensions."""
        target = consumption_dir / "document.xyz"
        target.write_bytes(b"content")

        settings.SCRATCH_DIR = scratch_dir
        settings.CONSUMER_IGNORE_PATTERNS = []

        cmd = Command()
        cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_not_called()


class ConsumerThread(Thread):
    """Thread wrapper for running the consumer command with proper cleanup."""

    def __init__(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        *,
        recursive: bool = False,
        subdirs_as_tags: bool = False,
        polling_interval: float = 0,
        stability_delay: float = 0.1,
    ) -> None:
        super().__init__()
        self.consumption_dir = consumption_dir
        self.scratch_dir = scratch_dir
        self.recursive = recursive
        self.subdirs_as_tags = subdirs_as_tags
        self.polling_interval = polling_interval
        self.stability_delay = stability_delay
        self.cmd = Command()
        self.cmd.stop_flag.clear()
        # Non-daemon ensures finally block runs and connections are closed
        self.daemon = False
        self.exception: Exception | None = None

    def run(self) -> None:
        try:
            # Use override_settings to avoid polluting global settings
            # which would affect other tests running on the same worker
            with override_settings(
                SCRATCH_DIR=self.scratch_dir,
                CONSUMER_RECURSIVE=self.recursive,
                CONSUMER_SUBDIRS_AS_TAGS=self.subdirs_as_tags,
                CONSUMER_POLLING_INTERVAL=self.polling_interval,
                CONSUMER_STABILITY_DELAY=self.stability_delay,
                CONSUMER_IGNORE_PATTERNS=[],
            ):
                self.cmd.handle(
                    directory=str(self.consumption_dir),
                    oneshot=False,
                    testing=True,
                )
        except Exception as e:
            self.exception = e
        finally:
            # Close database connections created in this thread
            db.connections.close_all()

    def stop(self) -> None:
        self.cmd.stop_flag.set()

    def stop_and_wait(self, timeout: float = 5.0) -> None:
        """Stop the thread and wait for it to finish, with cleanup."""
        self.stop()
        self.join(timeout=timeout)
        if self.is_alive():
            # Thread didn't stop in time - this is a test failure
            raise RuntimeError(
                f"Consumer thread did not stop within {timeout}s timeout",
            )


@pytest.fixture
def start_consumer(
    consumption_dir: Path,
    scratch_dir: Path,
    mock_supported_extensions: MagicMock,
) -> Generator[Callable[..., ConsumerThread], None, None]:
    """Start a consumer thread and ensure cleanup."""
    threads: list[ConsumerThread] = []

    def _start(**kwargs) -> ConsumerThread:
        thread = ConsumerThread(consumption_dir, scratch_dir, **kwargs)
        threads.append(thread)
        thread.start()
        sleep(2.0)  # Give thread time to start
        return thread

    try:
        yield _start
    finally:
        # Cleanup all threads that were started
        for thread in threads:
            thread.stop_and_wait()

        failed_threads = []
        for thread in threads:
            thread.join(timeout=5.0)
            if thread.is_alive():
                failed_threads.append(thread)

        # Clean up any Tags created by threads (they bypass test transaction isolation)
        Tag.objects.all().delete()

        db.connections.close_all()

        if failed_threads:
            pytest.fail(
                f"{len(failed_threads)} consumer thread(s) did not stop within timeout",
            )


@pytest.mark.django_db
class TestCommandWatch:
    """Integration tests for the watch loop."""

    def test_detects_new_file(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test watch mode detects and consumes new files."""
        thread = start_consumer()

        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    def test_detects_moved_file(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test watch mode detects moved/renamed files."""
        temp_location = scratch_dir / "temp.pdf"
        shutil.copy(sample_pdf, temp_location)

        thread = start_consumer()

        sleep(0.5)

        target = consumption_dir / "document.pdf"
        shutil.move(temp_location, target)

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    def test_handles_slow_write(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test watch mode waits for slow writes to complete."""
        pdf_bytes = sample_pdf.read_bytes()

        thread = start_consumer(stability_delay=0.2)

        target = consumption_dir / "document.pdf"
        with target.open("wb") as f:
            for i in range(0, len(pdf_bytes), 100):
                f.write(pdf_bytes[i : i + 100])
                f.flush()
                sleep(0.05)

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    def test_ignores_macos_files(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test watch mode ignores macOS system files."""
        thread = start_consumer()

        (consumption_dir / ".DS_Store").write_bytes(b"test")
        (consumption_dir / "._document.pdf").write_bytes(b"test")
        shutil.copy(sample_pdf, consumption_dir / "valid.pdf")

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        assert mock_consume_file_delay.delay.call_count == 1
        call_args = mock_consume_file_delay.delay.call_args[0][0]
        assert call_args.original_file.name == "valid.pdf"

    @pytest.mark.django_db
    @pytest.mark.usefixtures("mock_supported_extensions")
    def test_stop_flag_stops_consumer(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        mock_consume_file_delay: MagicMock,
    ) -> None:
        """Test stop flag properly stops the consumer."""
        thread = ConsumerThread(consumption_dir, scratch_dir)
        try:
            thread.start()
            sleep(0.3)
            assert thread.is_alive()
        finally:
            thread.stop_and_wait(timeout=5.0)
            # Clean up any Tags created by the thread
            Tag.objects.all().delete()

        assert not thread.is_alive()


@pytest.mark.django_db
class TestCommandWatchPolling:
    """Tests for polling mode."""

    def test_polling_mode_works(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """
        Test polling mode detects files.

        Uses active waiting with timeout to handle CI delays and polling timing.
        """
        # Use shorter polling interval for faster test
        thread = start_consumer(polling_interval=0.5, stability_delay=0.1)

        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        # Actively wait for consumption
        # Polling needs: interval (0.5s) + stability (0.1s) + next poll (0.5s) + margin
        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=5.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()


@pytest.mark.django_db
class TestCommandWatchRecursive:
    """Tests for recursive watching."""

    def test_recursive_detects_nested_files(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test recursive mode detects files in subdirectories."""
        subdir = consumption_dir / "level1" / "level2"
        subdir.mkdir(parents=True)

        thread = start_consumer(recursive=True)

        target = subdir / "document.pdf"
        shutil.copy(sample_pdf, target)

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    def test_subdirs_as_tags(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
        mocker: MockerFixture,
    ) -> None:
        """Test subdirs_as_tags creates tags from directory names."""
        # Mock _tags_from_path to avoid database operations in the consumer thread
        mock_tags = mocker.patch(
            "documents.management.commands.document_consumer._tags_from_path",
            return_value=[1, 2],
        )

        subdir = consumption_dir / "Invoices" / "2024"
        subdir.mkdir(parents=True)

        thread = start_consumer(recursive=True, subdirs_as_tags=True)

        target = subdir / "document.pdf"
        shutil.copy(sample_pdf, target)

        wait_for_mock_call(mock_consume_file_delay.delay, timeout_s=2.0)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_called()
        mock_tags.assert_called()
        call_args = mock_consume_file_delay.delay.call_args
        overrides = call_args[0][1]
        assert overrides.tag_ids is not None
        assert len(overrides.tag_ids) == 2


@pytest.mark.django_db
class TestCommandWatchEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_deleted_before_stable(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay: MagicMock,
        start_consumer: Callable[..., ConsumerThread],
    ) -> None:
        """Test handles files deleted before becoming stable."""
        thread = start_consumer(stability_delay=0.3)

        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)
        sleep(0.1)
        target.unlink()

        sleep(0.5)

        if thread.exception:
            raise thread.exception

        mock_consume_file_delay.delay.assert_not_called()

    @pytest.mark.usefixtures("mock_supported_extensions")
    def test_handles_task_exception(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test handles exceptions from consume task gracefully."""
        mock_task = mocker.patch(
            "documents.management.commands.document_consumer.consume_file",
        )
        mock_task.delay.side_effect = Exception("Task error")

        thread = ConsumerThread(consumption_dir, scratch_dir)
        try:
            thread.start()
            sleep(0.3)

            target = consumption_dir / "document.pdf"
            shutil.copy(sample_pdf, target)
            sleep(0.5)

            # Consumer should still be running despite the exception
            assert thread.is_alive()
        finally:
            thread.stop_and_wait(timeout=5.0)
            # Clean up any Tags created by the thread
            Tag.objects.all().delete()
