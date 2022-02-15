import os

from django.test import TestCase

from documents.tests.utils import DirectoriesMixin
from paperless_text.parsers import TextDocumentParser


class TestTextParser(DirectoriesMixin, TestCase):

    def test_thumbnail(self):

        parser = TextDocumentParser(None)

        # just make sure that it does not crash
        f = parser.get_thumbnail(os.path.join(os.path.dirname(__file__), "samples", "test.txt"), "text/plain")
        self.assertTrue(os.path.isfile(f))

    def test_parse(self):

        parser = TextDocumentParser(None)

        parser.parse(os.path.join(os.path.dirname(__file__), "samples", "test.txt"), "text/plain")

        self.assertEqual(parser.get_text(), "This is a test file.\n")
        self.assertIsNone(parser.get_archive_path())
