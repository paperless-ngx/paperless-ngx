import os
import time
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

    def try_parse_with_wait(self, test_file, mime_type):
        """
        For whatever reason, the image started during the test pipeline likes to
        segfault sometimes, when run with the exact files that usually pass.

        So, this function will retry the parsing up to 3 times, with larger backoff
        periods between each attempt, in hopes the issue resolves itself during
        one attempt to parse.

        This will wait the following:
            - Attempt 1 - 20s following failure
            - Attempt 2 - 40s following failure
            - Attempt 3 - 80s following failure

        """
        succeeded = False
        retry_time = 20.0
        retry_count = 0
        max_retry_count = 3

        while retry_count < max_retry_count and not succeeded:
            try:
                self.parser.parse(test_file, mime_type)

                succeeded = True
            except Exception as e:
                print(f"{e} during try #{retry_count}", flush=True)

                retry_count = retry_count + 1

                time.sleep(retry_time)
                retry_time = retry_time * 2.0

        self.assertTrue(
            succeeded,
            "Continued Tika server errors after multiple retries",
        )

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

        self.try_parse_with_wait(test_file, "application/vnd.oasis.opendocument.text")

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

        self.try_parse_with_wait(
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
