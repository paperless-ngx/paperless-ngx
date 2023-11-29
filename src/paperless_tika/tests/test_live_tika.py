import os
from pathlib import Path
from typing import Final

import pytest
from django.test import TestCase

from documents.tests.utils import util_call_with_backoff
from paperless_tika.parsers import TikaDocumentParser


@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg/Tika servers to test with",
)
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

        util_call_with_backoff(
            self.parser.parse,
            [test_file, "application/vnd.oasis.opendocument.text"],
        )

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

        util_call_with_backoff(
            self.parser.parse,
            [
                test_file,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
        )

        self.assertEqual(
            self.parser.text,
            "This is an DOCX test document, also made September 14, 2022",
        )
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertTrue(b"PDF-" in f.read()[:10])

        # self.assertEqual(self.parser.date, datetime.datetime(2022, 9, 14))

    def test_basic_parse_doc(self):
        """
        GIVEN:
            - An input DOC format document
        WHEN:
            - The document is parsed
        THEN:
            - Document content is correct
            - Document date is correct
        """
        test_file = self.SAMPLE_DIR / "sample.doc"

        util_call_with_backoff(
            self.parser.parse,
            [test_file, "application/msword"],
        )

        self.assertIn(
            "his is a test document, saved in the older .doc format",
            self.parser.text,
        )
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertTrue(b"PDF-" in f.read()[:10])

    def test_tika_fails_multi_part(self):
        """
        GIVEN:
            - An input ODT format document
            - The document is known to crash Tika when uploaded via multi-part form data
        WHEN:
            - The document is parsed
        THEN:
            - Document content is correct
            - Document date is correct
        See also:
            - https://issues.apache.org/jira/browse/TIKA-4110
        """
        test_file = self.SAMPLE_DIR / "multi-part-broken.odt"

        util_call_with_backoff(
            self.parser.parse,
            [test_file, "application/vnd.oasis.opendocument.text"],
        )

        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertTrue(b"PDF-" in f.read()[:10])
