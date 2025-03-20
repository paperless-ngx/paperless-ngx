import datetime as dt
import os
import shutil
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings
from pdfminer.high_level import extract_text
from pikepdf import Pdf

from documents import tasks
from documents.consumer import ConsumerError
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.double_sided import STAGING_FILE_NAME
from documents.double_sided import TIMEOUT_MINUTES
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DummyProgressManager
from documents.tests.utils import FileSystemAssertsMixin


@override_settings(
    CONSUMER_RECURSIVE=True,
    CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED=True,
)
class TestDoubleSided(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_DIR = Path(__file__).parent / "samples"

    def setUp(self):
        super().setUp()
        self.dirs.double_sided_dir = self.dirs.consumption_dir / "double-sided"
        self.dirs.double_sided_dir.mkdir()
        self.staging_file = self.dirs.scratch_dir / STAGING_FILE_NAME

    def consume_file(self, srcname, dstname: str | Path = "foo.pdf"):
        """
        Starts the consume process and also ensures the
        destination file does not exist afterwards
        """
        src = self.SAMPLE_DIR / srcname
        dst = self.dirs.double_sided_dir / dstname
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        with mock.patch(
            "documents.tasks.ProgressManager",
            DummyProgressManager,
        ):
            msg = tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=dst,
                ),
                None,
            )
        self.assertIsNotFile(dst)
        return msg

    def create_staging_file(self, src="double-sided-odd.pdf", datetime=None):
        shutil.copy(self.SAMPLE_DIR / src, self.staging_file)
        if datetime is None:
            datetime = dt.datetime.now()
        os.utime(str(self.staging_file), (datetime.timestamp(),) * 2)

    def test_odd_numbered_moved_to_staging(self):
        """
        GIVEN:
            - No staging file exists
        WHEN:
            - A file is copied into the double-sided consume directory
        THEN:
            - The file becomes the new staging file
            - The file in the consume directory gets removed
            - The staging file has the st_mtime set to now
            - The user gets informed
        """

        msg = self.consume_file("double-sided-odd.pdf")

        self.assertIsFile(self.staging_file)
        self.assertAlmostEqual(
            dt.datetime.fromtimestamp(self.staging_file.stat().st_mtime),
            dt.datetime.now(),
            delta=dt.timedelta(seconds=5),
        )
        self.assertIn("Received odd numbered pages", msg)

    def test_collation(self):
        """
        GIVEN:
            - A staging file not older than TIMEOUT_MINUTES with odd pages exists
        WHEN:
            - A file is copied into the double-sided consume directory
        THEN:
            - A new file containing the collated staging and uploaded file is
              created and put into the consume directory
            - The new file is named "foo-collated.pdf", where foo is the name of
              the second file
            - Both staging and uploaded file get deleted
            - The new file contains the pages in the correct order
        """

        self.create_staging_file()
        self.consume_file("double-sided-even.pdf", "some-random-name.pdf")

        target = self.dirs.consumption_dir / "some-random-name-collated.pdf"
        self.assertIsFile(target)
        self.assertIsNotFile(self.staging_file)
        self.assertRegex(
            extract_text(str(target)),
            r"(?s)"
            r"This is page 1.*This is page 2.*This is page 3.*"
            r"This is page 4.*This is page 5",
        )

    def test_staging_file_expiration(self):
        """
        GIVEN:
            - A staging file older than TIMEOUT_MINUTES exists
        WHEN:
            - A file is copied into the double-sided consume directory
        THEN:
            - It becomes the new staging file
        """

        self.create_staging_file(
            datetime=dt.datetime.now()
            - dt.timedelta(minutes=TIMEOUT_MINUTES, seconds=1),
        )
        msg = self.consume_file("double-sided-odd.pdf")
        self.assertIsFile(self.staging_file)
        self.assertIn("Received odd numbered pages", msg)

    def test_less_odd_pages_then_even_fails(self):
        """
        GIVEN:
            - A valid staging file
        WHEN:
            - A file is copied into the double-sided consume directory
              that has more pages than the staging file
        THEN:
            - Both files get removed
            - A ConsumerError exception is thrown
        """
        self.create_staging_file("simple.pdf")
        self.assertRaises(
            ConsumerError,
            self.consume_file,
            "double-sided-even.pdf",
        )
        self.assertIsNotFile(self.staging_file)

    @override_settings(CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT=True)
    def test_tiff_upload_enabled(self):
        """
        GIVEN:
            - CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT is true
            - No staging file exists
        WHEN:
            - A TIFF file gets uploaded into the double-sided
              consume dir
        THEN:
            - The file is converted into a PDF and moved to
              the staging file
        """
        self.consume_file("simple.tiff", "simple.tiff")
        self.assertIsFile(self.staging_file)
        # Ensure the file is a valid PDF by trying to read it
        Pdf.open(self.staging_file)

    @override_settings(CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT=False)
    def test_tiff_upload_disabled(self):
        """
        GIVEN:
            - CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT is false
            - No staging file exists
        WHEN:
            - A TIFF file gets uploaded into the double-sided
              consume dir
        THEN:
            - A ConsumerError is raised
        """
        self.assertRaises(
            ConsumerError,
            self.consume_file,
            "simple.tiff",
            "simple.tiff",
        )

    @override_settings(CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME="quux")
    def test_different_upload_dir_name(self):
        """
        GIVEN:
            - No staging file exists
            - CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME is set to quux
        WHEN:
            - A file is uploaded into the quux dir
        THEN:
            - A staging file is created
        """
        self.consume_file("double-sided-odd.pdf", Path("..") / "quux" / "foo.pdf")
        self.assertIsFile(self.staging_file)

    def test_only_double_sided_dir_is_handled(self):
        """
        GIVEN:
            - No staging file exists
        WHEN:
            - A file is uploaded into the normal consumption dir
        THEN:
            - The file is processed as normal
        """
        msg = self.consume_file("simple.pdf", Path("..") / "simple.pdf")
        self.assertIsNotFile(self.staging_file)
        self.assertRegex(msg, r"Success. New document id \d+ created")

    def test_subdirectory_upload(self):
        """
        GIVEN:
            - A staging file exists
        WHEN:
            - A file gets uploaded into foo/bar/double-sided
              or double-sided/foo/bar
        THEN:
            - The collated file gets put into foo/bar
        """
        for path in [
            Path("foo") / "bar" / "double-sided",
            Path("double-sided") / "foo" / "bar",
        ]:
            with self.subTest(path=path):
                # Ensure we get fresh directories for each run
                self.tearDown()
                self.setUp()

                self.create_staging_file()
                self.consume_file("double-sided-odd.pdf", path / "foo.pdf")
                self.assertIsFile(
                    self.dirs.consumption_dir / "foo" / "bar" / "foo-collated.pdf",
                )

    @override_settings(CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED=False)
    def test_disabled_double_sided_dir_upload(self):
        """
        GIVEN:
            - CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED is false
        WHEN:
            - A file is uploaded into the double-sided directory
        THEN:
            - The file is processed like a normal upload
        """
        msg = self.consume_file("simple.pdf")
        self.assertIsNotFile(self.staging_file)
        self.assertRegex(msg, r"Success. New document id \d+ created")
