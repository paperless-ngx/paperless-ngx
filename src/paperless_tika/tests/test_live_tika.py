import datetime
import os
from pathlib import Path
from typing import Final

import pytest
from django.test import TestCase
from paperless_tika.parsers import TikaDocumentParser


@pytest.mark.skipif("TIKA_LIVE" not in os.environ, reason="No tika server")
class TestTikaParserAgainstServer(TestCase):
    """
    This test case tests the Tika parsing against a live tika server,
    if the environment contains the correct value indicating such a server
    is available.
    """

    SAMPLE_DIR: Final[Path] = (Path(__file__).parent / Path("samples")).resolve()

    def setUp(self) -> None:
        self.parser = TikaDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    def test_basic_parse_odt(self):
        """
        GIVEN:
            - An input ODT format document
        WHEN:
            - The document is parsed
        THEN:
            - Document content is correct
            - Document date is correct
        """
        test_file = self.SAMPLE_DIR / Path("sample.odt")

        self.parser.parse(test_file, "application/vnd.oasis.opendocument.text")

        self.assertEqual(
            self.parser.text,
            "This is an ODT test document, created September 14, 2022",
        )
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            # PDFs begin with the bytes PDF-x.y
            self.assertTrue(b"PDF-" in f.read()[:10])

        # TODO: Unsure what can set the Creation-Date field in a document, enable when possible
        # self.assertEqual(self.parser.date, datetime.datetime(2022, 9, 14))

    def test_basic_parse_docx(self):
        """
        GIVEN:
            - An input DOCX format document
        WHEN:
            - The document is parsed
        THEN:
            - Document content is correct
            - Document date is correct
        """
        test_file = self.SAMPLE_DIR / Path("sample.docx")

        self.parser.parse(
            test_file,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        self.assertEqual(
            self.parser.text,
            "This is an DOCX test document, also made September 14, 2022",
        )
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertTrue(b"PDF-" in f.read()[:10])

        # self.assertEqual(self.parser.date, datetime.datetime(2022, 9, 14))
