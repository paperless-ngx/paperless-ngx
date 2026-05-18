from collections.abc import Generator

import pytest
from pytest_django.fixtures import SettingsWrapper

from documents.parsers import get_default_file_extension
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.registry import reset_parser_registry
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser


@pytest.fixture()
def _tika_registry(settings: SettingsWrapper) -> Generator[None, None, None]:
    """
    Rebuild the parser registry with Tika enabled for the duration of the
    test, then reset on exit so other tests see the default (Tika-disabled)
    registry.
    """
    settings.TIKA_ENABLED = True
    reset_parser_registry()
    yield
    reset_parser_registry()


@pytest.mark.django_db
class TestParserAvailability:
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("application/pdf", ".pdf", id="pdf"),
            pytest.param("image/png", ".png", id="png"),
            pytest.param("image/jpeg", ".jpg", id="jpeg"),
            pytest.param("image/tiff", ".tif", id="tiff"),
            pytest.param("image/webp", ".webp", id="webp"),
        ],
    )
    def test_tesseract_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tesseract based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            RasterisedDocumentParser,
        )

    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("text/plain", ".txt", id="plain"),
            pytest.param("text/csv", ".csv", id="csv"),
        ],
    )
    def test_text_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of a text form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The text based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TextDocumentParser,
        )

    @pytest.mark.usefixtures("_tika_registry")
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param(
                "application/vnd.oasis.opendocument.text",
                ".odt",
                id="odt",
            ),
            pytest.param("text/rtf", ".rtf", id="rtf"),
            pytest.param("application/msword", ".doc", id="doc"),
            pytest.param(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
                id="docx",
            ),
        ],
    )
    def test_tika_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of an office document form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tika/Gotenberg based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TikaDocumentParser,
        )

    def test_no_parser_for_mime(self) -> None:
        assert get_parser_registry().get_parser_for_file("text/sdgsdf", "") is None

    def test_default_extension(self) -> None:
        # Test no parser declared still returns an extension
        assert get_default_file_extension("application/zip") == ".zip"

        # Test invalid mimetype returns no extension
        assert get_default_file_extension("aasdasd/dgfgf") == ""

    def test_file_extension_support(self) -> None:
        assert is_file_ext_supported(".pdf")
        assert not is_file_ext_supported(".hsdfh")
        assert not is_file_ext_supported("")
