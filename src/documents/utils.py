import hashlib
import logging
import shutil
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from os import utime
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from django.conf import settings
from PIL import Image

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db.models import QuerySet

_T = TypeVar("_T")
_M = TypeVar("_M", bound="Model")

# A function that wraps an iterable — typically used to inject a progress bar.
IterWrapper = Callable[[Iterable[_T]], Iterable[_T]]


def identity(iterable: Iterable[_T]) -> Iterable[_T]:
    """Return the iterable unchanged; the no-op default for IterWrapper."""
    return iterable


class QuerySetStream(Generic[_M]):
    """Stream a QuerySet via .iterator(chunk_size=...) instead of
    materializing it (plus any prefetch caches) all at once, while still
    supporting len() via count() so a progress bar wrapped around this
    (e.g. via IterWrapper) shows a real total instead of falling back to
    indeterminate.

    Plain QuerySet iteration (``for row in queryset:``) is not lazy: Django
    fetches every matching row in one query and caches the fully-hydrated
    result in the queryset's own ``_result_cache`` before yielding the
    first item -- wrapping that in a progress bar or any other iterable
    adapter doesn't change this, since none of them alter how the
    underlying queryset produces items. ``.iterator(chunk_size=...)`` is
    the specific Django API that bypasses ``_result_cache`` and streams
    from a server-side cursor instead, discarding each chunk once consumed
    (and, since Django 4.1, still honours ``prefetch_related``, running the
    prefetches one batch at a time rather than for the whole queryset).

    Subclass to layer additional per-batch work on top (see
    ``documents.search._backend._DocumentViewerStream``) by overriding
    ``__iter__`` -- ``__len__`` and the constructor are inherited for free.
    """

    def __init__(self, queryset: "QuerySet[_M]", *, chunk_size: int) -> None:
        self._queryset = queryset
        self._chunk_size = chunk_size

    def __len__(self) -> int:
        return self._queryset.count()

    def __iter__(self) -> Iterator[_M]:
        return iter(self._queryset.iterator(chunk_size=self._chunk_size))


def _coerce_to_path(
    source: Path | str,
    dest: Path | str,
) -> tuple[Path, Path]:
    return Path(source).resolve(), Path(dest).resolve()


def copy_basic_file_stats(source: Path | str, dest: Path | str) -> None:
    """
    Copies only the m_time and a_time attributes from source to destination.
    Both are expected to exist.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories and copystat doesn't allow disabling
    these copies.

    If there is a PermissionError, skip copying file stats.
    """
    source, dest = _coerce_to_path(source, dest)
    src_stat = source.stat()

    try:
        utime(dest, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))
    except PermissionError:
        pass


def copy_file_with_basic_stats(
    source: Path | str,
    dest: Path | str,
) -> None:
    """
    A sort of simpler copy2 that doesn't copy extended file attributes,
    only the access time and modified times from source to dest.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories.

    If there is a PermissionError (e.g., on ZFS with acltype=nfsv4)
    fall back to copyfile (data only).
    """
    source, dest = _coerce_to_path(source, dest)

    try:
        shutil.copy(source, dest)
    except PermissionError:
        shutil.copyfile(source, dest)

    copy_basic_file_stats(source, dest)


def maybe_override_pixel_limit() -> None:
    """
    Maybe overrides the PIL limit on pixel count, if configured to allow it
    """
    limit: float | int | None = settings.MAX_IMAGE_PIXELS
    if limit is not None and limit >= 0:
        pixel_count = limit
        if pixel_count == 0:
            pixel_count = None
        Image.MAX_IMAGE_PIXELS = pixel_count


def run_subprocess(
    arguments: list[str],
    env: dict[str, str] | None = None,
    logger: logging.Logger | None = None,
    *,
    check_exit_code: bool = True,
    log_stdout: bool = True,
    log_stderr: bool = True,
) -> CompletedProcess:
    """
    Runs a subprocess and logs its output, checking return code if requested
    """

    proc_name = arguments[0]

    completed_proc = run(args=arguments, env=env, capture_output=True, check=False)

    if logger:
        logger.info(f"{proc_name} exited {completed_proc.returncode}")

    if log_stdout and logger and completed_proc.stdout:
        stdout_str = (
            completed_proc.stdout.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stdout:")
        for line in stdout_str:
            logger.info(line)

    if log_stderr and logger and completed_proc.stderr:
        stderr_str = (
            completed_proc.stderr.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stderr:")
        for line in stderr_str:
            logger.warning(line)

    # Last, if requested, after logging outputs
    if check_exit_code:
        completed_proc.check_returncode()

    return completed_proc


def get_boolean(boolstr: str) -> bool:
    """
    Return a boolean value from a string representation.
    """
    return bool(boolstr.lower() in ("yes", "y", "1", "t", "true"))


def compute_checksum(path: Path, chunk_size: int = 65536) -> str:
    """
    Compute the SHA-256 checksum of a file.

    Reads the file in chunks to avoid loading the entire file into memory.

    Args:
        path (Path): Path to the file to hash.
        chunk_size (int, optional): Number of bytes to read per chunk.
            Defaults to 65536.

    Returns:
        str: Hexadecimal SHA-256 digest of the file contents.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
