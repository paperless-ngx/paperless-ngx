import shutil
from os import utime
from pathlib import Path
from typing import Optional
from typing import Union

from django.conf import settings
from PIL import Image


def _coerce_to_path(
    source: Union[Path, str],
    dest: Union[Path, str],
) -> tuple[Path, Path]:
    return Path(source).resolve(), Path(dest).resolve()


def copy_basic_file_stats(source: Union[Path, str], dest: Union[Path, str]) -> None:
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
    source: Union[Path, str],
    dest: Union[Path, str],
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
    limit: Optional[Union[float, int]] = settings.MAX_IMAGE_PIXELS
    if limit is not None and limit >= 0:
        pixel_count = limit
        if pixel_count == 0:
            pixel_count = None
        Image.MAX_IMAGE_PIXELS = pixel_count
