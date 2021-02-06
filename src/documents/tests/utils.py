import os
import shutil
import tempfile
from collections import namedtuple
from contextlib import contextmanager

from django.test import override_settings


def setup_directories():

    dirs = namedtuple("Dirs", ())

    dirs.data_dir = tempfile.mkdtemp()
    dirs.scratch_dir = tempfile.mkdtemp()
    dirs.media_dir = tempfile.mkdtemp()
    dirs.consumption_dir = tempfile.mkdtemp()
    dirs.index_dir = os.path.join(dirs.data_dir, "index")
    dirs.originals_dir = os.path.join(dirs.media_dir, "documents", "originals")
    dirs.thumbnail_dir = os.path.join(dirs.media_dir, "documents", "thumbnails")
    dirs.archive_dir = os.path.join(dirs.media_dir, "documents", "archive")
    dirs.logging_dir = os.path.join(dirs.data_dir, "log")

    os.makedirs(dirs.index_dir, exist_ok=True)
    os.makedirs(dirs.originals_dir, exist_ok=True)
    os.makedirs(dirs.thumbnail_dir, exist_ok=True)
    os.makedirs(dirs.archive_dir, exist_ok=True)

    os.makedirs(dirs.logging_dir, exist_ok=True)

    dirs.settings_override = override_settings(
        DATA_DIR=dirs.data_dir,
        SCRATCH_DIR=dirs.scratch_dir,
        MEDIA_ROOT=dirs.media_dir,
        ORIGINALS_DIR=dirs.originals_dir,
        THUMBNAIL_DIR=dirs.thumbnail_dir,
        ARCHIVE_DIR=dirs.archive_dir,
        CONSUMPTION_DIR=dirs.consumption_dir,
        LOGGING_DIR=dirs.logging_dir,
        INDEX_DIR=dirs.index_dir,
        MODEL_FILE=os.path.join(dirs.data_dir, "classification_model.pickle"),
        MEDIA_LOCK=os.path.join(dirs.media_dir, "media.lock")

    )
    dirs.settings_override.enable()

    return dirs


def remove_dirs(dirs):
    shutil.rmtree(dirs.media_dir, ignore_errors=True)
    shutil.rmtree(dirs.data_dir, ignore_errors=True)
    shutil.rmtree(dirs.scratch_dir, ignore_errors=True)
    shutil.rmtree(dirs.consumption_dir, ignore_errors=True)
    dirs.settings_override.disable()


@contextmanager
def paperless_environment():
    dirs = None
    try:
        dirs = setup_directories()
        yield dirs
    finally:
        if dirs:
            remove_dirs(dirs)


class DirectoriesMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dirs = None

    def setUp(self) -> None:
        self.dirs = setup_directories()
        super(DirectoriesMixin, self).setUp()

    def tearDown(self) -> None:
        super(DirectoriesMixin, self).tearDown()
        remove_dirs(self.dirs)
