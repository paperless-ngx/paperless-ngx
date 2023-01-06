from tempfile import TemporaryDirectory
from unittest import mock

from django.test import TestCase
from documents.parsers import get_default_file_extension
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from paperless_tesseract.parsers import RasterisedDocumentParser
from paperless_text.parsers import TextDocumentParser


class TestParserDiscovery(TestCase):
    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test_get_parser_class_1_parser(self, m, *args):
        """
        GIVEN:
            - Parser declared for a given mimetype
        WHEN:
            - Attempt to get parser for the mimetype
        THEN:
            - Declared parser class is returned
        """

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

        self.assertEqual(get_parser_class_for_mime_type("application/pdf"), DummyParser)

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test_get_parser_class_n_parsers(self, m, *args):
        """
        GIVEN:
            - Two parsers declared for a given mimetype
            - Second parser has a higher weight
        WHEN:
            - Attempt to get parser for the mimetype
        THEN:
            - Second parser class is returned
        """

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

        self.assertEqual(
            get_parser_class_for_mime_type("application/pdf"),
            DummyParser2,
        )

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test_get_parser_class_0_parsers(self, m, *args):
        """
        GIVEN:
            - No parsers are declared
        WHEN:
            - Attempt to get parser for the mimetype
        THEN:
            - No parser class is returned
        """
        m.return_value = []
        with TemporaryDirectory() as tmpdir:
            self.assertIsNone(get_parser_class_for_mime_type("application/pdf"))

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test_get_parser_class_no_valid_parser(self, m, *args):
        """
        GIVEN:
            - No parser declared for a given mimetype
            - Parser declared for a different mimetype
        WHEN:
            - Attempt to get parser for the given mimetype
        THEN:
            - No parser class is returned
        """

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

        self.assertIsNone(get_parser_class_for_mime_type("image/tiff"))


class TestParserAvailability(TestCase):
    def test_file_extensions(self):

        supported_mimes_and_exts = [
            ("application/pdf", ".pdf"),
            ("image/png", ".png"),
            ("image/jpeg", ".jpg"),
            ("image/tiff", ".tif"),
            ("image/webp", ".webp"),
            ("text/plain", ".txt"),
            ("text/csv", ".csv"),
        ]

        supported_exts = get_supported_file_extensions()

        for mime_type, ext in supported_mimes_and_exts:
            self.assertIn(ext, supported_exts)
            self.assertEqual(get_default_file_extension(mime_type), ext)

        # Test no parser declared still returns a an extension
        self.assertEqual(get_default_file_extension("application/zip"), ".zip")

        # Test invalid mimetype returns no extension
        self.assertEqual(get_default_file_extension("aasdasd/dgfgf"), "")

        self.assertIsInstance(
            get_parser_class_for_mime_type("application/pdf")(logging_group=None),
            RasterisedDocumentParser,
        )
        self.assertIsInstance(
            get_parser_class_for_mime_type("text/plain")(logging_group=None),
            TextDocumentParser,
        )
        self.assertIsNone(get_parser_class_for_mime_type("text/sdgsdf"))

        self.assertTrue(is_file_ext_supported(".pdf"))
        self.assertFalse(is_file_ext_supported(".hsdfh"))
        self.assertFalse(is_file_ext_supported(""))
