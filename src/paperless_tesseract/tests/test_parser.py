import os
import shutil
import tempfile
import uuid
from typing import ContextManager
from unittest import mock

from django.test import TestCase, override_settings

from documents.parsers import ParseError, run_convert
from paperless_tesseract.parsers import RasterisedDocumentParser, get_text_from_pdf

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


class TestParser(TestCase):

    def setUp(self):
        self.scratch = tempfile.mkdtemp()

        override_settings(SCRATCH_DIR=self.scratch).enable()

    def tearDown(self):
        shutil.rmtree(self.scratch)

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_get_text_from_pdf(self):
        text = get_text_from_pdf(os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'))

        self.assertEqual(text.strip(), "This is a test document.")

    def test_thumbnail(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'), "application/pdf")
        # dont really know how to test it, just call it and assert that it does not raise anything.

    @mock.patch("paperless_tesseract.parsers.run_convert")
    def test_thumbnail_fallback(self, m):

        def call_convert(input_file, output_file, **kwargs):
            if ".pdf" in input_file:
                raise ParseError("Does not compute.")
            else:
                run_convert(input_file=input_file, output_file=output_file, **kwargs)

        m.side_effect = call_convert

        parser = RasterisedDocumentParser(uuid.uuid4())
        parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple-digital.pdf'), "application/pdf")
        # dont really know how to test it, just call it and assert that it does not raise anything.

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

        self.assertEqual(parser.get_text(), "This is a test document.")

    def test_with_form(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertEqual(parser.get_text(), "Please enter your name in here:\n\nThis is a PDF document with a form.")

    @override_settings(OCR_MODE="redo")
    def test_with_form_error(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertIsNone(parser.archive_path)

        self.assertEqual(parser.get_text(), "Please enter your name in here:\n\nThis is a PDF document with a form.")

    @override_settings(OCR_MODE="redo")
    @mock.patch("paperless_tesseract.parsers.get_text_from_pdf", lambda _: None)
    def test_with_form_error_notext(self):
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

        self.assertRaises(ParseError, f)

    @override_settings(OCR_MODE="force")
    def test_with_form_force(self):
        parser = RasterisedDocumentParser(None)

#        parser.parse(os.path.join(self.SAMPLE_FILES, "with-form.pdf"), "application/pdf")

#        self.assertEqual(parser.get_text(), "Please enter your name in here:\n\nThis is a PDF document with a form.")

    def test_image_simple(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple.png"), "image/png")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertEqual(parser.get_text(), "This is a test document.")

    def test_image_simple_alpha_fail(self):
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(os.path.join(self.SAMPLE_FILES, "simple-alpha.png"), "image/png")

        self.assertRaises(ParseError, f)


    def test_image_no_dpi_fail(self):
        parser = RasterisedDocumentParser(None)

        def f():
            parser.parse(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"), "image/png")

        self.assertRaises(ParseError, f)

    @override_settings(OCR_IMAGE_DPI=72)
    def test_image_no_dpi_default(self):
        parser = RasterisedDocumentParser(None)

        parser.parse(os.path.join(self.SAMPLE_FILES, "simple-no-dpi.png"), "image/png")

        self.assertTrue(os.path.isfile(parser.archive_path))

        self.assertEqual(parser.get_text(), "This is a test document.")

    def test_multi_page(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.\n\nThis is a multi page document. Page 3.")

    @override_settings(OCR_PAGES=2, OCR_MODE="skip")
    def test_multi_page_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.\n\nThis is a multi page document. Page 3.")

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_pages_redo(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.\n\nThis is a multi page document. Page 3.")

    @override_settings(OCR_PAGES=2, OCR_MODE="force")
    def test_multi_page_pages_force(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-digital.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.\n\nThis is a multi page document. Page 3.")

    @override_settings(OOCR_MODE="skip")
    def test_multi_page_analog_pages_skip(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.\n\nThis is a multi page document. Page 3.")

    @override_settings(OCR_PAGES=2, OCR_MODE="redo")
    def test_multi_page_analog_pages_redo(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.\n\nThis is a multi page document. Page 2.")

    @override_settings(OCR_PAGES=1, OCR_MODE="force")
    def test_multi_page_analog_pages_force(self):
        parser = RasterisedDocumentParser(None)
        parser.parse(os.path.join(self.SAMPLE_FILES, "multi-page-images.pdf"), "application/pdf")
        self.assertTrue(os.path.isfile(parser.archive_path))
        self.assertEqual(parser.get_text(), "This is a multi page document. Page 1.")
