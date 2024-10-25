import shutil
import tempfile
import time
import warnings
from collections import namedtuple
from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Iterator
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Any
from unittest import mock

import httpx
import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test import override_settings

from documents.consumer import ConsumerPlugin
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.parsers import ParseError
from documents.plugins.helpers import ProgressStatusOptions


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


def util_call_with_backoff(
    method_or_callable: Callable,
    args: list | tuple,
    *,
    skip_on_50x_err=True,
) -> tuple[bool, Any]:
    """
    For whatever reason, the images started during the test pipeline like to
    segfault sometimes, crash and otherwise fail randomly, when run with the
    exact files that usually pass.

    So, this function will retry the given method/function up to 3 times, with larger backoff
    periods between each attempt, in hopes the issue resolves itself during
    one attempt to parse.

    This will wait the following:
        - Attempt 1 - 20s following failure
        - Attempt 2 - 40s following failure
        - Attempt 3 - 80s following failure

    """
    result = None
    succeeded = False
    retry_time = 20.0
    retry_count = 0
    status_codes = []
    max_retry_count = 3

    while retry_count < max_retry_count and not succeeded:
        try:
            result = method_or_callable(*args)

            succeeded = True
        except ParseError as e:  # pragma: no cover
            cause_exec = e.__cause__
            if cause_exec is not None and isinstance(cause_exec, httpx.HTTPStatusError):
                status_codes.append(cause_exec.response.status_code)
                warnings.warn(
                    f"HTTP Exception for {cause_exec.request.url} - {cause_exec}",
                )
            else:
                warnings.warn(f"Unexpected error: {e}")
        except Exception as e:  # pragma: no cover
            warnings.warn(f"Unexpected error: {e}")

        retry_count = retry_count + 1

        time.sleep(retry_time)
        retry_time = retry_time * 2.0

    if (
        not succeeded
        and status_codes
        and skip_on_50x_err
        and all(httpx.codes.is_server_error(code) for code in status_codes)
    ):
        pytest.skip("Repeated HTTP 50x for service")  # pragma: no cover

    return succeeded, result


class DirectoriesMixin:
    """
    Creates and overrides settings for all folders and paths, then ensures
    they are cleaned up on exit
    """

    def setUp(self) -> None:
        self.dirs = setup_directories()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        remove_dirs(self.dirs)


class FileSystemAssertsMixin:
    """
    Utilities for checks various state information of the file system
    """

    def assertIsFile(self, path: PathLike | str):
        self.assertTrue(Path(path).resolve().is_file(), f"File does not exist: {path}")

    def assertIsNotFile(self, path: PathLike | str):
        self.assertFalse(Path(path).resolve().is_file(), f"File does exist: {path}")

    def assertIsDir(self, path: PathLike | str):
        self.assertTrue(Path(path).resolve().is_dir(), f"Dir does not exist: {path}")

    def assertIsNotDir(self, path: PathLike | str):
        self.assertFalse(Path(path).resolve().is_dir(), f"Dir does exist: {path}")

    def assertFilesEqual(
        self,
        path1: PathLike | str,
        path2: PathLike | str,
    ):
        path1 = Path(path1)
        path2 = Path(path2)
        import hashlib

        hash1 = hashlib.sha256(path1.read_bytes()).hexdigest()
        hash2 = hashlib.sha256(path2.read_bytes()).hexdigest()

        self.assertEqual(hash1, hash2, "File SHA256 mismatch")

    def assertFileCountInDir(self, path: PathLike | str, count: int):
        path = Path(path).resolve()
        self.assertTrue(path.is_dir(), f"Path {path} is not a directory")
        files = [x for x in path.iterdir() if x.is_file()]
        self.assertEqual(
            len(files),
            count,
            f"Path {path} contains {len(files)} files instead of {count} files",
        )


class ConsumerProgressMixin:
    """
    Mocks the Consumer _send_progress, preventing attempts to connect to Redis
    and allowing access to its calls for verification
    """

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
    ) -> tuple[ConsumableDocument, DocumentMetadataOverrides]:
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
    ) -> Iterator[tuple[ConsumableDocument, DocumentMetadataOverrides]]:
        """
        Iterates over all calls to the async task and returns the arguments
        """
        # Must be at least 1 call
        self.consume_file_mock.assert_called()

        for args, kwargs in self.consume_file_mock.call_args_list:
            input_doc, overrides = args

            yield (input_doc, overrides)

    def get_specific_consume_delay_call_args(
        self,
        index: int,
    ) -> tuple[ConsumableDocument, DocumentMetadataOverrides]:
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
    dependencies = None
    migrate_to = None
    auto_migrate = True

    def setUp(self):
        super().setUp()

        assert (
            self.migrate_from and self.migrate_to
        ), f"TestCase '{type(self).__name__}' must define migrate_from and migrate_to properties"
        self.migrate_from = [(self.app, self.migrate_from)]
        if self.dependencies is not None:
            self.migrate_from.extend(self.dependencies)
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


class SampleDirMixin:
    SAMPLE_DIR = Path(__file__).parent / "samples"

    BARCODE_SAMPLE_DIR = SAMPLE_DIR / "barcodes"


class GetConsumerMixin:
    @contextmanager
    def get_consumer(
        self,
        filepath: Path,
        overrides: DocumentMetadataOverrides | None = None,
        source: DocumentSource = DocumentSource.ConsumeFolder,
    ) -> Generator[ConsumerPlugin, None, None]:
        # Store this for verification
        self.status = DummyProgressManager(filepath.name, None)
        reader = ConsumerPlugin(
            ConsumableDocument(source, original_file=filepath),
            overrides or DocumentMetadataOverrides(),
            self.status,  # type: ignore
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        try:
            yield reader
        finally:
            reader.cleanup()


class DummyProgressManager:
    """
    A dummy handler for progress management that doesn't actually try to
    connect to Redis.  Payloads are stored for test assertions if needed.

    Use it with
      mock.patch("documents.tasks.ProgressManager", DummyProgressManager)
    """

    def __init__(self, filename: str, task_id: str | None = None) -> None:
        self.filename = filename
        self.task_id = task_id
        self.payloads = []

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def send_progress(
        self,
        status: ProgressStatusOptions,
        message: str,
        current_progress: int,
        max_progress: int,
        extra_args: dict[str, str | int] | None = None,
    ) -> None:
        # Ensure the layer is open
        self.open()

        payload = {
            "type": "status_update",
            "data": {
                "filename": self.filename,
                "task_id": self.task_id,
                "current_progress": current_progress,
                "max_progress": max_progress,
                "status": status,
                "message": message,
            },
        }
        if extra_args is not None:
            payload["data"].update(extra_args)

        self.payloads.append(payload)
