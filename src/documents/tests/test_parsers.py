import os
import shutil
import tempfile
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import override_settings
from django.test import TestCase
from documents.parsers import DocumentParser
from documents.parsers import get_default_file_extension
from documents.parsers import get_parser_class
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from paperless_tesseract.parsers import RasterisedDocumentParser
from paperless_text.parsers import TextDocumentParser


def fake_magic_from_file(file, mime=False):

    if mime:
        if os.path.splitext(file)[1] == ".pdf":
            return "application/pdf"
        else:
            return "unknown"
    else:
        return "A verbose string that describes the contents of the file"


@mock.patch("documents.parsers.magic.from_file", fake_magic_from_file)
class TestParserDiscovery(TestCase):
    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_1_parser(self, m, *args):
        class DummyParser:
            pass

        m.return_value = (
            (
                None,
                {
                    "weight": 0,
                    "parser": DummyParser,
                    "mime_types": {"application/pdf": ".pdf"},
                },
            ),
        )

        self.assertEqual(get_parser_class("doc.pdf"), DummyParser)

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_n_parsers(self, m, *args):
        class DummyParser1:
            pass

        class DummyParser2:
            pass

        m.return_value = (
            (
                None,
                {
                    "weight": 0,
                    "parser": DummyParser1,
                    "mime_types": {"application/pdf": ".pdf"},
                },
            ),
            (
                None,
                {
                    "weight": 1,
                    "parser": DummyParser2,
                    "mime_types": {"application/pdf": ".pdf"},
                },
            ),
        )

        self.assertEqual(get_parser_class("doc.pdf"), DummyParser2)

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_0_parsers(self, m, *args):
        m.return_value = []
        with TemporaryDirectory() as tmpdir:
            self.assertIsNone(get_parser_class("doc.pdf"))


def fake_get_thumbnail(self, path, mimetype, file_name):
    return os.path.join(os.path.dirname(__file__), "examples", "no-text.png")


class TestParserAvailability(TestCase):
    def test_file_extensions(self):

        for ext in [".pdf", ".jpe", ".jpg", ".jpeg", ".txt", ".csv"]:
            self.assertIn(ext, get_supported_file_extensions())
        self.assertEqual(get_default_file_extension("application/pdf"), ".pdf")
        self.assertEqual(get_default_file_extension("image/png"), ".png")
        self.assertEqual(get_default_file_extension("image/jpeg"), ".jpg")
        self.assertEqual(get_default_file_extension("text/plain"), ".txt")
        self.assertEqual(get_default_file_extension("text/csv"), ".csv")
        self.assertEqual(get_default_file_extension("application/zip"), ".zip")
        self.assertEqual(get_default_file_extension("aasdasd/dgfgf"), "")

        self.assertIsInstance(
            get_parser_class_for_mime_type("application/pdf")(logging_group=None),
            RasterisedDocumentParser,
        )
        self.assertIsInstance(
            get_parser_class_for_mime_type("text/plain")(logging_group=None),
            TextDocumentParser,
        )
        self.assertEqual(get_parser_class_for_mime_type("text/sdgsdf"), None)

        self.assertTrue(is_file_ext_supported(".pdf"))
        self.assertFalse(is_file_ext_supported(".hsdfh"))
        self.assertFalse(is_file_ext_supported(""))
