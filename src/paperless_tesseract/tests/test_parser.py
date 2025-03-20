import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings
from ocrmypdf import SubprocessOutputError

from documents.parsers import ParseError
from documents.parsers import run_convert
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_tesseract.parsers import RasterisedDocumentParser
from paperless_tesseract.parsers import post_process_text


class TestParser(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_FILES = Path(__file__).resolve().parent / "samples"

    def assertContainsStrings(self, content, strings):
        # Asserts that all strings appear in content, in the given order.
        indices = []
        for s in strings:
            if s in content:
                indices.append(content.index(s))
            else:
                self.fail(f"'{s}' is not in '{content}'")
        self.assertListEqual(indices, sorted(indices))

    def test_post_process_text(self):
        text_cases = [
            ("simple     string", "simple string"),
            ("simple    newline\n   testing string", "simple newline\ntesting string"),
            (
                "utf-8   строка с пробелами в конце  ",
                "utf-8 строка с пробелами в конце",
            ),
        ]

        for source, result in text_cases:
            actual_result = post_process_text(source)
            self.assertEqual(
                result,
                actual_result,
                f"strip_exceess_whitespace({source}) != '{result}', but '{actual_result}'",
            )

    def test_get_text_from_pdf(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        text = parser.extract_text(
            None,
            self.SAMPLE_FILES / "simple-digital.pdf",
        )

        self.assertContainsStrings(text.strip(), ["This is a test document."])

    def test_get_page_count(self):
        """
        GIVEN:
            - PDF file with a single page
            - PDF file with multiple pages
        WHEN:
            - The number of pages is requested
        THEN:
            - The method returns 1 as the expected number of pages
            - The method returns the correct number of pages (6)
        """
        parser = RasterisedDocumentParser(uuid.uuid4())
        page_count = parser.get_page_count(
            os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"),
            "application/pdf",
        )
        self.assertEqual(page_count, 1)

        page_count = parser.get_page_count(
            os.path.join(self.SAMPLE_FILES, "multi-page-mixed.pdf"),
            "application/pdf",
        )
        self.assertEqual(page_count, 6)

    def test_get_page_count_password_protected(self):
        """
        GIVEN:
            - Password protected PDF file
        WHEN:
            - The number of pages is requested
        THEN:
            - The method returns None
        """
        parser = RasterisedDocumentParser(uuid.uuid4())
        with self.assertLogs("paperless.parsing.tesseract", level="WARNING") as cm:
            page_count = parser.get_page_count(
                os.path.join(self.SAMPLE_FILES, "password-protected.pdf"),
                "application/pdf",
            )
            self.assertEqual(page_count, None)
            self.assertIn("Unable to determine PDF page count", cm.output[0])

    def test_thumbnail(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(thumb)

    @mock.patch("documents.parsers.run_convert")
    def test_thumbnail_fallback(self, m):
        def call_convert(input_file, output_file, **kwargs):
            if ".pdf" in input_file:
                raise ParseError("Does not compute.")
            else:
                run_convert(input_file=input_file, output_file=output_file, **kwargs)

        m.side_effect = call_convert

        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(thumb)

    def test_thumbnail_encrypted(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "encrypted.pdf"),
            "application/pdf",
        )
        self.assertIsFile(thumb)

    def test_get_dpi(self):
        parser = RasterisedDocumentParser(None)

        dpi = parser.get_dpi(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"))
        self.assertEqual(dpi, None)

        dpi = parser.get_dpi(os.path.join(self.SAMPLE_FILES, "simple.png"))
        self.assertEqual(dpi, 72)

    def test_simple_digital(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"),
            "application/pdf",
        )

        self.assertIsFile(parser.archive_path)

        self.assertContainsStrings(parser.get_text(), ["This is a test document."])

    def test_with_form(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "with-form.pdf"),
            "application/pdf",
        )

        self.assertIsFile(parser.archive_path)

        self.assertContainsStrings(
            parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    @override_settings(OCR_MODE="redo")
    def test_with_form_error(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "with-form.pdf"),
            "application/pdf",
        )

        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    @override_settings(OCR_MODE="skip")
    def test_signed(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "signed.pdf"), "application/pdf")

        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text(),
            [
                "This is a digitally signed PDF, created with Acrobat Pro for the Paperless project to enable",
                "automated testing of signed/encrypted PDFs",
            ],
        )

    @override_settings(OCR_MODE="skip")
    def test_encrypted(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "encrypted.pdf"),
            "application/pdf",
        )

        self.assertIsNone(parser.archive_path)
        self.assertEqual(parser.get_text(), "")

    @override_settings(OCR_MODE="redo")
    def test_with_form_error_notext(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "with-form.pdf"),
            "application/pdf",
        )

        self.assertContainsStrings(
            parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    @override_settings(OCR_MODE="force")
    def test_with_form_force(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "with-form.pdf"),
            "application/pdf",
        )

        self.assertContainsStrings(
            parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    def test_image_simple(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.png"), "image/png")

        self.assertIsFile(parser.archive_path)

        self.assertContainsStrings(parser.get_text(), ["This is a test document."])

    def test_image_simple_alpha(self):
        parser = RasterisedDocumentParser(None)

        with tempfile.TemporaryDirectory() as tempdir:
            # Copy sample file to temp directory, as the parsing changes the file
            # and this makes it modified to Git
            sample_file = os.path.join(self.SAMPLE_FILES, "simple-alpha.png")
            dest_file = os.path.join(tempdir, "simple-alpha.png")
            shutil.copy(sample_file, dest_file)

            parser.parse(dest_file, "image/png")

            self.assertIsFile(parser.archive_path)

            self.assertContainsStrings(parser.get_text(), ["This is a test document."])

    def test_image_calc_a4_dpi(self):
        parser = RasterisedDocumentParser(None)

        dpi = parser.calculate_a4_dpi(
            os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"),
        )

        self.assertEqual(dpi, 62)

    @mock.patch("paperless_tesseract.parsers.RasterisedDocumentParser.calculate_a4_dpi")
    def test_image_dpi_fail(self, m):
        m.return_value = None
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(
                os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"),
                "image/png",
            )

        self.assertRaises(ParseError, f)

    @override_settings(OCR_IMAGE_DPI=72, MAX_IMAGE_PIXELS=0)
    def test_image_no_dpi_default(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"), "image/png")

        self.assertIsFile(parser.archive_path)

        self.assertContainsStrings(
            parser.get_text().lower(),
            ["this is a test document."],
        )

    def test_multi_page(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_PAGES=2, OCR_MODE="skip")
    def test_multi_page_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_pages_redo(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_PAGES=2, OCR_MODE="force")
    def test_multi_page_pages_force(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_MODE="skip")
    def test_multi_page_analog_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_analog_pages_redo(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR of only pages 1 and 2 requested
            - OCR mode set to redo
        WHEN:
            - Document is parsed
        THEN:
            - Text of page 1 and 2 extracted
            - An archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2"])
        self.assertNotIn("page 3", parser.get_text().lower())

    @override_settings(OCR_PAGES=1, OCR_MODE="force")
    def test_multi_page_analog_pages_force(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR of only page 1 requested
            - OCR mode set to force
        WHEN:
            - Document is parsed
        THEN:
            - Only text of page 1 is extracted
            - An archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(parser.get_text().lower(), ["page 1"])
        self.assertNotIn("page 2", parser.get_text().lower())
        self.assertNotIn("page 3", parser.get_text().lower())

    @override_settings(OCR_MODE="skip_noarchive")
    def test_skip_noarchive_withtext(self):
        """
        GIVEN:
            - File with existing text layer
            - OCR mode set to skip_noarchive
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - No archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_MODE="skip_noarchive")
    def test_skip_noarchive_notext(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR mode set to skip_noarchive
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - An archive file is created with the OCRd text
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )

        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

        self.assertIsNotNone(parser.archive_path)

    @override_settings(OCR_SKIP_ARCHIVE_FILE="never")
    def test_skip_archive_never_withtext(self):
        """
        GIVEN:
            - File with existing text layer
            - OCR_SKIP_ARCHIVE_FILE set to never
        WHEN:
            - Document is parsed
        THEN:
            - Text from text layer is extracted
            - Archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsNotNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_SKIP_ARCHIVE_FILE="never")
    def test_skip_archive_never_withimages(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR_SKIP_ARCHIVE_FILE set to never
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - Archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsNotNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_SKIP_ARCHIVE_FILE="with_text")
    def test_skip_archive_withtext_withtext(self):
        """
        GIVEN:
            - File with existing text layer
            - OCR_SKIP_ARCHIVE_FILE set to with_text
        WHEN:
            - Document is parsed
        THEN:
            - Text from text layer is extracted
            - No archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_SKIP_ARCHIVE_FILE="with_text")
    def test_skip_archive_withtext_withimages(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR_SKIP_ARCHIVE_FILE set to with_text
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - Archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsNotNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_SKIP_ARCHIVE_FILE="always")
    def test_skip_archive_always_withtext(self):
        """
        GIVEN:
            - File with existing text layer
            - OCR_SKIP_ARCHIVE_FILE set to always
        WHEN:
            - Document is parsed
        THEN:
            - Text from text layer is extracted
            - No archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"),
            "application/pdf",
        )
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_SKIP_ARCHIVE_FILE="always")
    def test_skip_archive_always_withimages(self):
        """
        GIVEN:
            - File with text contained in images but no text layer
            - OCR_SKIP_ARCHIVE_FILE set to always
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - No archive file is created
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"),
            "application/pdf",
        )
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @override_settings(OCR_MODE="skip")
    def test_multi_page_mixed(self):
        """
        GIVEN:
            - File with some text contained in images and some in text layer
            - OCR mode set to skip
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - An archive file is created with the OCRd text and the original text
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-mixed.pdf"),
            "application/pdf",
        )
        self.assertIsNotNone(parser.archive_path)
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3", "page 4", "page 5", "page 6"],
        )

        with open(os.path.join(parser.tempdir, "sidecar.txt")) as f:
            sidecar = f.read()

        self.assertIn("[OCR skipped on page(s) 4-6]", sidecar)

    @override_settings(OCR_MODE="redo")
    def test_single_page_mixed(self):
        """
        GIVEN:
            - File with some text contained in images and some in text layer
            - Text and images are mixed on the same page
            - OCR mode set to redo
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - Full content of the file is parsed (not just the image text)
            - An archive file is created with the OCRd text and the original text
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "single-page-mixed.pdf"),
            "application/pdf",
        )
        self.assertIsNotNone(parser.archive_path)
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            [
                "this is some normal text, present on page 1 of the document.",
                "this is some text, but in an image, also on page 1.",
                "this is further text on page 1.",
            ],
        )

        with open(os.path.join(parser.tempdir, "sidecar.txt")) as f:
            sidecar = f.read().lower()

        self.assertIn("this is some text, but in an image, also on page 1.", sidecar)
        self.assertNotIn(
            "this is some normal text, present on page 1 of the document.",
            sidecar,
        )

    @override_settings(OCR_MODE="skip_noarchive")
    def test_multi_page_mixed_no_archive(self):
        """
        GIVEN:
            - File with some text contained in images and some in text layer
            - OCR mode set to skip_noarchive
        WHEN:
            - Document is parsed
        THEN:
            - Text from images is extracted
            - No archive file is created as original file contains text
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-mixed.pdf"),
            "application/pdf",
        )
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 4", "page 5", "page 6"],
        )

    @override_settings(OCR_MODE="skip", OCR_ROTATE_PAGES=True)
    def test_rotate(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "rotated.pdf"), "application/pdf")
        self.assertContainsStrings(
            parser.get_text(),
            [
                "This is the text that appears on the first page. It’s a lot of text.",
                "Even if the pages are rotated, OCRmyPDF still gets the job done.",
                "This is a really weird file with lots of nonsense text.",
                "If you read this, it’s your own fault. Also check your screen orientation.",
            ],
        )

    def test_multi_page_tiff(self):
        """
        GIVEN:
            - Multi-page TIFF image
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        parser = RasterisedDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "multi-page-images.tiff"),
            "image/tiff",
        )
        self.assertIsFile(parser.archive_path)
        self.assertContainsStrings(
            parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_multi_page_tiff_alpha(self):
        """
        GIVEN:
            - Multi-page TIFF image
            - Image include an alpha channel
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        parser = RasterisedDocumentParser(None)
        sample_file = os.path.join(self.SAMPLE_FILES, "multi-page-images-alpha.tiff")
        with tempfile.NamedTemporaryFile() as tmp_file:
            shutil.copy(sample_file, tmp_file.name)
            parser.parse(
                tmp_file.name,
                "image/tiff",
            )
            self.assertIsFile(parser.archive_path)
            self.assertContainsStrings(
                parser.get_text().lower(),
                ["page 1", "page 2", "page 3"],
            )

    def test_multi_page_tiff_alpha_srgb(self):
        """
        GIVEN:
            - Multi-page TIFF image
            - Image include an alpha channel
            - Image is srgb colorspace
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        parser = RasterisedDocumentParser(None)
        sample_file = os.path.join(
            self.SAMPLE_FILES,
            "multi-page-images-alpha-rgb.tiff",
        )
        with tempfile.NamedTemporaryFile() as tmp_file:
            shutil.copy(sample_file, tmp_file.name)
            parser.parse(
                tmp_file.name,
                "image/tiff",
            )
            self.assertIsFile(parser.archive_path)
            self.assertContainsStrings(
                parser.get_text().lower(),
                ["page 1", "page 2", "page 3"],
            )

    def test_ocrmypdf_parameters(self):
        parser = RasterisedDocumentParser(None)
        params = parser.construct_ocrmypdf_parameters(
            input_file="input.pdf",
            output_file="output.pdf",
            sidecar_file="sidecar.txt",
            mime_type="application/pdf",
            safe_fallback=False,
        )

        self.assertEqual(params["input_file"], "input.pdf")
        self.assertEqual(params["output_file"], "output.pdf")
        self.assertEqual(params["sidecar"], "sidecar.txt")

        with override_settings(OCR_CLEAN="none"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn("clean", params)
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params["clean"])
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean-final", OCR_MODE="skip"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params["clean_final"])
            self.assertNotIn("clean", params)

        with override_settings(OCR_CLEAN="clean-final", OCR_MODE="redo"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params["clean"])
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_DESKEW=True, OCR_MODE="skip"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params["deskew"])

        with override_settings(OCR_DESKEW=True, OCR_MODE="redo"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn("deskew", params)

        with override_settings(OCR_DESKEW=False, OCR_MODE="skip"):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn("deskew", params)

        with override_settings(OCR_MAX_IMAGE_PIXELS=1_000_001.0):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertIn("max_image_mpixels", params)
            self.assertAlmostEqual(params["max_image_mpixels"], 1, places=4)

        with override_settings(OCR_MAX_IMAGE_PIXELS=-1_000_001.0):
            parser = RasterisedDocumentParser(None)
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn("max_image_mpixels", params)

    def test_rtl_language_detection(self):
        """
        GIVEN:
            - File with text in an RTL language
        WHEN:
            - Document is parsed
        THEN:
            - Text from the document is extracted
        """
        parser = RasterisedDocumentParser(None)

        parser.parse(
            os.path.join(self.SAMPLE_FILES, "rtl-test.pdf"),
            "application/pdf",
        )

        # Copied from the PDF to here.  Don't even look at it
        self.assertIn("ةﯾﻠﺧﺎدﻻ ةرازو", parser.get_text())

    @mock.patch("ocrmypdf.ocr")
    def test_gs_rendering_error(self, m):
        m.side_effect = SubprocessOutputError("Ghostscript PDF/A rendering failed")
        parser = RasterisedDocumentParser(None)

        self.assertRaises(
            ParseError,
            parser.parse,
            os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"),
            "application/pdf",
        )


class TestParserFileTypes(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_bmp(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.bmp"), "image/bmp")
        self.assertIsFile(parser.archive_path)
        self.assertIn("this is a test document", parser.get_text().lower())

    def test_jpg(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.jpg"), "image/jpeg")
        self.assertIsFile(parser.archive_path)
        self.assertIn("this is a test document", parser.get_text().lower())

    @override_settings(OCR_IMAGE_DPI=200)
    def test_gif(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.gif"), "image/gif")
        self.assertIsFile(parser.archive_path)
        self.assertIn("this is a test document", parser.get_text().lower())

    def test_tiff(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.tif"), "image/tiff")
        self.assertIsFile(parser.archive_path)
        self.assertIn("this is a test document", parser.get_text().lower())

    @override_settings(OCR_IMAGE_DPI=72)
    def test_webp(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "document.webp"), "image/webp")
        self.assertIsFile(parser.archive_path)
        # Older tesseracts consistently mangle the space between "a webp",
        # tesseract 5.3.0 seems to do a better job, so we're accepting both
        self.assertRegex(
            parser.get_text().lower(),
            r"this is a ?webp document, created 11/14/2022.",
        )
