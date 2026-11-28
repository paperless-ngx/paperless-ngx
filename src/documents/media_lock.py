"""
The global media lock, reentrant within a thread.

Code that both needs media.lock and opens a transaction that locks document
rows must take media.lock first, so no transaction ever waits on it while
holding rows. Reentrancy lets code already holding the lock (for example the
consumer) call into code that takes it again (for example a workflow email
action attaching files) without blocking itself.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.conf import settings
from filelock import FileLock

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def media_lock(timeout: float = -1) -> Iterator[None]:
    """
    Hold settings.MEDIA_LOCK for the block.

    is_singleton returns one FileLock instance per path in this process, and
    the default thread_local=True keeps the hold count per thread, so the
    same thread re-enters while other threads and processes are excluded.
    The timeout goes to acquire() because a singleton rejects construction
    with different parameters. A negative timeout waits forever.
    """
    lock = FileLock(settings.MEDIA_LOCK, is_singleton=True)
    with lock.acquire(timeout=timeout):
        yield
