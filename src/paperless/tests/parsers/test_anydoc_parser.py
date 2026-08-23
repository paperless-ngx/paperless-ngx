from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pytest_django.fixtures import SettingsWrapper
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from documents.parsers import ParseError
from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.anydoc import AnydocDocumentParser

ODT_MIME = "application/vnd.oasis.opendocument.text"


def enable_anydoc(settings: SettingsWrapper, gotenberg: str = "") -> None:
    settings.ANYDOC_ENABLED = True
    settings.ANYDOC_GOTENBERG_ENDPOINT = gotenberg


class TestAnydocParserRegistryInterface:
    """Verify that AnydocDocumentParser satisfies the ParserProtocol contract."""

    def test_satisfies_parser_protocol(self) -> None:
        assert isinstance(AnydocDocumentParser(), ParserProtocol)

    def test_supported_mime_types_includes_office_and_pdf(self) -> None:
        mime_types = AnydocDocumentParser.supported_mime_types()
        assert isinstance(mime_types, dict)
        assert ODT_MIME in mime_types
        assert "application/pdf" in mime_types

    def test_score_returns_none_when_disabled(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.ANYDOC_ENABLED = False
        result = AnydocDocumentParser.score(ODT_MIME, "sample.odt")
        assert result is None

    def test_score_returns_10_for_office_when_enabled(
        self,
        settings: SettingsWrapper,
    ) -> None:
        enable_anydoc(settings)
        result = AnydocDocumentParser.score(ODT_MIME, "sample.odt")
        assert result == 10

    def test_score_returns_none_for_unknown_mime(
        self,
        settings: SettingsWrapper,
    ) -> None:
        enable_anydoc(settings)
        result = AnydocDocumentParser.score("application/x-unknown", "file.xyz")
        assert result is None

    def test_score_returns_none_for_pdf_without_path(
        self,
        settings: SettingsWrapper,
    ) -> None:
        enable_anydoc(settings)
        result = AnydocDocumentParser.score("application/pdf", "doc.pdf")
        assert result is None

    def test_score_claims_text_based_pdf(
        self,
        settings: SettingsWrapper,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - A born-digital PDF containing a text layer
        WHEN:
            - The parser scores the file
        THEN:
            - A score beating the Tesseract OCR parser (10) is returned
        """
        enable_anydoc(settings)
        result = AnydocDocumentParser.score(
            "application/pdf",
            "simple-digital.pdf",
            simple_digital_pdf_file,
        )
        assert result == 20

    def test_score_declines_scanned_pdf(
        self,
        settings: SettingsWrapper,
        multi_page_images_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - A scanned PDF without a text layer
        WHEN:
            - The parser scores the file
        THEN:
            - None is returned so the OCR parser handles it
        """
        enable_anydoc(settings)
        result = AnydocDocumentParser.score(
            "application/pdf",
            "multi-page-images.pdf",
            multi_page_images_pdf_file,
        )
        assert result is None

    def test_rendition_and_archive_follow_gotenberg_setting(
        self,
        settings: SettingsWrapper,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        parser = AnydocDocumentParser()
        assert parser.requires_pdf_rendition is False
        assert parser.can_produce_archive is False

        enable_anydoc(settings, gotenberg="http://localhost:3000")
        parser = AnydocDocumentParser()
        assert parser.requires_pdf_rendition is True
        assert parser.can_produce_archive is True


@pytest.mark.django_db()
class TestAnydocParserOfficeDocuments:
    def test_parse_without_gotenberg(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - Native parsing enabled and no Gotenberg endpoint
        WHEN:
            - An office document is parsed
        THEN:
            - Text comes from anydoc and no archive is produced
        """
        enable_anydoc(settings, gotenberg="")
        to_markdown = mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            return_value="# Invoice\n\nTotal: 42",
        )

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(sample_odt_file, ODT_MIME)

        to_markdown.assert_called_once_with(str(sample_odt_file))
        assert anydoc_parser.get_text() == "# Invoice\n\nTotal: 42"
        assert anydoc_parser.get_archive_path() is None
        assert anydoc_parser.get_date() is None

    def test_parse_with_gotenberg_rendition(
        self,
        httpx_mock: HTTPXMock,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - Native parsing enabled and a Gotenberg endpoint configured
        WHEN:
            - An office document is parsed
        THEN:
            - Text comes from anydoc and the Gotenberg PDF becomes the archive
        """
        enable_anydoc(settings, gotenberg="http://localhost:3000")
        mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            return_value="the content",
        )
        httpx_mock.add_response(content=b"%PDF-1.7 rendition")

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(sample_odt_file, ODT_MIME)

        assert anydoc_parser.get_text() == "the content"
        archive = anydoc_parser.get_archive_path()
        assert archive is not None
        with Path(archive).open("rb") as f:
            assert f.read() == b"%PDF-1.7 rendition"

    def test_unreachable_gotenberg_degrades_gracefully(
        self,
        httpx_mock: HTTPXMock,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - A configured Gotenberg endpoint that cannot be reached at all
        WHEN:
            - An office document is parsed
        THEN:
            - Text extraction still succeeds and the document is ingested
              without a PDF archive instead of failing
        """
        enable_anydoc(settings, gotenberg="http://unreachable:3000")
        mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            return_value="the content",
        )
        httpx_mock.add_exception(
            httpx.ConnectError("[Errno 99] Cannot assign requested address"),
        )

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(sample_odt_file, ODT_MIME)

        assert anydoc_parser.get_text() == "the content"
        assert anydoc_parser.get_archive_path() is None

    def test_parse_failure_raises_parse_error(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            side_effect=RuntimeError("boom"),
        )

        anydoc_parser.configure(ParserContext())
        with pytest.raises(ParseError):
            anydoc_parser.parse(sample_odt_file, ODT_MIME)

    def test_convert_failure_raises_parse_error(
        self,
        httpx_mock: HTTPXMock,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="http://localhost:3000")
        mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            return_value="the content",
        )
        httpx_mock.add_response(status_code=500)

        anydoc_parser.configure(ParserContext())
        with pytest.raises(ParseError):
            anydoc_parser.parse(sample_odt_file, ODT_MIME)

    def test_placeholder_thumbnail_without_gotenberg(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        mocker.patch(
            "paperless.parsers.anydoc.anydoc.to_markdown",
            return_value="thumbnail text",
        )

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(sample_odt_file, ODT_MIME)
        thumbnail = anydoc_parser.get_thumbnail(sample_odt_file, ODT_MIME)

        assert thumbnail.exists()
        assert thumbnail.suffix == ".webp"
        assert thumbnail.parent == anydoc_parser._tempdir


@pytest.mark.django_db()
class TestAnydocParserPdfs:
    @pytest.fixture()
    def pdf_result(self) -> SimpleNamespace:
        return SimpleNamespace(
            markdown="# Report\n\nBody text",
            page_count=7,
            pdf_type="text_based",
        )

    def test_parse_pdf_produces_archive_copy(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
        pdf_result: SimpleNamespace,
    ) -> None:
        """
        GIVEN:
            - A text-based PDF and produce_archive=True
        WHEN:
            - The document is parsed
        THEN:
            - Text and page count come from pdf-inspector and the archive is
              a byte-identical copy of the original
        """
        enable_anydoc(settings, gotenberg="")
        process = mocker.patch(
            "paperless.parsers.anydoc.pdf_inspector.process_pdf",
            return_value=pdf_result,
        )

        original_bytes = simple_digital_pdf_file.read_bytes()
        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(simple_digital_pdf_file, "application/pdf")

        process.assert_called_once_with(str(simple_digital_pdf_file))
        assert anydoc_parser.get_text() == "# Report\n\nBody text"
        assert (
            anydoc_parser.get_page_count(
                simple_digital_pdf_file,
                "application/pdf",
            )
            == 7
        )

        archive = anydoc_parser.get_archive_path()
        assert archive is not None
        assert archive.read_bytes() == original_bytes

    def test_parse_pdf_without_archive(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
        pdf_result: SimpleNamespace,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        mocker.patch(
            "paperless.parsers.anydoc.pdf_inspector.process_pdf",
            return_value=pdf_result,
        )

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        assert anydoc_parser.get_text() == "# Report\n\nBody text"
        assert anydoc_parser.get_archive_path() is None

    def test_parse_pdf_falls_back_to_extract_text(
        self,
        mocker: MockerFixture,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        mocker.patch(
            "paperless.parsers.anydoc.pdf_inspector.process_pdf",
            return_value=SimpleNamespace(markdown=None, page_count=2),
        )
        extract = mocker.patch(
            "paperless.parsers.anydoc.pdf_inspector.extract_text",
            return_value="plain fallback",
        )

        anydoc_parser.configure(ParserContext())
        anydoc_parser.parse(simple_digital_pdf_file, "application/pdf")

        extract.assert_called_once_with(str(simple_digital_pdf_file))
        assert anydoc_parser.get_text() == "plain fallback"

    def test_thumbnail_from_original_pdf(
        self,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        thumbnail = anydoc_parser.get_thumbnail(
            simple_digital_pdf_file,
            "application/pdf",
        )
        assert thumbnail.exists()

    def test_extract_metadata_from_pdf(
        self,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        metadata = anydoc_parser.extract_metadata(
            simple_digital_pdf_file,
            "application/pdf",
        )
        assert isinstance(metadata, list)


@pytest.mark.django_db()
class TestAnydocParserMetadataOffice:
    def test_office_metadata_is_empty(
        self,
        settings: SettingsWrapper,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        enable_anydoc(settings, gotenberg="")
        metadata = anydoc_parser.extract_metadata(sample_odt_file, ODT_MIME)
        assert metadata == []
