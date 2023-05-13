from pathlib import Path

from django.test import TestCase

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_text.parsers import TextDocumentParser


class TestTextParser(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_DIR = Path(__file__).resolve().parent / "samples"

    def test_thumbnail(self):
        parser = TextDocumentParser(None)

        # just make sure that it does not crash
        f = parser.get_thumbnail(
            self.SAMPLE_DIR / "test.txt",
            "text/plain",
        )
        self.assertIsFile(f)

    def test_parse(self):
        parser = TextDocumentParser(None)

        parser.parse(
            self.SAMPLE_DIR / "test.txt",
            "text/plain",
        )

        self.assertEqual(parser.get_text(), "This is a test file.\n")
        self.assertIsNone(parser.get_archive_path())

    def test_parse_invalid_bytes(self):
        """
        GIVEN:
            - Text file which contains invalid UTF bytes
        WHEN:
            - The file is parsed
        THEN:
            - Parsing continues
            - Invalid bytes are removed
        """
        parser = TextDocumentParser(None)

        parser.parse(
            self.SAMPLE_DIR / "decode_error.txt",
            "text/plain",
        )

        self.assertEqual(parser.get_text(), "Pantothens�ure\n")
        self.assertIsNone(parser.get_archive_path())
