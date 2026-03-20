from django.test import TestCase
from django.test import override_settings

from documents.parsers import get_default_file_extension
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.registry import reset_parser_registry
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser


class TestParserAvailability(TestCase):
    def test_tesseract_parser(self) -> None:
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
                get_parser_registry().get_parser_for_file(mime_type, "")(),
                RasterisedDocumentParser,
            )

    def test_text_parser(self) -> None:
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
                get_parser_registry().get_parser_for_file(mime_type, "")(),
                TextDocumentParser,
            )

    def test_tika_parser(self) -> None:
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

        self.addCleanup(reset_parser_registry)

        # Reset and rebuild the registry with Tika enabled.
        with override_settings(TIKA_ENABLED=True):
            reset_parser_registry()
            supported_exts = get_supported_file_extensions()

            for mime_type, ext in supported_mimes_and_exts:
                self.assertIn(ext, supported_exts)
                self.assertEqual(get_default_file_extension(mime_type), ext)
                self.assertIsInstance(
                    get_parser_registry().get_parser_for_file(mime_type, "")(),
                    TikaDocumentParser,
                )

    def test_no_parser_for_mime(self) -> None:
        self.assertIsNone(get_parser_registry().get_parser_for_file("text/sdgsdf", ""))

    def test_default_extension(self) -> None:
        # Test no parser declared still returns a an extension
        self.assertEqual(get_default_file_extension("application/zip"), ".zip")

        # Test invalid mimetype returns no extension
        self.assertEqual(get_default_file_extension("aasdasd/dgfgf"), "")

    def test_file_extension_support(self) -> None:
        self.assertTrue(is_file_ext_supported(".pdf"))
        self.assertFalse(is_file_ext_supported(".hsdfh"))
        self.assertFalse(is_file_ext_supported(""))
