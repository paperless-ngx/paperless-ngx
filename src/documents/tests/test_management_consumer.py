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
from unittest import mock

import pytest
from django.core.management import CommandError
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

# -- Fixtures --


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
    # Use a minimal valid-ish PDF header
    pdf_content = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def consumer_filter() -> ConsumerFilter:
    """Create a ConsumerFilter for testing."""
    return ConsumerFilter(
        supported_extensions=frozenset({".pdf", ".png", ".jpg"}),
        ignore_patterns=[r"^custom_ignore.*"],
    )


@pytest.fixture
def mock_consume_file_delay():
    """Mock the consume_file.delay celery task."""
    with mock.patch(
        "documents.management.commands.document_consumer.consume_file",
    ) as mock_task:
        mock_task.delay = mock.MagicMock()
        yield mock_task


# -- TrackedFile Tests --


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

        # Modify the file
        temp_file.write_bytes(b"modified content that is longer")

        assert tracked.is_unchanged() is False

    def test_is_unchanged_deleted_file(self, temp_file: Path) -> None:
        """Test is_unchanged returns False when file is deleted."""
        tracked = TrackedFile(path=temp_file, last_event_time=monotonic())
        tracked.update_stats()
        temp_file.unlink()
        assert tracked.is_unchanged() is False


# -- FileStabilityTracker Tests --


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

        # File should still be pending, not yet stable
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
        sleep(0.15)  # Wait longer than stability_delay (0.1s)

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

        # Modify file just before checking
        temp_file.write_bytes(b"modified content")

        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 0
        # File should be re-tracked with new event time
        assert stability_tracker.pending_count == 1

    def test_get_stable_files_deleted_during_check(
        self,
        temp_file: Path,
    ) -> None:
        """Test deleted file is not returned during stability check."""
        tracker = FileStabilityTracker(stability_delay=0.1)
        tracker.track(temp_file, Change.added)
        sleep(0.12)

        # Delete file just before checking
        temp_file.unlink()

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

        # Wait for file1 to be stable (but not file2)
        sleep(0.06)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 1
        assert stable[0] == file1

        # Now wait for file2
        sleep(0.06)
        stable = list(stability_tracker.get_stable_files())
        assert len(stable) == 1
        assert stable[0] == file2

    def test_clear(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test clear removes all tracked files."""
        stability_tracker.track(temp_file, Change.added)
        assert stability_tracker.pending_count == 1

        stability_tracker.clear()
        assert stability_tracker.pending_count == 0
        assert stability_tracker.has_pending_files() is False

    def test_track_resolves_path(
        self,
        stability_tracker: FileStabilityTracker,
        temp_file: Path,
    ) -> None:
        """Test that tracking resolves paths consistently."""
        # Track with relative-looking path
        stability_tracker.track(temp_file, Change.added)

        # Track again with resolved path - should update, not add
        stability_tracker.track(temp_file.resolve(), Change.modified)

        assert stability_tracker.pending_count == 1


# -- ConsumerFilter Tests --


class TestConsumerFilter:
    """Tests for the ConsumerFilter class."""

    def test_accepts_supported_extension(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter accepts files with supported extensions."""
        test_file = tmp_path / "document.pdf"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is True

    def test_rejects_unsupported_extension(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects files with unsupported extensions."""
        test_file = tmp_path / "document.xyz"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_rejects_no_extension(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects files without extensions."""
        test_file = tmp_path / "document"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_case_insensitive_extension(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter handles extensions case-insensitively."""
        test_file = tmp_path / "document.PDF"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is True

    def test_rejects_ds_store(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects .DS_Store files."""
        test_file = tmp_path / ".DS_Store"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_rejects_macos_resource_fork(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects macOS resource fork files (._*)."""
        test_file = tmp_path / "._document.pdf"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_rejects_syncthing_folder(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects .stfolder directory via ignore_dirs."""
        stfolder = tmp_path / ".stfolder"
        stfolder.mkdir()
        # DefaultFilter ignores directories by name
        assert consumer_filter(Change.added, str(stfolder)) is False

    def test_rejects_syncthing_versions(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects .stversions directory via ignore_dirs."""
        stversions = tmp_path / ".stversions"
        stversions.mkdir()
        assert consumer_filter(Change.added, str(stversions)) is False

    def test_rejects_synology_eadir(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects Synology @eaDir directory via ignore_dirs."""
        eadir = tmp_path / "@eaDir"
        eadir.mkdir()
        assert consumer_filter(Change.added, str(eadir)) is False

    def test_rejects_thumbs_db(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects Thumbs.db."""
        test_file = tmp_path / "Thumbs.db"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_rejects_desktop_ini(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter rejects desktop.ini."""
        test_file = tmp_path / "desktop.ini"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_custom_ignore_pattern(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter respects custom ignore patterns."""
        test_file = tmp_path / "custom_ignore_this.pdf"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is False

    def test_accepts_similar_to_ignored(
        self,
        consumer_filter: ConsumerFilter,
        tmp_path: Path,
    ) -> None:
        """Test filter accepts files similar to but not matching ignore patterns."""
        test_file = tmp_path / "stfolder.pdf"
        test_file.touch()
        assert consumer_filter(Change.added, str(test_file)) is True

    def test_default_patterns_are_regex(self) -> None:
        """Test that default patterns are valid regex."""
        for pattern in ConsumerFilter.DEFAULT_IGNORE_PATTERNS:
            # Should not raise
            re.compile(pattern)


class TestConsumerFilterWithoutExtensions:
    """Tests for ConsumerFilter edge cases."""

    def test_filter_works_with_default_extensions(self, tmp_path: Path) -> None:
        """Test filter works when using default extensions."""
        # This would use get_supported_file_extensions() in real usage
        filter_obj = ConsumerFilter(
            supported_extensions=frozenset({".pdf"}),
        )
        test_file = tmp_path / "document.pdf"
        test_file.touch()
        assert filter_obj(Change.added, str(test_file)) is True

    def test_ignores_patterns_by_filename(self, tmp_path: Path) -> None:
        """Test filter ignores patterns matched against filename only."""
        filter_obj = ConsumerFilter(
            supported_extensions=frozenset({".pdf"}),
        )
        test_file = tmp_path / ".DS_Store"
        test_file.touch()
        assert filter_obj(Change.added, str(test_file)) is False


# -- _consume_file Tests --


class TestConsumeFile:
    """Tests for the _consume_file function."""

    @pytest.mark.django_db
    def test_consume_queues_file(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
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

    @pytest.mark.django_db
    def test_consume_nonexistent_file(
        self,
        consumption_dir: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test _consume_file handles nonexistent files gracefully."""
        _consume_file(
            filepath=consumption_dir / "nonexistent.pdf",
            consumption_dir=consumption_dir,
            subdirs_as_tags=False,
        )

        mock_consume_file_delay.delay.assert_not_called()

    @pytest.mark.django_db
    def test_consume_directory(
        self,
        consumption_dir: Path,
        mock_consume_file_delay,
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

    @pytest.mark.django_db
    def test_consume_with_permission_error(
        self,
        consumption_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test _consume_file handles permission errors."""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        with mock.patch.object(Path, "is_file", side_effect=PermissionError("denied")):
            _consume_file(
                filepath=target,
                consumption_dir=consumption_dir,
                subdirs_as_tags=False,
            )

        mock_consume_file_delay.delay.assert_not_called()


# -- _tags_from_path Tests --


class TestTagsFromPath:
    """Tests for the _tags_from_path function."""

    @pytest.mark.django_db
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

    @pytest.mark.django_db
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
        # Should not create a duplicate
        assert Tag.objects.filter(name__iexact="existing").count() == 1

    @pytest.mark.django_db
    def test_no_tags_for_root_file(self, consumption_dir: Path) -> None:
        """Test no tags created for files directly in consumption dir."""
        target = consumption_dir / "document.pdf"
        target.touch()

        tag_ids = _tags_from_path(target, consumption_dir)

        assert len(tag_ids) == 0


# -- Command Validation Tests --


class TestCommandValidation:
    """Tests for command argument validation."""

    def test_raises_for_missing_consumption_dir(self) -> None:
        """Test command raises error when directory is not provided and setting is unset."""
        with override_settings(CONSUMPTION_DIR=None):
            with pytest.raises(CommandError, match="not configured"):
                cmd = Command()
                cmd.handle(directory=None, oneshot=True, testing=False)

    def test_raises_for_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test command raises error for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(CommandError, match="does not exist"):
            cmd = Command()
            cmd.handle(directory=str(nonexistent), oneshot=True, testing=False)

    def test_raises_for_file_instead_of_directory(
        self,
        sample_pdf: Path,
    ) -> None:
        """Test command raises error when path is a file, not directory."""
        with pytest.raises(CommandError, match="not a directory"):
            cmd = Command()
            cmd.handle(directory=str(sample_pdf), oneshot=True, testing=False)


# -- Command Oneshot Tests --


class TestCommandOneshot:
    """Tests for oneshot mode."""

    @pytest.mark.django_db
    def test_processes_existing_files(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test oneshot mode processes existing files."""
        target = consumption_dir / "document.pdf"
        shutil.copy(sample_pdf, target)

        with (
            override_settings(SCRATCH_DIR=scratch_dir),
            mock.patch(
                "documents.management.commands.document_consumer.get_supported_file_extensions",
                return_value={".pdf"},
            ),
        ):
            cmd = Command()
            cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_called_once()

    @pytest.mark.django_db
    def test_processes_recursive(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test oneshot mode processes files recursively."""
        subdir = consumption_dir / "subdir"
        subdir.mkdir()
        target = subdir / "document.pdf"
        shutil.copy(sample_pdf, target)

        with (
            override_settings(SCRATCH_DIR=scratch_dir, CONSUMER_RECURSIVE=True),
            mock.patch(
                "documents.management.commands.document_consumer.get_supported_file_extensions",
                return_value={".pdf"},
            ),
        ):
            cmd = Command()
            cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_called_once()

    @pytest.mark.django_db
    def test_ignores_unsupported_extensions(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test oneshot mode ignores unsupported file extensions."""
        target = consumption_dir / "document.xyz"
        target.write_bytes(b"content")

        with (
            override_settings(SCRATCH_DIR=scratch_dir),
            mock.patch(
                "documents.management.commands.document_consumer.get_supported_file_extensions",
                return_value={".pdf"},
            ),
        ):
            cmd = Command()
            cmd.handle(directory=str(consumption_dir), oneshot=True, testing=False)

        mock_consume_file_delay.delay.assert_not_called()


# -- Command Watch Tests --


class ConsumerThread(Thread):
    """Thread wrapper for running the consumer command."""

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
        self.daemon = True
        self.exception: Exception | None = None

    def run(self) -> None:
        try:
            # Apply settings overrides within the thread
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

    def stop(self) -> None:
        self.cmd.stop_flag.set()


class TestCommandWatch:
    """Integration tests for the watch loop."""

    @pytest.mark.django_db
    def test_detects_new_file(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test watch mode detects and consumes new files."""
        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(consumption_dir, scratch_dir)
            thread.start()

            # Give thread time to start watching
            sleep(0.5)

            # Copy file
            target = consumption_dir / "document.pdf"
            shutil.copy(sample_pdf, target)

            # Wait for stability delay + processing
            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    @pytest.mark.django_db
    def test_detects_moved_file(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test watch mode detects moved/renamed files."""
        # Create temp file outside consumption dir
        temp_location = scratch_dir / "temp.pdf"
        shutil.copy(sample_pdf, temp_location)

        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(consumption_dir, scratch_dir)
            thread.start()

            sleep(0.5)

            # Move file into consumption dir
            target = consumption_dir / "document.pdf"
            shutil.move(temp_location, target)

            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    @pytest.mark.django_db
    def test_handles_slow_write(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test watch mode waits for slow writes to complete."""
        pdf_bytes = sample_pdf.read_bytes()

        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(
                consumption_dir,
                scratch_dir,
                stability_delay=0.2,
            )
            thread.start()

            sleep(0.5)

            # Simulate slow write
            target = consumption_dir / "document.pdf"
            with target.open("wb") as f:
                for i in range(0, len(pdf_bytes), 100):
                    f.write(pdf_bytes[i : i + 100])
                    f.flush()
                    sleep(0.05)

            # Wait for stability
            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    @pytest.mark.django_db
    def test_ignores_macos_files(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test watch mode ignores macOS system files."""
        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(consumption_dir, scratch_dir)
            thread.start()

            sleep(0.5)

            # Create macOS files
            (consumption_dir / ".DS_Store").write_bytes(b"test")
            (consumption_dir / "._document.pdf").write_bytes(b"test")

            # Also create a valid file to confirm filtering works
            shutil.copy(sample_pdf, consumption_dir / "valid.pdf")

            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        # Should only consume the valid file
        assert mock_consume_file_delay.delay.call_count == 1
        call_args = mock_consume_file_delay.delay.call_args[0][0]
        assert call_args.original_file.name == "valid.pdf"

    @pytest.mark.django_db
    def test_stop_flag_stops_consumer(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test stop flag properly stops the consumer."""
        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(consumption_dir, scratch_dir)
            thread.start()

            sleep(0.3)
            assert thread.is_alive()

            thread.stop()
            thread.join(timeout=2.0)

            assert not thread.is_alive()


class TestCommandWatchPolling:
    """Tests for polling mode."""

    @pytest.mark.django_db
    def test_polling_mode_works(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test polling mode detects files."""
        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(
                consumption_dir,
                scratch_dir,
                polling_interval=0.5,  # Enable polling
            )
            thread.start()

            sleep(0.5)

            target = consumption_dir / "document.pdf"
            shutil.copy(sample_pdf, target)

            # Polling needs more time
            sleep(1.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()


class TestCommandWatchRecursive:
    """Tests for recursive watching."""

    @pytest.mark.django_db
    def test_recursive_detects_nested_files(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test recursive mode detects files in subdirectories."""
        subdir = consumption_dir / "level1" / "level2"
        subdir.mkdir(parents=True)

        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(
                consumption_dir,
                scratch_dir,
                recursive=True,
            )
            thread.start()

            sleep(0.5)

            target = subdir / "document.pdf"
            shutil.copy(sample_pdf, target)

            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()

    @pytest.mark.django_db
    def test_subdirs_as_tags(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test subdirs_as_tags creates tags from directory names."""
        subdir = consumption_dir / "Invoices" / "2024"
        subdir.mkdir(parents=True)

        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(
                consumption_dir,
                scratch_dir,
                recursive=True,
                subdirs_as_tags=True,
            )
            thread.start()

            sleep(0.5)

            target = subdir / "document.pdf"
            shutil.copy(sample_pdf, target)

            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        mock_consume_file_delay.delay.assert_called()
        # Check tags were passed
        call_args = mock_consume_file_delay.delay.call_args
        overrides = call_args[0][1]
        assert overrides.tag_ids is not None
        assert len(overrides.tag_ids) == 2


class TestCommandWatchEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.django_db
    def test_handles_deleted_before_stable(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
        mock_consume_file_delay,
    ) -> None:
        """Test handles files deleted before becoming stable."""
        with mock.patch(
            "documents.management.commands.document_consumer.get_supported_file_extensions",
            return_value={".pdf"},
        ):
            thread = ConsumerThread(
                consumption_dir,
                scratch_dir,
                stability_delay=0.3,  # Longer delay
            )
            thread.start()

            sleep(0.3)

            # Create and quickly delete
            target = consumption_dir / "document.pdf"
            shutil.copy(sample_pdf, target)
            sleep(0.1)  # Before stability delay
            target.unlink()

            sleep(0.5)

            thread.stop()
            thread.join(timeout=2.0)

            if thread.exception:
                raise thread.exception

        # Should not have consumed the deleted file
        mock_consume_file_delay.delay.assert_not_called()

    @pytest.mark.django_db
    def test_handles_task_exception(
        self,
        consumption_dir: Path,
        scratch_dir: Path,
        sample_pdf: Path,
    ) -> None:
        """Test handles exceptions from consume task gracefully."""
        with (
            mock.patch(
                "documents.management.commands.document_consumer.consume_file",
            ) as mock_task,
            mock.patch(
                "documents.management.commands.document_consumer.get_supported_file_extensions",
                return_value={".pdf"},
            ),
        ):
            mock_task.delay.side_effect = Exception("Task error")

            thread = ConsumerThread(consumption_dir, scratch_dir)
            thread.start()

            sleep(0.3)

            target = consumption_dir / "document.pdf"
            shutil.copy(sample_pdf, target)

            sleep(0.5)

            # Consumer should still be running despite the exception
            assert thread.is_alive()

            thread.stop()
            thread.join(timeout=2.0)
