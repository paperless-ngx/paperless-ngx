from __future__ import annotations

import datetime
import hashlib
import logging
from typing import TYPE_CHECKING

import pytest
from django.utils import timezone
from filelock import Timeout

from documents.file_moves import move_files_for_document
from documents.file_moves import request_file_move
from documents.models import Document
from paperless_testing.factories import CorrespondentFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import TagFactory
from paperless_testing.locks import record_media_lock_acquisitions

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings
    from pytest_mock import MockerFixture

    from paperless_testing.dirs import PaperlessDirs

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
            - Its file sits at the generated path (checksum matches), placed
              after the creation-time move already failed
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
    def test_reverse_m2m_does_not_request_a_move(
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
            - No move is requested with the tag as the instance
        """
        tag = TagFactory()
        request = mocker.patch("documents.signals.handlers.request_file_move")

        tag.documents.add(document)

        request.assert_not_called()
