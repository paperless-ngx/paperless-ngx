"""Tests for the sanity checker module.

Tests exercise ``check_sanity`` as a whole, verifying document validation,
orphan detection, task recording, and the iter_wrapper contract.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from documents.models import Document
from documents.models import PaperlessTask
from documents.sanity_checker import check_sanity

if TYPE_CHECKING:
    from collections.abc import Iterable

    from documents.tests.conftest import PaperlessDirs


@pytest.mark.django_db
class TestCheckSanityNoDocuments:
    """Sanity checks against an empty archive."""

    @pytest.mark.usefixtures("_media_settings")
    def test_no_documents(self) -> None:
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning
        assert len(messages) == 0

    @pytest.mark.usefixtures("_media_settings")
    def test_no_issues_logs_clean(self, caplog: pytest.LogCaptureFixture) -> None:
        messages = check_sanity()
        with caplog.at_level(logging.INFO, logger="paperless.sanity_checker"):
            messages.log_messages()
        assert "Sanity checker detected no issues." in caplog.text


@pytest.mark.django_db
class TestCheckSanityHealthyDocument:
    def test_no_errors(self, sample_doc: Document) -> None:
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning
        assert len(messages) == 0


@pytest.mark.django_db
class TestCheckSanityThumbnail:
    def test_missing(self, sample_doc: Document) -> None:
        Path(sample_doc.thumbnail_path).unlink()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "Thumbnail of document does not exist" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_unreadable(self, sample_doc: Document) -> None:
        thumb = Path(sample_doc.thumbnail_path)
        thumb.chmod(0o000)
        try:
            messages = check_sanity()
            assert messages.has_error
            assert any(
                "Cannot read thumbnail" in m["message"] for m in messages[sample_doc.pk]
            )
        finally:
            thumb.chmod(0o644)


@pytest.mark.django_db
class TestCheckSanityOriginal:
    def test_missing(self, sample_doc: Document) -> None:
        Path(sample_doc.source_path).unlink()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "Original of document does not exist" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_checksum_mismatch(self, sample_doc: Document) -> None:
        sample_doc.checksum = "badhash"
        sample_doc.save()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "Checksum mismatch" in m["message"] and "badhash" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_unreadable(self, sample_doc: Document) -> None:
        src = Path(sample_doc.source_path)
        src.chmod(0o000)
        try:
            messages = check_sanity()
            assert messages.has_error
            assert any(
                "Cannot read original" in m["message"] for m in messages[sample_doc.pk]
            )
        finally:
            src.chmod(0o644)


@pytest.mark.django_db
class TestCheckSanityArchive:
    def test_checksum_without_filename(self, sample_doc: Document) -> None:
        sample_doc.archive_filename = None
        sample_doc.save()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "checksum, but no archive filename" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_filename_without_checksum(self, sample_doc: Document) -> None:
        sample_doc.archive_checksum = None
        sample_doc.save()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "checksum is missing" in m["message"] for m in messages[sample_doc.pk]
        )

    def test_missing_file(self, sample_doc: Document) -> None:
        Path(sample_doc.archive_path).unlink()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "Archived version of document does not exist" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_checksum_mismatch(self, sample_doc: Document) -> None:
        sample_doc.archive_checksum = "wronghash"
        sample_doc.save()
        messages = check_sanity()
        assert messages.has_error
        assert any(
            "Checksum mismatch of archived document" in m["message"]
            for m in messages[sample_doc.pk]
        )

    def test_unreadable(self, sample_doc: Document) -> None:
        archive = Path(sample_doc.archive_path)
        archive.chmod(0o000)
        try:
            messages = check_sanity()
            assert messages.has_error
            assert any(
                "Cannot read archive" in m["message"] for m in messages[sample_doc.pk]
            )
        finally:
            archive.chmod(0o644)

    def test_no_archive_at_all(self, sample_doc: Document) -> None:
        """Document with neither archive checksum nor filename is valid."""
        Path(sample_doc.archive_path).unlink()
        sample_doc.archive_checksum = None
        sample_doc.archive_filename = None
        sample_doc.save()
        messages = check_sanity()
        assert not messages.has_error


@pytest.mark.django_db
class TestCheckSanityContent:
    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("", id="empty-string"),
        ],
    )
    def test_no_content(self, sample_doc: Document, content: str) -> None:
        sample_doc.content = content
        sample_doc.save()
        messages = check_sanity()
        assert not messages.has_error
        assert not messages.has_warning
        assert any("no OCR data" in m["message"] for m in messages[sample_doc.pk])


@pytest.mark.django_db
class TestCheckSanityOrphans:
    def test_orphaned_file(
        self,
        sample_doc: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        (paperless_dirs.originals / "orphan.pdf").touch()
        messages = check_sanity()
        assert messages.has_warning
        assert any("Orphaned file" in m["message"] for m in messages[None])

    @pytest.mark.usefixtures("_media_settings")
    def test_ignorable_files_not_flagged(
        self,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        (paperless_dirs.media / ".DS_Store").touch()
        (paperless_dirs.media / "desktop.ini").touch()
        messages = check_sanity()
        assert not messages.has_warning


@pytest.mark.django_db
class TestCheckSanityIterWrapper:
    def test_wrapper_receives_documents(self, sample_doc: Document) -> None:
        seen: list[Document] = []

        def tracking(iterable: Iterable[Document]) -> Iterable[Document]:
            for item in iterable:
                seen.append(item)
                yield item

        check_sanity(iter_wrapper=tracking)
        assert len(seen) == 1
        assert seen[0].pk == sample_doc.pk

    def test_default_works_without_wrapper(self, sample_doc: Document) -> None:
        messages = check_sanity()
        assert not messages.has_error


@pytest.mark.django_db
class TestCheckSanityTaskRecording:
    @pytest.mark.parametrize(
        ("expected_type", "scheduled"),
        [
            pytest.param(PaperlessTask.TaskType.SCHEDULED_TASK, True, id="scheduled"),
            pytest.param(PaperlessTask.TaskType.MANUAL_TASK, False, id="manual"),
        ],
    )
    @pytest.mark.usefixtures("_media_settings")
    def test_task_type(self, expected_type: str, *, scheduled: bool) -> None:
        check_sanity(scheduled=scheduled)
        task = PaperlessTask.objects.latest("date_created")
        assert task.task_name == PaperlessTask.TaskName.CHECK_SANITY
        assert task.type == expected_type

    def test_success_status(self, sample_doc: Document) -> None:
        check_sanity()
        task = PaperlessTask.objects.latest("date_created")
        assert task.status == "SUCCESS"

    def test_failure_status(self, sample_doc: Document) -> None:
        Path(sample_doc.source_path).unlink()
        check_sanity()
        task = PaperlessTask.objects.latest("date_created")
        assert task.status == "FAILURE"
        assert "Check logs for details" in task.result


@pytest.mark.django_db
class TestCheckSanityLogMessages:
    def test_logs_doc_issues(
        self,
        sample_doc: Document,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        Path(sample_doc.source_path).unlink()
        messages = check_sanity()
        with caplog.at_level(logging.INFO, logger="paperless.sanity_checker"):
            messages.log_messages()
        assert f"document #{sample_doc.pk}" in caplog.text
        assert "Original of document does not exist" in caplog.text

    def test_logs_global_issues(
        self,
        sample_doc: Document,
        paperless_dirs: PaperlessDirs,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        (paperless_dirs.originals / "orphan.pdf").touch()
        messages = check_sanity()
        with caplog.at_level(logging.WARNING, logger="paperless.sanity_checker"):
            messages.log_messages()
        assert "Orphaned file" in caplog.text

    @pytest.mark.usefixtures("_media_settings")
    def test_logs_unknown_doc_pk(self, caplog: pytest.LogCaptureFixture) -> None:
        """A doc PK not in the DB logs 'Unknown' as the title."""
        messages = check_sanity()
        messages.error(99999, "Ghost document")
        with caplog.at_level(logging.INFO, logger="paperless.sanity_checker"):
            messages.log_messages()
        assert "#99999" in caplog.text
        assert "Unknown" in caplog.text
