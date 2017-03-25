import os
from unittest import mock, skipIf

import pyocr
from django.test import TestCase
from pyocr.libtesseract.tesseract_raw import \
    TesseractError as OtherTesseractError

from ..parsers import image_to_string, strip_excess_whitespace


class FakeTesseract(object):

    @staticmethod
    def can_detect_orientation():
        return True

    @staticmethod
    def detect_orientation(file_handle, lang):
        raise OtherTesseractError("arbitrary status", "message")

    @staticmethod
    def image_to_string(file_handle, lang):
        return "This is test text"


class FakePyOcr(object):

    @staticmethod
    def get_available_tools():
        return [FakeTesseract]


class TestOCR(TestCase):

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

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")
    TESSERACT_INSTALLED = bool(pyocr.get_available_tools())

    def test_strip_excess_whitespace(self):
        for source, result in self.text_cases:
            actual_result = strip_excess_whitespace(source)
            self.assertEqual(
                result,
                actual_result,
                "strip_exceess_whitespace({}) != '{}', but '{}'".format(
                    source,
                    result,
                    actual_result
                )
            )

    @skipIf(not TESSERACT_INSTALLED, "Tesseract not installed. Skipping")
    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SAMPLE_FILES
    )
    @mock.patch("paperless_tesseract.parsers.pyocr", FakePyOcr)
    def test_image_to_string_with_text_free_page(self):
        """
        This test is sort of silly, since it's really just reproducing an odd
        exception thrown by pyocr when it encounters a page with no text.
        Actually running this test against an installation of Tesseract results
        in a segmentation fault rooted somewhere deep inside pyocr where I
        don't care to dig.  Regardless, if you run the consumer normally,
        text-free pages are now handled correctly so long as we work around
        this weird exception.
        """
        image_to_string(["no-text.png", "en"])
