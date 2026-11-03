from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest
from django.db import transaction
from filelock import Timeout

from documents.file_moves import in_user_transaction
from documents.media_lock import media_lock
from paperless_testing.locks import record_media_lock_acquisitions

if TYPE_CHECKING:
    from paperless_testing.dirs import PaperlessDirs


@pytest.mark.usefixtures("paperless_dirs")
class TestMediaLock:
    def test_same_thread_reenters_without_blocking(self) -> None:
        """
        GIVEN:
            - media.lock held by the current thread
        WHEN:
            - The same thread acquires it again with a zero timeout
        THEN:
            - The nested acquisition succeeds immediately
        """
        with media_lock(), media_lock(timeout=0):
            pass

    def test_other_thread_is_excluded(self) -> None:
        """
        GIVEN:
            - media.lock held by the current thread
        WHEN:
            - Another thread tries to acquire it with a short timeout
        THEN:
            - The other thread times out
            - After release, the other thread can acquire it
        """
        outcomes: list[str] = []

        def try_acquire() -> None:
            try:
                with media_lock(timeout=0.2):
                    outcomes.append("acquired")
            except Timeout:
                outcomes.append("timeout")

        with media_lock():
            worker = threading.Thread(target=try_acquire)
            worker.start()
            worker.join()

        worker = threading.Thread(target=try_acquire)
        worker.start()
        worker.join()

        assert outcomes == ["timeout", "acquired"]

    def test_lock_file_is_the_configured_path(
        self,
        paperless_dirs: PaperlessDirs,
    ) -> None:
        """
        GIVEN:
            - The test's media directory layout
        WHEN:
            - media.lock is acquired
        THEN:
            - The lock file is created at settings.MEDIA_LOCK
        """
        with media_lock():
            assert paperless_dirs.media_lock.exists()


@pytest.mark.django_db
class TestInUserTransaction:
    def test_false_inside_test_case_wrapper(self) -> None:
        """
        GIVEN:
            - The transaction pytest-django wraps around the test
        WHEN:
            - in_user_transaction is called
        THEN:
            - It returns False
        """
        assert in_user_transaction() is False

    def test_true_inside_atomic(self) -> None:
        """
        GIVEN:
            - An atomic block opened by code under test
        WHEN:
            - in_user_transaction is called inside it
        THEN:
            - It returns True
        """
        with transaction.atomic():
            assert in_user_transaction() is True


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRecordMediaLockAcquisitions:
    def test_records_only_first_acquisitions(self) -> None:
        """
        GIVEN:
            - Nested media.lock acquisitions, the outer one inside a transaction
        WHEN:
            - They are recorded
        THEN:
            - Only the outer, first acquisition is recorded, flagged as inside
              a transaction
        """
        with record_media_lock_acquisitions() as acquisitions:
            with transaction.atomic(), media_lock(), media_lock():
                pass

        assert [a.in_user_transaction for a in acquisitions] == [True]
