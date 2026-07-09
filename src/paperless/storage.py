from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import fsspec
from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import IO


class PaperlessStorage:
    """
    Thin wrapper around fsspec providing paperless-specific operations.
    Abstracts local filesystem and future remote backends (S3, GCS, etc).
    """

    def __init__(self) -> None:
        backend: str = getattr(settings, "PAPERLESS_STORAGE_BACKEND", "file")
        options: dict = getattr(settings, "PAPERLESS_STORAGE_BACKEND_OPTIONS", {})
        self._protocol = backend
        self._fs = fsspec.filesystem(backend, **options)

    # ------------------------------------------------------------------ #
    # File I/O                                                             #
    # ------------------------------------------------------------------ #

    def open(self, path: str | Path, mode: str = "rb") -> IO:
        return self._fs.open(str(path), mode)

    def write(self, dest: str | Path, source: str | Path | bytes | IO) -> None:
        dest_str = str(dest)
        if isinstance(source, (str, Path)):
            self._fs.put(str(source), dest_str)
        elif isinstance(source, bytes):
            with self._fs.open(dest_str, "wb") as f:
                f.write(source)
        else:
            with self._fs.open(dest_str, "wb") as f:
                f.write(source.read())

    def delete(self, path: str | Path | None) -> None:
        if path is not None:
            try:
                self._fs.rm(str(path))
            except FileNotFoundError:
                pass

    def move(self, src: str | Path, dst: str | Path) -> None:
        self._fs.move(str(src), str(dst))

    def copy(self, src: str | Path, dst: str | Path) -> None:
        self._fs.copy(str(src), str(dst))

    # ------------------------------------------------------------------ #
    # Queries                                                              #
    # ------------------------------------------------------------------ #

    def exists(self, path: str | Path) -> bool:
        return self._fs.exists(str(path))

    def size(self, path: str | Path) -> int | None:
        try:
            return self._fs.stat(str(path))["size"]
        except (FileNotFoundError, KeyError):
            return None

    # ------------------------------------------------------------------ #
    # Path helpers (filesystem-specific)                                   #
    # ------------------------------------------------------------------ #

    def makedirs(self, path: str | Path) -> None:
        """Create parent directory structure. No-op for object stores."""
        try:
            self._fs.makedirs(str(Path(path).parent), exist_ok=True)
        except (NotImplementedError, AttributeError):
            pass  # remote backends don't need directories

    def delete_empty_dirs(self, path: str | Path, root: str | Path) -> None:
        """Prune empty parent dirs up to root. Local filesystem only."""
        if self._protocol == "file":
            from documents.file_handling import delete_empty_directories

            delete_empty_directories(Path(path).parent, root=Path(root))

    def glob(self, pattern: str | Path) -> list[str]:
        return self._fs.glob(str(pattern))

    # ------------------------------------------------------------------ #
    # Locking                                                              #
    # ------------------------------------------------------------------ #

    @contextmanager
    def acquire_lock(self) -> Generator[None, None, None]:
        """
        Context manager for storage-level lock.
        Local: filelock on MEDIA_LOCK (existing behavior).
        Remote (future): Redis lock (Redis is already a dependency via Celery).
        """
        if self._protocol == "file":
            from filelock import FileLock

            with FileLock(settings.MEDIA_LOCK):
                yield
        else:
            # Future S3 backend uses Redis lock
            import redis as redis_client

            client = redis_client.from_url(settings.CELERY_BROKER_URL)
            lock = client.lock("paperless_media_lock", timeout=300)
            with lock:
                yield


# ------------------------------------------------------------------ #
# Singleton accessor                                                   #
# ------------------------------------------------------------------ #

_storage: PaperlessStorage | None = None
_storage_lock = threading.Lock()


def get_storage() -> PaperlessStorage:
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = PaperlessStorage()
    return _storage


def reset_storage() -> None:
    """For tests only — clears the cached singleton."""
    global _storage
    _storage = None
