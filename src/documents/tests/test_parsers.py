from tempfile import TemporaryDirectory
from unittest import mock

from django.apps import apps
from django.test import TestCase
from django.test import override_settings

from documents.parsers import get_default_file_extension
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from paperless_tesseract.parsers import RasterisedDocumentParser
from paperless_text.parsers import TextDocumentParser
from paperless_tika.parsers import TikaDocumentParser


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
        with TemporaryDirectory():
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
    def test_tesseract_parser(self):
        """
        GIVEN:
            - Various mime types
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tesseract based parser is return
        """
        supported_mimes_and_exts = [
            ("application/pdf", ".pdf"),
            ("image/png", ".png"),
            ("image/jpeg", ".jpg"),
            ("image/tiff", ".tif"),
            ("image/webp", ".webp"),
        ]

        supported_exts = get_supported_file_extensions()

        for mime_type, ext in supported_mimes_and_exts:
            self.assertIn(ext, supported_exts)
            self.assertEqual(get_default_file_extension(mime_type), ext)
            self.assertIsInstance(
                get_parser_class_for_mime_type(mime_type)(logging_group=None),
                RasterisedDocumentParser,
            )

    def test_text_parser(self):
        """
        GIVEN:
            - Various mime types of a text form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The text based parser is return
        """
        supported_mimes_and_exts = [
            ("text/plain", ".txt"),
            ("text/csv", ".csv"),
        ]

        supported_exts = get_supported_file_extensions()

        for mime_type, ext in supported_mimes_and_exts:
            self.assertIn(ext, supported_exts)
            self.assertEqual(get_default_file_extension(mime_type), ext)
            self.assertIsInstance(
                get_parser_class_for_mime_type(mime_type)(logging_group=None),
                TextDocumentParser,
            )

    def test_tika_parser(self):
        """
        GIVEN:
            - Various mime types of a office document form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tika/Gotenberg based parser is return
        """
        supported_mimes_and_exts = [
            ("application/vnd.oasis.opendocument.text", ".odt"),
            ("text/rtf", ".rtf"),
            ("application/msword", ".doc"),
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
            ),
        ]

        # Force the app ready to notice the settings override
        with override_settings(TIKA_ENABLED=True, INSTALLED_APPS=["paperless_tika"]):
            app = apps.get_app_config("paperless_tika")
            app.ready()
            supported_exts = get_supported_file_extensions()

        for mime_type, ext in supported_mimes_and_exts:
            self.assertIn(ext, supported_exts)
            self.assertEqual(get_default_file_extension(mime_type), ext)
            self.assertIsInstance(
                get_parser_class_for_mime_type(mime_type)(logging_group=None),
                TikaDocumentParser,
            )

    def test_no_parser_for_mime(self):
        self.assertIsNone(get_parser_class_for_mime_type("text/sdgsdf"))

    def test_default_extension(self):
        # Test no parser declared still returns a an extension
        self.assertEqual(get_default_file_extension("application/zip"), ".zip")

        # Test invalid mimetype returns no extension
        self.assertEqual(get_default_file_extension("aasdasd/dgfgf"), "")

    def test_file_extension_support(self):
        self.assertTrue(is_file_ext_supported(".pdf"))
        self.assertFalse(is_file_ext_supported(".hsdfh"))
        self.assertFalse(is_file_ext_supported(""))
