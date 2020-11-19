import os
import shutil
import tempfile
import uuid
from typing import ContextManager
from unittest import mock

from django.test import TestCase, override_settings
from pyocr.error import TesseractError

from documents.parsers import ParseError, run_convert
from paperless_tesseract.parsers import RasterisedDocumentParser, get_text_from_pdf, image_to_string, OCRError

image_to_string_calls = []


class FakeTesseract(object):

    @staticmethod
    def can_detect_orientation():
        return True

    @staticmethod
    def detect_orientation(file_handle, lang):
        raise TesseractError("arbitrary status", "message")

    @staticmethod
    def get_available_languages():
        return ['eng', 'deu']

    @staticmethod
    def image_to_string(file_handle, lang):
        image_to_string_calls.append((file_handle.name, lang))
        return file_handle.read()


class FakePyOcr(object):

    @staticmethod
    def get_available_tools():
        return [FakeTesseract]


def fake_convert(input_file, output_file, **kwargs):
    with open(input_file) as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        with open(output_file % i, "w") as f2:
            f2.write(line.strip())


def fake_unpaper(pnm):
    output = pnm + ".unpaper.pnm"
    shutil.copy(pnm, output)
    return output


class FakeImageFile(ContextManager):
    def __init__(self, fname):
        self.fname = fname

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __enter__(self):
        return os.path.basename(self.fname)


fake_image = FakeImageFile


@mock.patch("paperless_tesseract.parsers.pyocr", FakePyOcr)
@mock.patch("paperless_tesseract.parsers.run_convert", fake_convert)
@mock.patch("paperless_tesseract.parsers.run_unpaper", fake_unpaper)
@mock.patch("paperless_tesseract.parsers.Image.open", open)
class TestRasterisedDocumentParser(TestCase):

    def setUp(self):
        self.scratch = tempfile.mkdtemp()

        global image_to_string_calls

        image_to_string_calls = []

        override_settings(OCR_LANGUAGE="eng", SCRATCH_DIR=self.scratch).enable()

    def tearDown(self):
        shutil.rmtree(self.scratch)

    def get_input_file(self, pages):
        _, fname = tempfile.mkstemp(suffix=".pdf", dir=self.scratch)
        with open(fname, "w") as f:
            f.writelines([f"line {p}\n" for p in range(pages)])
        return fname

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "en")
    def test_parse_text_simple_language_match(self):
        parser = RasterisedDocumentParser(self.get_input_file(1), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "en")
    def test_parse_text_2_pages(self):
        parser = RasterisedDocumentParser(self.get_input_file(2), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0 line 1")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng", "eng"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "en")
    def test_parse_text_3_pages(self):
        parser = RasterisedDocumentParser(self.get_input_file(3), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0 line 1 line 2")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng", "eng", "eng"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: None)
    def test_parse_text_lang_detect_failed(self):
        parser = RasterisedDocumentParser(self.get_input_file(3), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0 line 1 line 2")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng", "eng", "eng"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "it")
    def test_parse_text_lang_not_installed(self):
        parser = RasterisedDocumentParser(self.get_input_file(4), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0 line 1 line 2 line 3")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng", "eng", "eng", "eng"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "de")
    def test_parse_text_lang_mismatch(self):
        parser = RasterisedDocumentParser(self.get_input_file(3), uuid.uuid4())
        text = parser.get_text()
        self.assertEqual(text, "line 0 line 1 line 2")

        self.assertListEqual([args[1] for args in image_to_string_calls], ["eng", "deu", "deu", "deu"])

    @mock.patch("paperless_tesseract.parsers.langdetect.detect", lambda _: "de")
    def test_parse_empty_doc(self):
        parser = RasterisedDocumentParser(self.get_input_file(0), uuid.uuid4())
        try:
            parser.get_text()
        except ParseError as e:
            self.assertEqual("Empty document, nothing to do.", str(e))
        else:
            self.fail("Should raise exception")


class TestAuxilliaryFunctions(TestCase):

    def setUp(self):
        self.scratch = tempfile.mkdtemp()

        override_settings(SCRATCH_DIR=self.scratch).enable()

    def tearDown(self):
        shutil.rmtree(self.scratch)

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_get_text_from_pdf(self):
        text = get_text_from_pdf(os.path.join(self.SAMPLE_FILES, 'simple.pdf'))

        self.assertEqual(text.strip(), "This is a test document.")

    def test_get_text_from_pdf_error(self):
        text = get_text_from_pdf(os.path.join(self.SAMPLE_FILES, 'simple.png'))

        self.assertEqual(text.strip(), "")

    def test_image_to_string(self):
        text = image_to_string((os.path.join(self.SAMPLE_FILES, 'simple.png'), "eng"))

        self.assertEqual(text, "This is a test document.")

    def test_image_to_string_language_unavailable(self):
        try:
            image_to_string((os.path.join(self.SAMPLE_FILES, 'simple.png'), "ita"))
        except OCRError as e:
            self.assertTrue("Failed loading language" in str(e))
        else:
            self.fail("Should raise exception")

    @override_settings(OCR_ALWAYS=False)
    @mock.patch("paperless_tesseract.parsers.get_text_from_pdf")
    @mock.patch("paperless_tesseract.parsers.RasterisedDocumentParser._get_greyscale")
    def test_is_ocred(self, m2, m):
        parser = RasterisedDocumentParser("", uuid.uuid4())
        m.return_value = "lots of text lots of text lots of text lots of text lots of text lots of text " \
                         "lots of text lots of text lots of text lots of text lots of text lots of text " \
                         "lots of text lots of text lots of text lots of text lots of text lots of text "
        parser.get_text()
        self.assertEqual(m.call_count, 2)
        self.assertEqual(m2.call_count, 0)

    def test_thumbnail(self):
        parser = RasterisedDocumentParser(os.path.join(self.SAMPLE_FILES, 'simple.pdf'), uuid.uuid4())
        parser.get_thumbnail()
        # dont really know how to test it, just call it and assert that it does not raise anything.

    @mock.patch("paperless_tesseract.parsers.run_convert")
    def test_thumbnail_fallback(self, m):

        def call_convert(input_file, output_file, **kwargs):
            if ".pdf" in input_file:
                raise ParseError("Does not compute.")
            else:
                run_convert(input_file=input_file, output_file=output_file, **kwargs)

        m.side_effect = call_convert

        parser = RasterisedDocumentParser(os.path.join(self.SAMPLE_FILES, 'simple.pdf'), uuid.uuid4())
        parser.get_thumbnail()
        # dont really know how to test it, just call it and assert that it does not raise anything.
