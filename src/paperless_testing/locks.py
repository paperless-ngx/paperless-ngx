"""Record first acquisitions of the global media lock during a test."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class MediaLockAcquisition:
    """One first (non-reentrant) acquisition of settings.MEDIA_LOCK."""

    in_user_transaction: bool


@contextmanager
def record_media_lock_acquisitions() -> Iterator[list[MediaLockAcquisition]]:
    """
    Record every first acquisition of settings.MEDIA_LOCK made in the block.

    Reentrant acquisitions by a thread that already holds the lock never wait,
    so they are not recorded. Each record notes whether a real (non test case)
    transaction was open at that moment, which is the lock ordering hazard.
    """
    from django.conf import settings
    from filelock import BaseFileLock

    from documents.file_moves import in_user_transaction

    records: list[MediaLockAcquisition] = []
    original_acquire = BaseFileLock.acquire

    def recording_acquire(self: BaseFileLock, *args: object, **kwargs: object):
        if Path(self.lock_file) == Path(settings.MEDIA_LOCK) and not self.is_locked:
            records.append(
                MediaLockAcquisition(in_user_transaction=in_user_transaction()),
            )
        return original_acquire(self, *args, **kwargs)

    with mock.patch.object(BaseFileLock, "acquire", recording_acquire):
        yield records
