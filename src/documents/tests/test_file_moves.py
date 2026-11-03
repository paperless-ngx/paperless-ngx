from __future__ import annotations

import datetime
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from celery.contrib.django.task import DjangoTask
from django.db import transaction
from django.http import HttpRequest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from filelock import Timeout
from rest_framework import status

from documents.file_moves import _active_collector
from documents.file_moves import defer_file_moves
from documents.file_moves import flush_pending_file_moves
from documents.file_moves import move_files_for_document
from documents.file_moves import request_file_move
from documents.models import CustomField
from documents.models import Document
from documents.tasks import bulk_update_documents
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
            - media.lock is never first acquired while a transaction is open,
              which is the lock ordering that let two such requests deadlock
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
