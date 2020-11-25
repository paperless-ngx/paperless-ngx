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

        self.assertIsNone(text)

    def test_thumbnail(self):
        parser = RasterisedDocumentParser(uuid.uuid4())
        parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple.pdf'), "application/pdf")
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
        parser.get_thumbnail(os.path.join(self.SAMPLE_FILES, 'simple.pdf'), "application/pdf")
        # dont really know how to test it, just call it and assert that it does not raise anything.
