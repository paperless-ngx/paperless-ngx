import shutil
import tempfile
from collections import namedtuple
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Iterator
from typing import Tuple
from typing import Union
from unittest import mock

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test import override_settings

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides


def setup_directories():
    dirs = namedtuple("Dirs", ())

    dirs.data_dir = Path(tempfile.mkdtemp())
    dirs.scratch_dir = Path(tempfile.mkdtemp())
    dirs.media_dir = Path(tempfile.mkdtemp())
    dirs.consumption_dir = Path(tempfile.mkdtemp())
    dirs.static_dir = Path(tempfile.mkdtemp())
    dirs.index_dir = dirs.data_dir / "index"
    dirs.originals_dir = dirs.media_dir / "documents" / "originals"
    dirs.thumbnail_dir = dirs.media_dir / "documents" / "thumbnails"
    dirs.archive_dir = dirs.media_dir / "documents" / "archive"
    dirs.logging_dir = dirs.data_dir / "log"

    dirs.index_dir.mkdir(parents=True, exist_ok=True)
    dirs.originals_dir.mkdir(parents=True, exist_ok=True)
    dirs.thumbnail_dir.mkdir(parents=True, exist_ok=True)
    dirs.archive_dir.mkdir(parents=True, exist_ok=True)
    dirs.logging_dir.mkdir(parents=True, exist_ok=True)

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
        STATIC_ROOT=dirs.static_dir,
        MODEL_FILE=dirs.data_dir / "classification_model.pickle",
        MEDIA_LOCK=dirs.media_dir / "media.lock",
    )
    dirs.settings_override.enable()

    return dirs


def remove_dirs(dirs):
    shutil.rmtree(dirs.media_dir, ignore_errors=True)
    shutil.rmtree(dirs.data_dir, ignore_errors=True)
    shutil.rmtree(dirs.scratch_dir, ignore_errors=True)
    shutil.rmtree(dirs.consumption_dir, ignore_errors=True)
    shutil.rmtree(dirs.static_dir, ignore_errors=True)
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
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        remove_dirs(self.dirs)


class FileSystemAssertsMixin:
    def assertIsFile(self, path: Union[PathLike, str]):
        self.assertTrue(Path(path).resolve().is_file(), f"File does not exist: {path}")

    def assertIsNotFile(self, path: Union[PathLike, str]):
        self.assertFalse(Path(path).resolve().is_file(), f"File does exist: {path}")

    def assertIsDir(self, path: Union[PathLike, str]):
        self.assertTrue(Path(path).resolve().is_dir(), f"Dir does not exist: {path}")

    def assertIsNotDir(self, path: Union[PathLike, str]):
        self.assertFalse(Path(path).resolve().is_dir(), f"Dir does exist: {path}")


class ConsumerProgressMixin:
    def setUp(self) -> None:
        self.send_progress_patcher = mock.patch(
            "documents.consumer.Consumer._send_progress",
        )
        self.send_progress_mock = self.send_progress_patcher.start()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.send_progress_patcher.stop()


class DocumentConsumeDelayMixin:
    """
    Provides mocking of the consume_file asynchronous task and useful utilities
    for decoding its arguments
    """

    def setUp(self) -> None:
        self.consume_file_patcher = mock.patch("documents.tasks.consume_file.delay")
        self.consume_file_mock = self.consume_file_patcher.start()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.consume_file_patcher.stop()

    def get_last_consume_delay_call_args(
        self,
    ) -> Tuple[ConsumableDocument, DocumentMetadataOverrides]:
        """
        Returns the most recent arguments to the async task
        """
        # Must be at least 1 call
        self.consume_file_mock.assert_called()

        args, _ = self.consume_file_mock.call_args
        input_doc, overrides = args

        return (input_doc, overrides)

    def get_all_consume_delay_call_args(
        self,
    ) -> Iterator[Tuple[ConsumableDocument, DocumentMetadataOverrides]]:
        """
        Iterates over all calls to the async task and returns the arguments
        """

        for args, _ in self.consume_file_mock.call_args_list:
            input_doc, overrides = args

            yield (input_doc, overrides)

    def get_specific_consume_delay_call_args(
        self,
        index: int,
    ) -> Iterator[Tuple[ConsumableDocument, DocumentMetadataOverrides]]:
        """
        Returns the arguments of a specific call to the async task
        """
        # Must be at least 1 call
        self.consume_file_mock.assert_called()

        args, _ = self.consume_file_mock.call_args_list[index]
        input_doc, overrides = args

        return (input_doc, overrides)


class TestMigrations(TransactionTestCase):
    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None
    auto_migrate = True

    def setUp(self):
        super().setUp()

        assert (
            self.migrate_from and self.migrate_to
        ), "TestCase '{}' must define migrate_from and migrate_to properties".format(
            type(self).__name__,
        )
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        self.apps = old_apps

        if self.auto_migrate:
            self.performMigration()

    def performMigration(self):
        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass
