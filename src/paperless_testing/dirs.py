"""The Paperless-ngx temp directory layout, stated once.

``build_paperless_dirs`` owns where things go and creates them.
``dirs_settings`` owns the mapping onto Django setting names and is pure.
Everything else in the test suite is a caller of these two.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import TypedDict

from django.test import override_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class PaperlessDirs:
    """Standard Paperless-ngx directory layout for tests."""

    data_dir: Path
    scratch_dir: Path
    media_dir: Path
    consumption_dir: Path
    static_dir: Path
    index_dir: Path
    originals_dir: Path
    thumbnail_dir: Path
    archive_dir: Path
    logging_dir: Path
    model_file: Path
    media_lock: Path


class DirSettings(TypedDict):
    """The Django settings the layout above maps onto."""

    DATA_DIR: Path
    SCRATCH_DIR: Path
    MEDIA_ROOT: Path
    ORIGINALS_DIR: Path
    THUMBNAIL_DIR: Path
    ARCHIVE_DIR: Path
    CONSUMPTION_DIR: Path
    LOGGING_DIR: Path
    INDEX_DIR: Path
    STATIC_ROOT: Path
    MODEL_FILE: Path
    MEDIA_LOCK: Path


def build_paperless_dirs(root: Path) -> PaperlessDirs:
    """Compute the layout under root and create the directories."""
    data_dir = root / "data"
    media_dir = root / "media"
    documents_dir = media_dir / "documents"

    dirs = PaperlessDirs(
        data_dir=data_dir,
        scratch_dir=root / "scratch",
        media_dir=media_dir,
        consumption_dir=root / "consume",
        static_dir=root / "static",
        index_dir=data_dir / "index",
        originals_dir=documents_dir / "originals",
        thumbnail_dir=documents_dir / "thumbnails",
        archive_dir=documents_dir / "archive",
        logging_dir=data_dir / "log",
        model_file=data_dir / "classification_model.pickle",
        media_lock=media_dir / "media.lock",
    )

    for directory in (
        dirs.data_dir,
        dirs.scratch_dir,
        dirs.media_dir,
        dirs.consumption_dir,
        dirs.static_dir,
        dirs.index_dir,
        dirs.originals_dir,
        dirs.thumbnail_dir,
        dirs.archive_dir,
        dirs.logging_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return dirs


def dirs_settings(dirs: PaperlessDirs) -> DirSettings:
    """Map the layout onto Django setting names."""
    return DirSettings(
        DATA_DIR=dirs.data_dir,
        SCRATCH_DIR=dirs.scratch_dir,
        MEDIA_ROOT=dirs.media_dir,
        ORIGINALS_DIR=dirs.originals_dir,
        THUMBNAIL_DIR=dirs.thumbnail_dir,
        ARCHIVE_DIR=dirs.archive_dir,
        CONSUMPTION_DIR=dirs.consumption_dir,
        LOGGING_DIR=dirs.logging_dir,
        INDEX_DIR=dirs.index_dir,
        STATIC_ROOT=dirs.static_dir,
        MODEL_FILE=dirs.model_file,
        MEDIA_LOCK=dirs.media_lock,
    )


@contextmanager
def paperless_environment() -> Iterator[PaperlessDirs]:
    """A second, isolated environment for the duration of the block.

    Only for tests needing a fresh environment part way through a test body,
    which a fixture cannot provide. Everything else uses the paperless_dirs
    fixture.
    """
    from documents.search import reset_backend

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        dirs = build_paperless_dirs(Path(tmp))
        with override_settings(**dirs_settings(dirs)):
            reset_backend()
            try:
                yield dirs
            finally:
                reset_backend()
