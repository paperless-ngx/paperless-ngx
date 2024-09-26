import importlib
import shutil
import tempfile
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from unittest import mock

from django.test import override_settings

from documents.tests.utils import TestMigrations

# https://github.com/python/cpython/issues/100950
migration_1037_obj = importlib.import_module(
    "documents.migrations.1037_webp_encrypted_thumbnail_conversion",
)


@override_settings(PASSPHRASE="test")
@mock.patch(
    f"{__name__}.migration_1037_obj.multiprocessing.pool.Pool.map",
)
@mock.patch(f"{__name__}.migration_1037_obj.run_convert")
class TestMigrateToEncrytpedWebPThumbnails(TestMigrations):
    migrate_from = (
        "1022_paperlesstask_squashed_1036_alter_savedviewfilterrule_rule_type"
    )
    migrate_to = "1037_webp_encrypted_thumbnail_conversion"
    auto_migrate = False

    def pretend_convert_output(self, *args, **kwargs):
        """
        Pretends to do the conversion, by copying the input file
        to the output file
        """
        shutil.copy2(
            Path(kwargs["input_file"].rstrip("[0]")),
            Path(kwargs["output_file"]),
        )

    def pretend_map(self, func: Callable, iterable: Iterable):
        """
        Pretends to be the map of a multiprocessing.Pool, but secretly does
        everything in series
        """
        for item in iterable:
            func(item)

    def create_dummy_thumbnails(
        self,
        thumb_dir: Path,
        ext: str,
        count: int,
        start_count: int = 0,
    ):
        """
        Helper to create a certain count of files of given extension in a given directory
        """
        for idx in range(count):
            (Path(thumb_dir) / Path(f"{start_count + idx:07}.{ext}")).touch()
        # Triple check expected files exist
        self.assert_file_count_by_extension(ext, thumb_dir, count)

    def create_webp_thumbnail_files(
        self,
        thumb_dir: Path,
        count: int,
        start_count: int = 0,
    ):
        """
        Creates a dummy WebP thumbnail file in the given directory, based on
        the database Document
        """
        self.create_dummy_thumbnails(thumb_dir, "webp", count, start_count)

    def create_encrypted_webp_thumbnail_files(
        self,
        thumb_dir: Path,
        count: int,
        start_count: int = 0,
    ):
        """
        Creates a dummy encrypted WebP thumbnail file in the given directory, based on
        the database Document
        """
        self.create_dummy_thumbnails(thumb_dir, "webp.gpg", count, start_count)

    def create_png_thumbnail_files(
        self,
        thumb_dir: Path,
        count: int,
        start_count: int = 0,
    ):
        """
        Creates a dummy PNG thumbnail file in the given directory, based on
        the database Document
        """

        self.create_dummy_thumbnails(thumb_dir, "png", count, start_count)

    def create_encrypted_png_thumbnail_files(
        self,
        thumb_dir: Path,
        count: int,
        start_count: int = 0,
    ):
        """
        Creates a dummy encrypted PNG thumbnail file in the given directory, based on
        the database Document
        """

        self.create_dummy_thumbnails(thumb_dir, "png.gpg", count, start_count)

    def assert_file_count_by_extension(
        self,
        ext: str,
        dir: str | Path,
        expected_count: int,
    ):
        """
        Helper to assert a certain count of given extension files in given directory
        """
        if not isinstance(dir, Path):
            dir = Path(dir)
        matching_files = list(dir.glob(f"*.{ext}"))
        self.assertEqual(len(matching_files), expected_count)

    def assert_encrypted_png_file_count(self, dir: Path, expected_count: int):
        """
        Helper to assert a certain count of excrypted PNG extension files in given directory
        """
        self.assert_file_count_by_extension("png.gpg", dir, expected_count)

    def assert_encrypted_webp_file_count(self, dir: Path, expected_count: int):
        """
        Helper to assert a certain count of encrypted WebP extension files in given directory
        """
        self.assert_file_count_by_extension("webp.gpg", dir, expected_count)

    def assert_webp_file_count(self, dir: Path, expected_count: int):
        """
        Helper to assert a certain count of WebP extension files in given directory
        """
        self.assert_file_count_by_extension("webp", dir, expected_count)

    def assert_png_file_count(self, dir: Path, expected_count: int):
        """
        Helper to assert a certain count of PNG extension files in given directory
        """
        self.assert_file_count_by_extension("png", dir, expected_count)

    def setUp(self):
        self.thumbnail_dir = Path(tempfile.mkdtemp()).resolve()

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree(self.thumbnail_dir)

        return super().tearDown()

    def test_do_nothing_if_converted(
        self,
        run_convert_mock: mock.MagicMock,
        map_mock: mock.MagicMock,
    ):
        """
        GIVEN:
            - Encrypted document exists with existing encrypted WebP thumbnail path
        WHEN:
            - Migration is attempted
        THEN:
            - Nothing is converted
        """
        map_mock.side_effect = self.pretend_map

        with override_settings(
            THUMBNAIL_DIR=self.thumbnail_dir,
        ):
            self.create_encrypted_webp_thumbnail_files(self.thumbnail_dir, 3)

            self.performMigration()
            run_convert_mock.assert_not_called()

            self.assert_encrypted_webp_file_count(self.thumbnail_dir, 3)

    def test_convert_thumbnails(
        self,
        run_convert_mock: mock.MagicMock,
        map_mock: mock.MagicMock,
    ):
        """
        GIVEN:
            - Encrypted documents exist with PNG thumbnail
        WHEN:
            - Migration is attempted
        THEN:
            - Thumbnails are converted to webp & re-encrypted
        """
        map_mock.side_effect = self.pretend_map
        run_convert_mock.side_effect = self.pretend_convert_output

        with override_settings(
            THUMBNAIL_DIR=self.thumbnail_dir,
        ):
            self.create_encrypted_png_thumbnail_files(self.thumbnail_dir, 3)

            self.performMigration()

            run_convert_mock.assert_called()
            self.assertEqual(run_convert_mock.call_count, 3)

            self.assert_encrypted_webp_file_count(self.thumbnail_dir, 3)

    def test_convert_errors_out(
        self,
        run_convert_mock: mock.MagicMock,
        map_mock: mock.MagicMock,
    ):
        """
        GIVEN:
            - Encrypted document exists with PNG thumbnail
        WHEN:
            - Migration is attempted, but raises an exception
        THEN:
            - Single thumbnail is converted
        """
        map_mock.side_effect = self.pretend_map
        run_convert_mock.side_effect = OSError

        with override_settings(
            THUMBNAIL_DIR=self.thumbnail_dir,
        ):
            self.create_encrypted_png_thumbnail_files(self.thumbnail_dir, 3)

            self.performMigration()

            run_convert_mock.assert_called()
            self.assertEqual(run_convert_mock.call_count, 3)

            self.assert_encrypted_png_file_count(self.thumbnail_dir, 3)

    def test_convert_mixed(
        self,
        run_convert_mock: mock.MagicMock,
        map_mock: mock.MagicMock,
    ):
        """
        GIVEN:
            - Documents exist with PNG, encrypted PNG and WebP thumbnails
        WHEN:
            - Migration is attempted
        THEN:
            - Only encrypted PNG thumbnails are converted
        """
        map_mock.side_effect = self.pretend_map
        run_convert_mock.side_effect = self.pretend_convert_output

        with override_settings(
            THUMBNAIL_DIR=self.thumbnail_dir,
        ):
            self.create_png_thumbnail_files(self.thumbnail_dir, 3)
            self.create_encrypted_png_thumbnail_files(
                self.thumbnail_dir,
                3,
                start_count=3,
            )
            self.create_webp_thumbnail_files(self.thumbnail_dir, 2, start_count=6)
            self.create_encrypted_webp_thumbnail_files(
                self.thumbnail_dir,
                3,
                start_count=8,
            )

            self.performMigration()

            run_convert_mock.assert_called()
            self.assertEqual(run_convert_mock.call_count, 3)

            self.assert_png_file_count(self.thumbnail_dir, 3)
            self.assert_encrypted_webp_file_count(self.thumbnail_dir, 6)
            self.assert_webp_file_count(self.thumbnail_dir, 2)
            self.assert_encrypted_png_file_count(self.thumbnail_dir, 0)
