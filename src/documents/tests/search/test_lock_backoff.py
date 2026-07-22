"""Tests for search index lock backoff, retry logic, and self-healing deferred tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import filelock
import pytest

from documents.search._backend import _LOCK_BACKOFF_CAP
from documents.search._backend import _LOCK_RETRY_ATTEMPTS
from documents.search._backend import _LOCK_TIMEOUT_SECONDS
from documents.search._backend import SearchIndexLockError
from documents.search._backend import TantivyBackend
from documents.tasks import index_document
from documents.tasks import remove_document_from_index
from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.search


@pytest.fixture
def disk_backend(tmp_path: Path) -> Generator[TantivyBackend, None, None]:
    """On-disk TantivyBackend so the file-lock code path is exercised."""
    b = TantivyBackend(path=tmp_path)
    b.open()
    try:
        yield b
    finally:
        b.close()


class TestWriteBatchLockRetry:
    """Test WriteBatch retry loop with backoff + full jitter."""

    @pytest.mark.django_db
    def test_lock_retries_then_succeeds(
        self,
        disk_backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """Timeout on first 3 attempts then success on 4th — document must be indexed."""
        doc = DocumentFactory()

        acquire_calls = 0

        def flaky_acquire(timeout: float) -> None:
            nonlocal acquire_calls
            acquire_calls += 1
            # Raise Timeout for first _LOCK_RETRY_ATTEMPTS - 1 calls, succeed on last
            if acquire_calls < _LOCK_RETRY_ATTEMPTS:
                raise filelock.Timeout("")

        sleep_values: list[float] = []

        mocker.patch(
            "documents.search._backend.filelock.FileLock.acquire",
            side_effect=flaky_acquire,
        )
        mock_sleep = mocker.patch(
            "documents.search._backend.time.sleep",
            side_effect=lambda s: sleep_values.append(s),
        )

        # Should not raise — 4th attempt succeeds
        with disk_backend.batch_update(lock_timeout=_LOCK_TIMEOUT_SECONDS) as batch:
            batch.add_or_update(doc)

        # sleep called exactly _LOCK_RETRY_ATTEMPTS - 1 times (once per failed attempt)
        assert mock_sleep.call_count == _LOCK_RETRY_ATTEMPTS - 1

        # All sleep values must be in [0, _LOCK_BACKOFF_CAP]
        for s in sleep_values:
            assert 0 <= s <= _LOCK_BACKOFF_CAP, (
                f"Sleep value {s} outside [0, {_LOCK_BACKOFF_CAP}]"
            )

    def test_lock_exhaustion_raises_search_index_lock_error(
        self,
        disk_backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """All acquire attempts raise Timeout — WriteBatch must raise SearchIndexLockError."""
        mocker.patch(
            "documents.search._backend.filelock.FileLock.acquire",
            side_effect=filelock.Timeout(""),
        )
        mocker.patch("documents.search._backend.time.sleep")

        with pytest.raises(SearchIndexLockError):
            with disk_backend.batch_update(lock_timeout=_LOCK_TIMEOUT_SECONDS):
                pass

    def test_jitter_values_in_range(
        self,
        disk_backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """Sleep values must always lie in [0, _LOCK_BACKOFF_CAP] across many samples."""
        mocker.patch(
            "documents.search._backend.filelock.FileLock.acquire",
            side_effect=filelock.Timeout(""),
        )
        sleep_values: list[float] = []
        mocker.patch(
            "documents.search._backend.time.sleep",
            side_effect=lambda s: sleep_values.append(s),
        )
        for _ in range(50):
            sleep_values.clear()
            with pytest.raises(SearchIndexLockError):
                with disk_backend.batch_update(lock_timeout=_LOCK_TIMEOUT_SECONDS):
                    pass

            for s in sleep_values:
                assert 0 <= s <= _LOCK_BACKOFF_CAP, (
                    f"Jitter {s} exceeds cap {_LOCK_BACKOFF_CAP}"
                )


class TestAddOrUpdateDeferredScheduling:
    """Test that add_or_update() and remove() defer to Celery on lock exhaustion."""

    @pytest.mark.django_db
    def test_lock_exhaustion_schedules_deferred_task(
        self,
        disk_backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """Lock exhaustion in add_or_update must schedule index_document task, not raise."""
        doc = DocumentFactory()

        mocker.patch(
            "documents.search._backend.filelock.FileLock.acquire",
            side_effect=filelock.Timeout(""),
        )
        mocker.patch("documents.search._backend.time.sleep")
        mock_apply = mocker.patch("documents.tasks.index_document.apply_async")

        # Must NOT raise
        disk_backend.add_or_update(doc)

        mock_apply.assert_called_once_with(args=[doc.pk], countdown=60)

    def test_remove_exhaustion_schedules_deferred_task(
        self,
        disk_backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """Lock exhaustion in remove() must schedule remove_document_from_index task, not raise."""
        doc_id = 503

        mocker.patch(
            "documents.search._backend.filelock.FileLock.acquire",
            side_effect=filelock.Timeout(""),
        )
        mocker.patch("documents.search._backend.time.sleep")
        mock_apply = mocker.patch(
            "documents.tasks.remove_document_from_index.apply_async",
        )

        # Must NOT raise
        disk_backend.remove(doc_id)

        mock_apply.assert_called_once_with(args=[doc_id], countdown=60)


@pytest.mark.django_db
class TestIndexDocumentTask:
    """Test the deferred index_document and remove_document_from_index Celery tasks."""

    def test_index_document_task_skips_deleted_document(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """index_document with a non-existent doc_id must return cleanly and log INFO."""
        nonexistent_id = 999999

        with caplog.at_level(logging.INFO, logger="paperless.tasks"):
            index_document(nonexistent_id)

        assert any("no longer exists" in record.message for record in caplog.records), (
            "Expected INFO log about missing document"
        )

    def test_index_document_task_indexes_existing_document(
        self,
        backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """index_document task must add the document to the index via batch_update."""
        doc = DocumentFactory(content="via deferred task")

        # get_backend is imported lazily inside the task: `from documents.search import get_backend`
        mocker.patch(
            "documents.search.get_backend",
            return_value=backend,
        )
        index_document(doc.pk)

        ids = backend.search_ids("deferred task", user=None)
        assert doc.pk in ids

    def test_remove_document_from_index_task_removes_existing_document(
        self,
        backend: TantivyBackend,
        mocker: MockerFixture,
    ) -> None:
        """remove_document_from_index task must remove the document from the index."""
        doc = DocumentFactory(content="will be removed by deferred task")
        backend.add_or_update(doc)
        assert doc.pk in backend.search_ids("removed", user=None)

        mocker.patch("documents.search.get_backend", return_value=backend)
        remove_document_from_index(doc.pk)

        assert doc.pk not in backend.search_ids("removed", user=None)

    def test_task_does_not_swallow_lock_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verifies the task body propagates SearchIndexLockError so Celery's
        autoretry_for can catch it (rather than the task swallowing the error
        and silently succeeding)."""
        doc = DocumentFactory()

        mock_batch = mocker.MagicMock()
        mock_batch.__enter__ = mocker.MagicMock(
            side_effect=SearchIndexLockError("exhausted"),
        )
        mock_batch.__exit__ = mocker.MagicMock(return_value=False)

        mock_backend = mocker.MagicMock()
        mock_backend.batch_update.return_value = mock_batch

        # get_backend is imported lazily inside the task: `from documents.search import get_backend`
        mocker.patch("documents.search.get_backend", return_value=mock_backend)

        with pytest.raises(SearchIndexLockError):
            index_document(doc.pk)
