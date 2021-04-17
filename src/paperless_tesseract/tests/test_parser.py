import os
import uuid
from typing import ContextManager
from unittest import mock

from django.test import TestCase, override_settings

from documents.parsers import ParseError, run_convert
from documents.tests.utils import DirectoriesMixin
from paperless_tesseract.parsers import RasterisedDocumentParser, post_process_text

image_to_string_calls = []


def fake_convert(input_file, output_file, **kwargs):
    with open(input_file) as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        with open(output_file % i, "w") as f2:
            f2.write(line.strip())


class FakeImageFile(ContextManager):
    def __init__(self, fname):
        self.fname = fname

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __enter__(self):
        return os.path.basename(self.fname)


class TestParser(DirectoriesMixin, TestCase):

    def assertContainsStrings(self, content, strings):
        # Asserts that all strings appear in content, in the given order.
        indices = []
        for s in strings:
            if s in content:
                indices.append(content.index(s))
            else:
                self.fail(f"'{s}' is not in '{content}'")
        self.assertListEqual(indices, sorted(indices))

    text_cases = [
        ("simple     string", "simple string"),
        (
            "simple    newline\n   testing string",
            "simple newline\ntesting string"
        ),
        (
            "utf-8   строка с пробелами в конце  ",
            "utf-8 строка с пробелами в конце"
        )
    ]

    def test_post_process_text(self):
        for source, result in self.text_cases:
            actual_result = post_process_text(source)
            self.assertEqual(
                result,
                actual_result,
                "strip_exceess_whitespace({}) != '{}', but '{}'".format(
                    source,
                    result,
                    actual_result
                )
            )

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_get_text_from_pdf(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        text = parser.extract_text(None, os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'))

        self.assertContainsStrings(text.strip(), ["This is a test document."])

    def test_thumbnail(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'), "application/pdf")
        self.assertTrue(os.path.isfile(thumb))

    @mock.patch("documents.parsers.run_convert")
    def test_thumbnail_fallback(self, m):

        def call_convert(input_file, output_file, **kwargs):
            if ".pdf" in input_file:
                raise ParseError("Does not compute.")
            else:
                run_convert(input_file=input_file, output_file=output_file, **kwargs)

        m.side_effect = call_convert

        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'), "application/pdf")
        self.assertTrue(os.path.isfile(thumb))

    def test_thumbnail_encrypted(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        thumb = parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'encrypted.pdf'), "application/pdf")
        self.assertTrue(os.path.isfile(thumb))

    def test_get_dpi(self):
        parser = RasterisedDocumentParser(None)

        dpi = parser.get_dpi(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"))
        self.assertEqual(dpi, None)

        dpi = parser.get_dpi(os.path.join(self.SAMPLE_FILES, "simple.png"))
        self.assertEqual(dpi, 72)

    def test_simple_digital(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple-digital.pdf"), "application/pdf")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertContainsStrings(parser.get_text(), ["This is a test document."])

    def test_with_form(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertContainsStrings(parser.get_text(), ["Please enter your name in here:", "This is a PDF document with a form."])

    @override_settings(OCR_MODE="redo")
    def test_with_form_error(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(parser.get_text(), ["Please enter your name in here:", "This is a PDF document with a form."])

    @override_settings(OCR_MODE="skip")
    def test_signed(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "signed.pdf"), "application/pdf")

        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(parser.get_text(), ["This is a digitally signed PDF, created with Acrobat Pro for the Paperless project to enable", "automated testing of signed/encrypted PDFs"])

    @override_settings(OCR_MODE="skip")
    def test_encrypted(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "encrypted.pdf"), "application/pdf")

        self.assertIsNone(parser.archive_path)
        self.assertEqual(parser.get_text(), "")


    @override_settings(OCR_MODE="redo")
    def test_with_form_error_notext(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertContainsStrings(parser.get_text(), ["Please enter your name in here:", "This is a PDF document with a form."])

    @override_settings(OCR_MODE="force")
    def test_with_form_force(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertContainsStrings(parser.get_text(), ["Please enter your name in here:", "This is a PDF document with a form."])

    def test_image_simple(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.png"), "image/png")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertContainsStrings(parser.get_text(), ["This is a test document."])

    def test_image_simple_alpha_fail(self):
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(os.path.join(self.SAMPLE_FILES, "simple-alpha.png"), "image/png")

        self.assertRaises(ParseError, f)

    def test_image_calc_a4_dpi(self):
        parser = RasterisedDocumentParser(None)

        dpi = parser.calculate_a4_dpi(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"))

        self.assertEqual(dpi, 62)

    @mock.patch("paperless_tesseract.parsers.RasterisedDocumentParser.calculate_a4_dpi")
    def test_image_dpi_fail(self, m):
        m.return_value = None
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"), "image/png")

        self.assertRaises(ParseError, f)

    @override_settings(OCR_IMAGE_DPI=72)
    def test_image_no_dpi_default(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"), "image/png")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertContainsStrings(parser.get_text().lower(), ["this is a test document."])

    def test_multi_page(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_PAGES=2, OCR_MODE="skip")
    def test_multi_page_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_pages_redo(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_PAGES=2, OCR_MODE="force")
    def test_multi_page_pages_force(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OOCR_MODE="skip")
    def test_multi_page_analog_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_analog_pages_redo(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2"])
        self.assertFalse("page 3" in parser.get_text().lower())

    @override_settings(OCR_PAGES=1, OCR_MODE="force")
    def test_multi_page_analog_pages_force(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1"])
        self.assertFalse("page 2" in parser.get_text().lower())
        self.assertFalse("page 3" in parser.get_text().lower())

    @override_settings(OCR_MODE="skip_noarchive")
    def test_skip_noarchive_withtext(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_MODE="skip_noarchive")
    def test_skip_noarchive_notext(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3"])

    @override_settings(OCR_MODE="skip")
    def test_multi_page_mixed(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-mixed.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertContainsStrings(parser.get_text().lower(), ["page 1", "page 2", "page 3", "page 4", "page 5", "page 6"])

        with open(os.path.join(parser.tempdir, "sidecar.txt")) as f:
            sidecar = f.read()

        self.assertIn("[OCR skipped on page(s) 4-6]", sidecar)

    @override_settings(OCR_MODE="skip_noarchive")
    def test_multi_page_mixed_no_archive(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-mixed.pdf"), "application/pdf")
        self.assertIsNone(parser.archive_path)
        self.assertContainsStrings(parser.get_text().lower(), ["page 4", "page 5", "page 6"])

    @override_settings(OCR_MODE="skip", OCR_ROTATE_PAGES=True)
    def test_rotate(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "rotated.pdf"), "application/pdf")
        self.assertContainsStrings(parser.get_text(), [
            "This is the text that appears on the first page. It’s a lot of text.",
            "Even if the pages are rotated, OCRmyPDF still gets the job done.",
            "This is a really weird file with lots of nonsense text.",
            "If you read this, it’s your own fault. Also check your screen orientation."
        ])

    def test_ocrmypdf_parameters(self):
        parser = RasterisedDocumentParser(None)
        params = parser.construct_ocrmypdf_parameters(input_file="input.pdf", output_file="output.pdf",
                                                      sidecar_file="sidecar.txt", mime_type="application/pdf",
                                                      safe_fallback=False)

        self.assertEqual(params['input_file'], "input.pdf")
        self.assertEqual(params['output_file'], "output.pdf")
        self.assertEqual(params['sidecar'], "sidecar.txt")

        with override_settings(OCR_CLEAN="none"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn("clean", params)
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params['clean'])
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean-final", OCR_MODE="skip"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params['clean_final'])
            self.assertNotIn("clean", params)

        with override_settings(OCR_CLEAN="clean-final", OCR_MODE="redo"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params['clean'])
            self.assertNotIn("clean_final", params)

        with override_settings(OCR_DESKEW=True, OCR_MODE="skip"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertTrue(params['deskew'])

        with override_settings(OCR_DESKEW=True, OCR_MODE="redo"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn('deskew', params)

        with override_settings(OCR_DESKEW=False, OCR_MODE="skip"):
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
            self.assertNotIn('deskew', params)

class TestParserFileTypes(DirectoriesMixin, TestCase):

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_bmp(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.bmp"), "image/bmp")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertTrue("this is a test document" in parser.get_text().lower())

    def test_jpg(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.jpg"), "image/jpeg")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertTrue("this is a test document" in parser.get_text().lower())

    @override_settings(OCR_IMAGE_DPI=200)
    def test_gif(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.gif"), "image/gif")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertTrue("this is a test document" in parser.get_text().lower())

    def test_tiff(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.tif"), "image/tiff")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertTrue("this is a test document" in parser.get_text().lower())
