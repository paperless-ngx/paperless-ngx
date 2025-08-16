import logging
import re
import shutil
from os import utime
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run

from django.conf import settings
from django.db import connection
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


def escape_like_pattern(value, escape_char="\\"):
    return re.sub(r"([\\%_])", lambda m: escape_char + m.group(1), value)


ESCAPE_SQL_RE = re.compile(r"[:\";_\}>ʼ\\\.‘\[/<'\?%’,@\&=\*\~\|\{\)`\+\^\(\#\]!\-\$]")  # noqa: RUF001


def escape_fulltext(value):
    if connection.vendor == "postgresql":
        # In PostgreSQL, escape tsquery special characters: & | ! : * ( ) ' " \
        # WIP: Not needed for phraseto_tsquery
        return value
    else:
        return ESCAPE_SQL_RE.sub(" ", value)


def split_fulltext_tokens(value):
    return [token for token in escape_fulltext(value).split()]


NOT_FT_COMPATIBLE = re.compile(
    # CJK ideographs
    r"[\u4E00-\u9FFF"  # CJK Unified Ideographs
    r"\u3400-\u4DBF"  # CJK Extension A
    r"\u3040-\u30ff"  # Hiragana / Japanese
    r"\uAC00-\uD7AF"  # Hangul / Korean
    r"]",
)


def fulltext_compatible(text: str, threshold=0.5):
    """
    Check that a given text can be searched against a classic full-text SQL index.

    The text must have a ratio of supported characters above the given threshold.
    For instance, CJK characters are not natively supported by most SQL databases.
    """
    text = escape_fulltext(text)
    incompatible_chars = len(NOT_FT_COMPATIBLE.findall(text))
    total_relevant_chars = (
        sum(1 for c in text if not c.isspace() and not NOT_FT_COMPATIBLE.match(c))
        + incompatible_chars
    )
    if total_relevant_chars == 0:
        return False
    return (incompatible_chars / total_relevant_chars) < threshold


# Default keyword length to trigger fulltext search in MariaDB.
# Default used to be 4 (ft_min_word_length) for MyISAM storage engine,
# but it is 3 (innodb_ft_min_token_size) for InnoDB.
FULLTEXT_MINIMAL_TOKEN_LENGTH = 3
