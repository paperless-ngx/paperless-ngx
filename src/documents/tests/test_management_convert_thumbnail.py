import filecmp
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.test import TestCase
from documents.models import Document


class TestConvertThumbnails(TestCase):
    def call_command(self):
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "convert_thumbnails",
            "--no-color",
            stdout=stdout,
            stderr=stderr,
        )
        return stdout.getvalue(), stderr.getvalue()

    def setUp(self):
        """
        Creates a document in the database
        """
        super().setUp()

        self.doc = Document.objects.create(
            pk=1,
            checksum="A",
            title="A",
            content="first document",
            mime_type="application/pdf",
        )
        self.doc.save()

    def pretend_convert_output(self, *args, **kwargs):
        """
        Pretends to do the conversion, by copying the input file
        to the output file
        """
        shutil.copy2(
            Path(kwargs["input_file"].rstrip("[0]")),
            Path(kwargs["output_file"]),
        )

    def create_webp_thumbnail_file(self, thumb_dir):
        """
        Creates a dummy WebP thumbnail file in the given directory, based on
        the database Document
        """
        thumb_file = Path(thumb_dir) / Path(f"{self.doc.pk:07}.webp")
        thumb_file.write_text("this is a dummy webp file")
        return thumb_file

    def create_png_thumbnail_file(self, thumb_dir):
        """
        Creates a dummy PNG thumbnail file in the given directory, based on
        the database Document
        """
        thumb_file = Path(thumb_dir) / Path(f"{self.doc.pk:07}.png")
        thumb_file.write_text("this is a dummy png file")
        return thumb_file

    @mock.patch("documents.management.commands.convert_thumbnails.run_convert")
    def test_do_nothing_if_converted(self, run_convert_mock):
        """
        GIVEN:
            - Document exists with default WebP thumbnail path
        WHEN:
            - Thumbnail conversion is attempted
        THEN:
            - Nothing is converted
        """

        stdout, _ = self.call_command()
        run_convert_mock.assert_not_called()
        self.assertIn("Converting all PNG thumbnails to WebP", stdout)

    @mock.patch("documents.management.commands.convert_thumbnails.run_convert")
    def test_convert_single_thumbnail(self, run_convert_mock):
        """
        GIVEN:
            - Document exists with PNG thumbnail
        WHEN:
            - Thumbnail conversion is attempted
        THEN:
            - Single thumbnail is converted
        """

        run_convert_mock.side_effect = self.pretend_convert_output

        with tempfile.TemporaryDirectory() as thumbnail_dir:

            with override_settings(
                THUMBNAIL_DIR=thumbnail_dir,
            ):

                thumb_file = self.create_png_thumbnail_file(thumbnail_dir)

                stdout, _ = self.call_command()

                run_convert_mock.assert_called_once()
                self.assertIn(f"{thumb_file}", stdout)
                self.assertIn("Conversion to WebP completed", stdout)

                self.assertFalse(thumb_file.exists())
                self.assertTrue(thumb_file.with_suffix(".webp").exists())

    @mock.patch("documents.management.commands.convert_thumbnails.run_convert")
    def test_convert_errors_out(self, run_convert_mock):
        """
        GIVEN:
            - Document exists with PNG thumbnail
        WHEN:
            - Thumbnail conversion is attempted, but raises an exception
        THEN:
            - Single thumbnail is converted
        """

        run_convert_mock.side_effect = OSError

        with tempfile.TemporaryDirectory() as thumbnail_dir:

            with override_settings(
                THUMBNAIL_DIR=thumbnail_dir,
            ):

                thumb_file = self.create_png_thumbnail_file(thumbnail_dir)

                _, stderr = self.call_command()

                run_convert_mock.assert_called_once()
                self.assertIn("Error converting thumbnail", stderr)
                self.assertTrue(thumb_file.exists())
