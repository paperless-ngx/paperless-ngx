import logging
import shutil
from os import utime
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run

from django.conf import settings
from PIL import Image


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
    these copies
    """
    source, dest = _coerce_to_path(source, dest)
    src_stat = source.stat()
    utime(dest, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))


def copy_file_with_basic_stats(
    source: Path | str,
    dest: Path | str,
) -> None:
    """
    A sort of simpler copy2 that doesn't copy extended file attributes,
    only the access time and modified times from source to dest.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories.
    """
    source, dest = _coerce_to_path(source, dest)

    shutil.copy(source, dest)
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
