from __future__ import annotations

import datetime
import hashlib
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from celery.contrib.django.task import DjangoTask
from django.db import DatabaseError
from django.db import transaction
from django.http import HttpRequest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from filelock import Timeout
from rest_framework import status

from documents.file_moves import _active_collector
from documents.file_moves import _path_matches_checksum
from documents.file_moves import adefer_file_moves
from documents.file_moves import defer_file_moves
from documents.file_moves import flush_pending_file_moves
from documents.file_moves import move_files_for_document
from documents.file_moves import request_file_move
from documents.models import CustomField
from documents.models import Document
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.tasks import bulk_update_documents
from documents.tasks import check_scheduled_workflows
from documents.tasks import empty_trash
from paperless.celery import app as celery_app
from paperless.middleware import FileMoveMiddleware
from paperless_testing.factories import CorrespondentFactory
from paperless_testing.factories import CustomFieldFactory
from paperless_testing.factories import CustomFieldInstanceFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import StoragePathFactory
from paperless_testing.factories import TagFactory
from paperless_testing.locks import record_media_lock_acquisitions

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from pytest_django.fixtures import Settings
    from pytest_mock import MockerFixture
    from rest_framework.test import APIClient

    from paperless_testing.dirs import PaperlessDirs

    OnCommitCapture = Callable[..., AbstractContextManager[list[Callable[[], object]]]]

CONTENT = b"original content"


@pytest.fixture
def title_format(settings: Settings) -> None:
    settings.FILENAME_FORMAT = "{title}"


@pytest.fixture
def document(paperless_dirs: PaperlessDirs, title_format: None) -> Document:
    """A document named after its title, with its original on disk."""
    (paperless_dirs.originals_dir / "original.pdf").write_bytes(CONTENT)
    return DocumentFactory(
        title="original",
        filename="original.pdf",
        mime_type="application/pdf",
        checksum=hashlib.sha256(CONTENT).hexdigest(),
    )


@celery_app.task(name="documents.tests.test_file_moves.rename_then_fail")
def rename_then_fail(pk: int, originals_dir: str) -> None:
    """Test-only task: rename the document, check nothing moved yet, then fail."""
    doc = Document.objects.get(pk=pk)
    doc.title = "renamed"
    doc.save()
    assert (Path(originals_dir) / "original.pdf").is_file()
    raise RuntimeError("task failed after saving")


@pytest.mark.django_db
class TestMoveFilesForDocument:
    def test_moves_using_fresh_db_state(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A document whose title changed in the DB without any signal
        WHEN:
            - move_files_for_document is called with its pk
        THEN:
            - The file and the DB filename follow the DB title
            - The returned instance carries the final filename
        """
        Document.objects.filter(pk=document.pk).update(title="renamed")

        moved = move_files_for_document(document.pk)

        assert moved is not None
        assert moved.filename == "renamed.pdf"
        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()
        assert not (paperless_dirs.originals_dir / "original.pdf").exists()
        document.refresh_from_db()
        assert document.filename == "renamed.pdf"

    def test_missing_document_returns_none(self, paperless_dirs: PaperlessDirs) -> None:
        """
        GIVEN:
            - A pk with no document row
        WHEN:
            - move_files_for_document is called
        THEN:
            - It returns None without raising
        """
        assert move_files_for_document(999_999) is None

    def test_document_without_filename_skips_lock(
        self,
        paperless_dirs: PaperlessDirs,
        title_format: None,
    ) -> None:
        """
        GIVEN:
            - A document still being consumed (no filename yet)
        WHEN:
            - move_files_for_document is called
        THEN:
            - It returns None, writes nothing, and never takes media.lock
        """
        doc = DocumentFactory(filename=None, mime_type="application/pdf")

        with record_media_lock_acquisitions() as acquisitions:
            assert move_files_for_document(doc.pk) is None

        assert acquisitions == []
        doc.refresh_from_db()
        assert doc.filename is None

    def test_no_change_does_not_write_modified(
        self,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A document already at its generated path, modified in the past
        WHEN:
            - move_files_for_document is called
        THEN:
            - modified is not written
        """
        past = timezone.now() - datetime.timedelta(days=1)
        Document.objects.filter(pk=document.pk).update(modified=past)

        move_files_for_document(document.pk)

        document.refresh_from_db()
        assert document.modified == past

    def test_trashed_already_moved_document_gets_db_path_fixed(
        self,
        paperless_dirs: PaperlessDirs,
        title_format: None,
    ) -> None:
        """
        GIVEN:
            - A trashed document whose DB filename is stale
            - Its file already sits at the generated path (checksum matches)
        WHEN:
            - move_files_for_document is called
        THEN:
            - The DB filename is updated to where the file is
        """
        doc = DocumentFactory(
            title="current",
            filename="stale.pdf",
            mime_type="application/pdf",
            checksum=hashlib.sha256(CONTENT).hexdigest(),
        )
        assert Document.objects.get(pk=doc.pk).filename == "stale.pdf"
        doc.delete()
        (paperless_dirs.originals_dir / "current.pdf").write_bytes(CONTENT)

        move_files_for_document(doc.pk)

        assert Document.global_objects.get(pk=doc.pk).filename == "current.pdf"

    def test_lock_timeout_leaves_consistent_state(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A document whose title changed in the DB
            - media.lock cannot be acquired
        WHEN:
            - move_files_for_document is called
        THEN:
            - An error is logged and None is returned
            - The lock was requested with the 300 second timeout
            - The DB filename and the file on disk are unchanged
        """
        Document.objects.filter(pk=document.pk).update(title="renamed")
        lock = mocker.patch("documents.file_moves.media_lock")
        lock.return_value.__enter__.side_effect = Timeout("media.lock")

        with caplog.at_level(logging.ERROR, logger="paperless.handlers"):
            assert move_files_for_document(document.pk) is None

        assert "Timed out" in caplog.text
        lock.assert_called_once_with(timeout=300)
        document.refresh_from_db()
        assert document.filename == "original.pdf"
        assert (paperless_dirs.originals_dir / "original.pdf").is_file()

    def test_document_deleted_while_waiting_for_lock(
        self,
        document: Document,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A document that passes the lock-free filename check
            - The row is gone by the time the lock is held
        WHEN:
            - move_files_for_document is called
        THEN:
            - It returns None without raising
        """
        mocker.patch.object(
            Document.global_objects,
            "get",
            side_effect=Document.DoesNotExist,
        )

        assert move_files_for_document(document.pk) is None

    def test_target_outside_root_is_refused(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A generated filename that resolves outside the originals dir
        WHEN:
            - move_files_for_document is called
        THEN:
            - The move is refused and logged
            - The file and the DB filename are unchanged
        """
        mocker.patch(
            "documents.file_moves.generate_filename",
            return_value=Path("../escaped.pdf"),
        )

        with caplog.at_level(logging.WARNING, logger="paperless.handlers"):
            move_files_for_document(document.pk)

        assert "Refusing to move file outside root" in caplog.text
        assert (paperless_dirs.originals_dir / "original.pdf").is_file()
        assert not (paperless_dirs.originals_dir.parent / "escaped.pdf").exists()
        document.refresh_from_db()
        assert document.filename == "original.pdf"

    def test_target_appearing_before_move_is_never_overwritten(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A rename whose unique target name turns out to be taken
              (another file appeared after the name was chosen)
        WHEN:
            - move_files_for_document is called
        THEN:
            - Neither file is touched and the DB filename is unchanged
        """
        Document.objects.filter(pk=document.pk).update(title="renamed")
        (paperless_dirs.originals_dir / "renamed.pdf").write_bytes(b"someone else")
        mocker.patch(
            "documents.file_moves.generate_unique_filename",
            return_value=Path("renamed.pdf"),
        )

        with caplog.at_level(logging.WARNING, logger="paperless.handlers"):
            move_files_for_document(document.pk)

        assert "already exists" in caplog.text
        assert (paperless_dirs.originals_dir / "original.pdf").read_bytes() == CONTENT
        assert (paperless_dirs.originals_dir / "renamed.pdf").read_bytes() == (
            b"someone else"
        )
        document.refresh_from_db()
        assert document.filename == "original.pdf"

    def test_archive_filename_too_long_is_refused(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A document with an archive version whose generated archive
              filename exceeds the stored filename limit
        WHEN:
            - move_files_for_document is called
        THEN:
            - The move is refused and logged
            - Both filenames in the DB are unchanged
        """
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(CONTENT)
        Document.objects.filter(pk=document.pk).update(archive_filename="original.pdf")
        too_long = Path("a" * (Document.MAX_STORED_FILENAME_LENGTH + 1))
        mocker.patch(
            "documents.file_moves.generate_filename",
            side_effect=lambda doc, archive_filename=False: (
                too_long if archive_filename else Path("original.pdf")
            ),
        )

        with caplog.at_level(logging.WARNING, logger="paperless.handlers"):
            move_files_for_document(document.pk)

        assert "Generated archive filename exceeds" in caplog.text
        document.refresh_from_db()
        assert document.filename == "original.pdf"
        assert document.archive_filename == "original.pdf"

    def test_archive_already_at_generated_path_gets_db_path_fixed(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A document whose DB archive_filename is stale
            - Its archive already sits at the generated path (checksum matches)
            - The original is already correct
        WHEN:
            - move_files_for_document is called
        THEN:
            - Only archive_filename is updated, to where the archive is
            - The original is untouched
        """
        archive_content = b"archive content"
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(archive_content)
        Document.objects.filter(pk=document.pk).update(
            archive_filename="stale.pdf",
            archive_checksum=hashlib.sha256(archive_content).hexdigest(),
        )

        move_files_for_document(document.pk)

        document.refresh_from_db()
        assert document.archive_filename == "original.pdf"
        assert document.filename == "original.pdf"
        assert (paperless_dirs.originals_dir / "original.pdf").read_bytes() == CONTENT
        assert (paperless_dirs.archive_dir / "original.pdf").read_bytes() == (
            archive_content
        )

    def test_failed_restore_after_partial_move_leaves_db_untouched(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A rename that moves the original, then fails moving the archive
            - Moving the original back also fails
        WHEN:
            - move_files_for_document is called
        THEN:
            - Nothing raises
            - The DB still holds the old filenames, so nothing is claimed
              about files that did not move
            - Nothing is overwritten or deleted
        """
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(b"archive")
        Document.objects.filter(pk=document.pk).update(
            title="renamed",
            archive_filename="original.pdf",
        )
        real_move = shutil.move
        calls = 0

        def flaky_move(src: Path, dst: Path) -> object:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_move(src, dst)
            raise OSError("disk went away")

        mocker.patch("documents.file_moves.shutil.move", side_effect=flaky_move)

        move_files_for_document(document.pk)

        assert calls == 3
        document.refresh_from_db()
        assert document.filename == "original.pdf"
        assert document.archive_filename == "original.pdf"
        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()
        assert (paperless_dirs.archive_dir / "original.pdf").is_file()

    def test_original_filename_too_long_is_refused(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A generated original filename over the stored filename limit
        WHEN:
            - move_files_for_document is called
        THEN:
            - The move is refused and logged
            - The file and the DB filename are unchanged
        """
        mocker.patch(
            "documents.file_moves.generate_filename",
            return_value=Path("a" * (Document.MAX_STORED_FILENAME_LENGTH + 1)),
        )

        with caplog.at_level(logging.WARNING, logger="paperless.handlers"):
            move_files_for_document(document.pk)

        assert "Generated filename exceeds db path limit" in caplog.text
        assert (paperless_dirs.originals_dir / "original.pdf").is_file()
        document.refresh_from_db()
        assert document.filename == "original.pdf"

    def test_archive_at_generated_path_is_left_alone(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A document whose original and archive are both at their
              generated paths, modified in the past
        WHEN:
            - move_files_for_document is called
        THEN:
            - Nothing moves and modified is not written
        """
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(b"archive")
        past = timezone.now() - datetime.timedelta(days=1)
        Document.objects.filter(pk=document.pk).update(
            archive_filename="original.pdf",
            modified=past,
        )

        move_files_for_document(document.pk)

        document.refresh_from_db()
        assert document.modified == past
        assert (paperless_dirs.archive_dir / "original.pdf").read_bytes() == b"archive"

    def test_archive_name_conflict_gets_unique_name(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A rename whose archive name is already used by another file
        WHEN:
            - move_files_for_document is called
        THEN:
            - The original takes the plain new name
            - The archive takes a unique name and the other file is untouched
        """
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(b"archive")
        (paperless_dirs.archive_dir / "renamed.pdf").write_bytes(b"someone else")
        Document.objects.filter(pk=document.pk).update(
            title="renamed",
            archive_filename="original.pdf",
        )

        move_files_for_document(document.pk)

        document.refresh_from_db()
        assert document.filename == "renamed.pdf"
        assert document.archive_filename == "renamed_01.pdf"
        assert (paperless_dirs.archive_dir / "renamed_01.pdf").read_bytes() == (
            b"archive"
        )
        assert (paperless_dirs.archive_dir / "renamed.pdf").read_bytes() == (
            b"someone else"
        )

    def test_archive_only_move_cleans_up_empty_directory(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - An original at its generated path
            - An archive in a subfolder, away from its generated path
        WHEN:
            - move_files_for_document is called
        THEN:
            - Only the archive moves, to its generated path
            - The now empty archive subfolder is removed
        """
        (paperless_dirs.archive_dir / "sub").mkdir()
        (paperless_dirs.archive_dir / "sub" / "old.pdf").write_bytes(b"archive")
        Document.objects.filter(pk=document.pk).update(
            archive_filename="sub/old.pdf",
        )

        move_files_for_document(document.pk)

        document.refresh_from_db()
        assert document.filename == "original.pdf"
        assert document.archive_filename == "original.pdf"
        assert (paperless_dirs.archive_dir / "original.pdf").read_bytes() == b"archive"
        assert not (paperless_dirs.archive_dir / "sub").exists()

    def test_database_error_restores_both_files(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A rename that moves the original and the archive
            - The DB update afterwards fails
        WHEN:
            - move_files_for_document is called
        THEN:
            - Both files are moved back to where the DB says they are
        """
        (paperless_dirs.archive_dir / "original.pdf").write_bytes(b"archive")
        Document.objects.filter(pk=document.pk).update(
            title="renamed",
            archive_filename="original.pdf",
        )
        mocker.patch.object(
            Document.global_objects,
            "filter",
            side_effect=DatabaseError("write failed"),
        )

        move_files_for_document(document.pk)

        assert (paperless_dirs.originals_dir / "original.pdf").read_bytes() == CONTENT
        assert (paperless_dirs.archive_dir / "original.pdf").read_bytes() == b"archive"
        assert not (paperless_dirs.originals_dir / "renamed.pdf").exists()
        assert not (paperless_dirs.archive_dir / "renamed.pdf").exists()


class TestFlushWithoutScope:
    def test_flush_pending_file_moves_without_scope_is_noop(self) -> None:
        """
        GIVEN:
            - No file move scope is open
        WHEN:
            - flush_pending_file_moves is called
        THEN:
            - It returns without error
        """
        assert _active_collector.get() is None

        flush_pending_file_moves()


class TestPathMatchesChecksum:
    @pytest.mark.parametrize(
        ("checksum", "expected"),
        [
            pytest.param(hashlib.sha256(CONTENT).hexdigest(), True, id="match"),
            pytest.param("0" * 64, False, id="mismatch"),
            pytest.param(None, False, id="no-checksum"),
        ],
    )
    def test_file_checksum(
        self,
        tmp_path: Path,
        *,
        checksum: str | None,
        expected: bool,
    ) -> None:
        """
        GIVEN:
            - A file with known content
        WHEN:
            - Its checksum is compared against a stored value
        THEN:
            - Only a matching checksum is accepted
        """
        path = tmp_path / "file.pdf"
        path.write_bytes(CONTENT)

        assert _path_matches_checksum(path, checksum) is expected

    def test_missing_file_never_matches(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A path that is not a file
        WHEN:
            - Its checksum is compared
        THEN:
            - It does not match, whatever the stored checksum
        """
        checksum = hashlib.sha256(CONTENT).hexdigest()

        assert _path_matches_checksum(tmp_path / "missing.pdf", checksum) is False
        assert _path_matches_checksum(tmp_path, checksum) is False


@pytest.mark.django_db
class TestRequestFileMoveWithoutScope:
    def test_moves_immediately_and_syncs_only_file_columns(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - No file move scope is open
            - A caller instance with an unsaved in-memory change
        WHEN:
            - request_file_move is called after the title changed in the DB
        THEN:
            - The file moves immediately
            - The caller's filename is updated
            - The caller's unsaved change is kept
        """
        Document.objects.filter(pk=document.pk).update(title="renamed")
        unsaved = CorrespondentFactory()
        document.correspondent = unsaved

        request_file_move(document)

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()
        assert document.filename == "renamed.pdf"
        assert document.correspondent == unsaved
        assert document.title == "original"


@pytest.mark.django_db
class TestReceiver:
    def test_reverse_m2m_requests_a_move_per_document(
        self,
        document: Document,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A tag
        WHEN:
            - A document is added through the tag's reverse relation
        THEN:
            - A move is requested for the added document, never the tag
        """
        tag = TagFactory()
        request = mocker.patch("documents.signals.handlers.request_file_move")

        tag.documents.add(document)

        request.assert_called_once()
        assert request.call_args.args[0].pk == document.pk

    def test_reverse_clear_requests_a_move_per_cleared_document(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A tag on two documents, and one document without it
        WHEN:
            - The tag's reverse relation is cleared
        THEN:
            - A move is requested for each cleared document, and no other
        """
        tag = TagFactory()
        first = DocumentFactory.create()
        second = DocumentFactory.create()
        other = DocumentFactory.create()
        first.tags.add(tag)
        second.tags.add(tag)
        request = mocker.patch("documents.signals.handlers.request_file_move")

        tag.documents.clear()

        assert {call.args[0].pk for call in request.call_args_list} == {
            first.pk,
            second.pk,
        }
        assert other.pk not in {call.args[0].pk for call in request.call_args_list}

    def test_reverse_clear_moves_file_for_tag_in_template(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - A document whose filename depends on its tag
        WHEN:
            - The tag is removed through the reverse relation's clear()
        THEN:
            - The file and filename follow the document's new state
        """
        settings.FILENAME_FORMAT = "{tag_list}/{title}"
        tag = TagFactory(name="clearme")
        with defer_file_moves():
            document.tags.add(tag)
        document.refresh_from_db()
        assert document.filename == "clearme/original.pdf"

        with defer_file_moves():
            tag.documents.clear()

        document.refresh_from_db()
        assert document.filename == "original.pdf"
        assert (paperless_dirs.originals_dir / "original.pdf").is_file()


@pytest.mark.django_db
class TestDeferFileMoves:
    def test_moves_once_on_exit(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - An open file move scope
        WHEN:
            - The document is saved with a new title inside the scope
        THEN:
            - Nothing moves while the scope is open
            - On exit the file and DB filename follow the final title
        """
        with defer_file_moves():
            document.title = "renamed"
            document.save()
            assert (paperless_dirs.originals_dir / "original.pdf").is_file()
            assert Document.objects.get(pk=document.pk).filename == "original.pdf"

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()
        assert not (paperless_dirs.originals_dir / "original.pdf").exists()
        assert Document.objects.get(pk=document.pk).filename == "renamed.pdf"

    def test_nested_scope_defers_to_outer(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A scope nested inside another
        WHEN:
            - The document is saved inside the inner scope and the inner scope exits
        THEN:
            - Nothing moves until the outer scope exits
        """
        with defer_file_moves():
            with defer_file_moves():
                document.title = "renamed"
                document.save()
            assert (paperless_dirs.originals_dir / "original.pdf").is_file()

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_closed_collector_moves_immediately(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A collector that has already been closed (work outliving its scope)
        WHEN:
            - A save asks for a move while that collector is still current
        THEN:
            - The move happens immediately instead of being lost
        """
        with defer_file_moves():
            collector = _active_collector.get()
        assert collector is not None
        token = _active_collector.set(collector)
        try:
            document.title = "renamed"
            document.save()
        finally:
            _active_collector.reset(token)

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_scope_closing_inside_atomic_flushes_on_commit(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        django_capture_on_commit_callbacks: OnCommitCapture,
    ) -> None:
        """
        GIVEN:
            - A scope opened and closed inside an atomic block
        WHEN:
            - The atomic block commits
        THEN:
            - The move runs only once the commit callbacks run
        """
        with django_capture_on_commit_callbacks(execute=True):
            with transaction.atomic(), defer_file_moves():
                document.title = "renamed"
                document.save()
            assert (paperless_dirs.originals_dir / "original.pdf").is_file()

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_scope_closing_inside_rolled_back_atomic_moves_nothing(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        django_capture_on_commit_callbacks: OnCommitCapture,
    ) -> None:
        """
        GIVEN:
            - A scope opened and closed inside an atomic block
        WHEN:
            - The atomic block rolls back
        THEN:
            - The title change is gone and the file is not moved
        """

        class Rollback(Exception):
            pass

        with django_capture_on_commit_callbacks(execute=True):
            with pytest.raises(Rollback):
                with transaction.atomic(), defer_file_moves():
                    document.title = "renamed"
                    document.save()
                    raise Rollback

        assert (paperless_dirs.originals_dir / "original.pdf").is_file()
        assert not (paperless_dirs.originals_dir / "renamed.pdf").exists()
        assert Document.objects.get(pk=document.pk).title == "original"

    def test_flush_pending_moves_early(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - An open scope with a pending move
        WHEN:
            - flush_pending_file_moves is called inside the scope
        THEN:
            - The move happens before the scope exits
        """
        with defer_file_moves():
            document.title = "renamed"
            document.save()
            flush_pending_file_moves()
            assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_document_without_filename_in_scope_is_noop(
        self,
        paperless_dirs: PaperlessDirs,
        title_format: None,
    ) -> None:
        """
        GIVEN:
            - A document still being consumed (no filename yet)
        WHEN:
            - It is saved inside a scope and the scope exits
        THEN:
            - Nothing is written, media.lock is never taken, nothing raises
        """
        doc = DocumentFactory(filename=None, mime_type="application/pdf")

        with record_media_lock_acquisitions() as acquisitions:
            with defer_file_moves():
                doc.title = "renamed"
                doc.save()

        assert acquisitions == []
        doc.refresh_from_db()
        assert doc.filename is None

    def test_mover_keeps_metadata_changed_after_save(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - A filename format using correspondent and title
            - A scope in which the title is saved
        WHEN:
            - Another writer changes the correspondent before the scope exits
        THEN:
            - The correspondent change survives the flush
            - The final path reflects both changes
        """
        settings.FILENAME_FORMAT = "{correspondent}/{title}"
        correspondent = CorrespondentFactory(name="acme")

        with defer_file_moves():
            document.title = "renamed"
            document.save()
            Document.objects.filter(pk=document.pk).update(correspondent=correspondent)

        document.refresh_from_db()
        assert document.correspondent == correspondent
        assert document.filename == "acme/renamed.pdf"
        assert (paperless_dirs.originals_dir / "acme" / "renamed.pdf").is_file()

    def test_one_failure_does_not_stop_the_flush(
        self,
        paperless_dirs: PaperlessDirs,
        title_format: None,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Two documents saved in one scope
            - Moving the first raises an unexpected error
        WHEN:
            - The scope exits
        THEN:
            - The scope does not raise
            - The second document is still moved
        """
        (paperless_dirs.originals_dir / "a.pdf").write_bytes(CONTENT)
        first = DocumentFactory(
            filename="a.pdf",
            title="a",
            mime_type="application/pdf",
        )
        (paperless_dirs.originals_dir / "b.pdf").write_bytes(CONTENT)
        second = DocumentFactory(
            filename="b.pdf",
            title="b",
            mime_type="application/pdf",
        )

        real_move = move_files_for_document

        def failing_for_first(pk: int) -> Document | None:
            if pk == first.pk:
                raise RuntimeError("boom")
            return real_move(pk)

        mocker.patch(
            "documents.file_moves.move_files_for_document",
            side_effect=failing_for_first,
        )

        with defer_file_moves():
            first.title = "a2"
            first.save()
            second.title = "b2"
            second.save()

        assert (paperless_dirs.originals_dir / "b2.pdf").is_file()
        assert (paperless_dirs.originals_dir / "a.pdf").is_file()


@pytest.mark.django_db
class TestAsyncDeferFileMoves:
    def test_nested_async_scope_defers_to_outer(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - An async scope nested inside another async scope
        WHEN:
            - The document is renamed inside the inner scope
        THEN:
            - Nothing moves when the inner scope exits
            - The file moves once the outer scope exits
        """

        def rename() -> None:
            document.title = "renamed"
            document.save()

        async def run() -> None:
            async with adefer_file_moves():
                async with adefer_file_moves():
                    await sync_to_async(rename)()
                assert (paperless_dirs.originals_dir / "original.pdf").is_file()
            assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

        async_to_sync(run)()

    def test_empty_async_scope_skips_the_flush(
        self,
        document: Document,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An async scope in which no move was requested
        WHEN:
            - The scope exits
        THEN:
            - No flush is attempted, so no thread hop is paid
        """
        flush = mocker.patch("documents.file_moves._flush_after_commit")

        async def run() -> None:
            async with adefer_file_moves():
                pass

        async_to_sync(run)()

        flush.assert_not_called()


@pytest.mark.django_db
class TestFileMoveMiddleware:
    def test_sync_mode_flushes_before_returning(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - The middleware wrapping a sync view that renames the document
        WHEN:
            - A request passes through it
        THEN:
            - Nothing moves while the view runs
            - The file is at its final path when the middleware returns
        """

        def view(request: HttpRequest) -> HttpResponse:
            document.title = "renamed"
            document.save()
            assert (paperless_dirs.originals_dir / "original.pdf").is_file()
            return HttpResponse()

        middleware = FileMoveMiddleware(view)
        assert middleware.async_mode is False

        middleware(RequestFactory().get("/"))

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_async_mode_flushes_after_await(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - The middleware wrapping an async view that saves through
              sync_to_async
        WHEN:
            - A request passes through it
        THEN:
            - Nothing moves while the view runs
            - The file is at its final path after the await, so the collector
              survived the context copy into the sync thread
        """

        def rename() -> None:
            document.title = "renamed"
            document.save()

        async def view(request: HttpRequest) -> HttpResponse:
            await sync_to_async(rename)()
            assert (paperless_dirs.originals_dir / "original.pdf").is_file()
            return HttpResponse()

        middleware = FileMoveMiddleware(view)
        assert middleware.async_mode is True

        async_to_sync(middleware)(RequestFactory().get("/"))

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_view_raising_after_save_still_moves(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A view that saves a rename and then raises
        WHEN:
            - A request passes through the middleware
        THEN:
            - The exception propagates
            - The committed rename is still moved
        """

        def view(request: HttpRequest) -> HttpResponse:
            document.title = "renamed"
            document.save()
            raise RuntimeError("view failed")

        with pytest.raises(RuntimeError, match="view failed"):
            FileMoveMiddleware(view)(RequestFactory().get("/"))

        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()


@pytest.mark.django_db
class TestFileMovesThroughApi:
    def test_media_lock_never_taken_inside_a_transaction(
        self,
        admin_client: APIClient,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A document and a tag
        WHEN:
            - A tag + title PATCH and a note POST are made through the API
        THEN:
            - media.lock is acquired at least once
            - media.lock is never first acquired while a transaction is open
        """
        tag = TagFactory()

        with record_media_lock_acquisitions() as acquisitions:
            response = admin_client.patch(
                f"/api/documents/{document.pk}/",
                {"tags": [tag.pk], "title": "renamed"},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
            response = admin_client.post(
                f"/api/documents/{document.pk}/notes/",
                {"note": "a note"},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK

        assert acquisitions
        assert not any(a.in_user_transaction for a in acquisitions)

    def test_patch_moves_to_final_path(
        self,
        admin_client: APIClient,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A document named after its title
        WHEN:
            - Its title and tags are changed through the API
        THEN:
            - The file is at the final path when the response returns
        """
        response = admin_client.patch(
            f"/api/documents/{document.pk}/",
            {"tags": [TagFactory().pk], "title": "renamed"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()
        assert Document.objects.get(pk=document.pk).filename == "renamed.pdf"

    def test_patch_response_reports_post_move_modified(
        self,
        admin_client: APIClient,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A document named after its title
        WHEN:
            - Its title is changed through the API, causing a rename
        THEN:
            - The modified time in the response equals the stored value,
              which the file move bumped after the edit was saved
        """
        response = admin_client.patch(
            f"/api/documents/{document.pk}/",
            {"title": "renamed"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        stored = Document.objects.get(pk=document.pk)
        assert stored.filename == "renamed.pdf"
        assert parse_datetime(response.json()["modified"]) == stored.modified

    def test_trash_restore_keeps_db_and_disk_consistent(
        self,
        admin_client: APIClient,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A document moved to the trash
        WHEN:
            - It is restored through the trash API
        THEN:
            - Its DB filename points at a file that exists
        """
        admin_client.delete(f"/api/documents/{document.pk}/")

        response = admin_client.post(
            "/api/trash/",
            {"action": "restore", "documents": [document.pk]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        restored = Document.objects.get(pk=document.pk)
        assert restored.source_path.is_file()

    def test_root_storage_path_change_moves_versions(
        self,
        admin_client: APIClient,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A root document with one version, both with files on disk
        WHEN:
            - The root's storage path is changed through the API
        THEN:
            - The root and version files both follow the storage path
        """
        (paperless_dirs.originals_dir / "version.pdf").write_bytes(CONTENT)
        version = DocumentFactory(
            root_document=document,
            title="version",
            filename="version.pdf",
            mime_type="application/pdf",
            checksum=hashlib.sha256(CONTENT).hexdigest(),
        )
        storage_path = StoragePathFactory(path="stored/{{ title }}")

        response = admin_client.patch(
            f"/api/documents/{document.pk}/",
            {"storage_path": storage_path.pk},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        document.refresh_from_db()
        version.refresh_from_db()
        assert document.filename.startswith("stored/")
        assert version.filename.startswith("stored/")
        assert document.source_path.is_file()
        assert version.source_path.is_file()

    def test_custom_field_change_moves_to_final_path(
        self,
        admin_client: APIClient,
        document: Document,
        paperless_dirs: PaperlessDirs,
        settings: Settings,
    ) -> None:
        """
        GIVEN:
            - A filename format that uses a text custom field
            - A document with that field set
        WHEN:
            - The field value is changed through the API
        THEN:
            - The file is at the path for the new value
        """
        settings.FILENAME_FORMAT = (
            "{{ custom_fields|get_cf_value('flavor') }}/{{ title }}"
        )
        field = CustomFieldFactory(
            name="flavor",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstanceFactory(field=field, document=document, value_text="apple")

        response = admin_client.patch(
            f"/api/documents/{document.pk}/",
            {"custom_fields": [{"field": field.pk, "value": "cherry"}]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        document.refresh_from_db()
        assert document.filename == "cherry/original.pdf"
        assert (paperless_dirs.originals_dir / "cherry" / "original.pdf").is_file()


@pytest.mark.django_db
class TestCeleryTaskScope:
    def test_task_class_opens_scope(self) -> None:
        """
        GIVEN:
            - The paperless Celery app
        WHEN:
            - A registered task is inspected
        THEN:
            - It runs through FileMoveScopedTask
            - It keeps Celery's DjangoTask API, such as delay_on_commit
        """
        from paperless.celery import FileMoveScopedTask

        assert isinstance(bulk_update_documents, FileMoveScopedTask)
        assert isinstance(bulk_update_documents, DjangoTask)

    def test_failing_task_still_moves_committed_change(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A task that renames a document, then raises
        WHEN:
            - The task is applied
        THEN:
            - The task fails with its own error
            - Nothing moved while the task body ran
            - The committed rename is moved when the task ends
        """
        result = rename_then_fail.apply(
            args=[document.pk, str(paperless_dirs.originals_dir)],
        )

        assert result.failed()
        assert isinstance(result.result, RuntimeError)
        assert (paperless_dirs.originals_dir / "renamed.pdf").is_file()

    def test_bulk_update_moves_each_document(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Two documents whose titles changed in the DB without signals
        WHEN:
            - bulk_update_documents runs for both
        THEN:
            - Each document's file follows its new title
        """
        mocker.patch("documents.search.get_backend")
        (paperless_dirs.originals_dir / "second.pdf").write_bytes(CONTENT)
        second = DocumentFactory(
            title="second",
            filename="second.pdf",
            mime_type="application/pdf",
            checksum=hashlib.sha256(CONTENT).hexdigest(),
        )
        Document.objects.filter(pk=document.pk).update(title="first-renamed")
        Document.objects.filter(pk=second.pk).update(title="second-renamed")

        bulk_update_documents.apply(args=[[document.pk, second.pk]])

        assert (paperless_dirs.originals_dir / "first-renamed.pdf").is_file()
        assert (paperless_dirs.originals_dir / "second-renamed.pdf").is_file()

    def test_scheduled_workflows_move_each_document(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Two documents matched by a scheduled workflow, where running the
              workflow renames the document
        WHEN:
            - check_scheduled_workflows runs
        THEN:
            - The first document's file is already moved when the workflow
              runs for the second, not only when the task ends
        """
        (paperless_dirs.originals_dir / "second.pdf").write_bytes(CONTENT)
        second = DocumentFactory(
            title="second",
            filename="second.pdf",
            mime_type="application/pdf",
            checksum=hashlib.sha256(CONTENT).hexdigest(),
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=0,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.ADDED,
        )
        workflow = Workflow.objects.create(name="scheduled", order=0)
        workflow.triggers.add(trigger)
        workflow.actions.add(WorkflowAction.objects.create(assign_title="unused"))

        seen: dict[int, bool] = {}

        def rename(*, document: Document, **kwargs: object) -> None:
            seen[document.pk] = (paperless_dirs.originals_dir / "first.pdf").is_file()
            document.title = "first" if document.pk == first_pk else "other"
            document.save()

        first_pk = min(document.pk, second.pk)
        mocker.patch("documents.tasks.run_workflows", side_effect=rename)
        mocker.patch("documents.tasks.send_websocket_document_updated")

        check_scheduled_workflows.apply()

        second_pk = max(document.pk, second.pk)
        assert seen[first_pk] is False
        assert seen[second_pk] is True

    def test_websocket_notification_sent_after_move(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A document matched by a scheduled workflow that renames it
        WHEN:
            - check_scheduled_workflows runs
        THEN:
            - The websocket notification is sent after the file has moved and
              the filename column is updated, so clients see the final state
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=0,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.ADDED,
        )
        workflow = Workflow.objects.create(name="scheduled", order=0)
        workflow.triggers.add(trigger)
        workflow.actions.add(WorkflowAction.objects.create(assign_title="unused"))

        def rename(*, document: Document, **kwargs: object) -> None:
            document.title = "renamed"
            document.save()

        state: dict[str, object] = {}

        def notify(*, document: Document, **kwargs: object) -> None:
            state["moved"] = (paperless_dirs.originals_dir / "renamed.pdf").is_file()
            state["filename"] = Document.objects.get(pk=document.pk).filename

        mocker.patch("documents.tasks.run_workflows", side_effect=rename)
        mocker.patch("documents.tasks.send_websocket_document_updated", notify)

        check_scheduled_workflows.apply()

        assert state == {"moved": True, "filename": "renamed.pdf"}


@pytest.mark.django_db
class TestEmptyTrashLockOrdering:
    def test_hard_delete_takes_media_lock_outside_transaction(
        self,
        document: Document,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - A trashed document with its file on disk
        WHEN:
            - The trash is emptied for it
        THEN:
            - media.lock is never first acquired inside a transaction
            - The document row and its file are gone
        """
        document.delete()

        with record_media_lock_acquisitions() as acquisitions:
            empty_trash([document.pk])

        assert acquisitions
        assert not any(a.in_user_transaction for a in acquisitions)
        assert not Document.global_objects.filter(pk=document.pk).exists()
        assert not (paperless_dirs.originals_dir / "original.pdf").exists()
