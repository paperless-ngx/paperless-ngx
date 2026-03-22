import datetime
import zoneinfo
from http import HTTPStatus
from pathlib import Path

import pytest
from httpx import codes
from pytest_django.fixtures import SettingsWrapper
from pytest_httpx import HTTPXMock

from documents.parsers import ParseError
from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.tika import TikaDocumentParser


class TestTikaParserRegistryInterface:
    """Verify that TikaDocumentParser satisfies the ParserProtocol contract."""

    def test_satisfies_parser_protocol(self) -> None:
        assert isinstance(TikaDocumentParser(), ParserProtocol)

    def test_supported_mime_types_is_classmethod(self) -> None:
        mime_types = TikaDocumentParser.supported_mime_types()
        assert isinstance(mime_types, dict)
        assert len(mime_types) > 0

    def test_score_returns_none_when_tika_disabled(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.TIKA_ENABLED = False
        result = TikaDocumentParser.score(
            "application/vnd.oasis.opendocument.text",
            "sample.odt",
        )
        assert result is None

    def test_score_returns_int_when_tika_enabled(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.TIKA_ENABLED = True
        result = TikaDocumentParser.score(
            "application/vnd.oasis.opendocument.text",
            "sample.odt",
        )
        assert isinstance(result, int)

    def test_score_returns_none_for_unsupported_mime(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.TIKA_ENABLED = True
        result = TikaDocumentParser.score("application/pdf", "doc.pdf")
        assert result is None

    def test_can_produce_archive_is_false(self) -> None:
        assert TikaDocumentParser().can_produce_archive is False

    def test_requires_pdf_rendition_is_true(self) -> None:
        assert TikaDocumentParser().requires_pdf_rendition is True

    def test_get_page_count_returns_none_without_archive(
        self,
        tika_parser: TikaDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        assert (
            tika_parser.get_page_count(
                sample_odt_file,
                "application/vnd.oasis.opendocument.text",
            )
            is None
        )

    def test_get_page_count_returns_int_with_pdf_archive(
        self,
        tika_parser: TikaDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        tika_parser._archive_path = simple_digital_pdf_file
        count = tika_parser.get_page_count(simple_digital_pdf_file, "application/pdf")
        assert isinstance(count, int)
        assert count > 0


@pytest.mark.django_db()
class TestTikaParser:
    def test_parse(
        self,
        httpx_mock: HTTPXMock,
        settings: SettingsWrapper,
        tika_parser: TikaDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        settings.TIME_ZONE = "America/Chicago"
        # Pretend parse response
        httpx_mock.add_response(
            json={
                "Content-Type": "application/vnd.oasis.opendocument.text",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "the content",
                "dcterms:created": "2020-11-21T00:00:00",
            },
        )
        # Pretend convert to PDF response
        httpx_mock.add_response(content=b"PDF document")

        tika_parser.configure(ParserContext())
        tika_parser.parse(sample_odt_file, "application/vnd.oasis.opendocument.text")

        assert tika_parser.get_text() == "the content"
        assert tika_parser.get_archive_path() is not None
        with Path(tika_parser.get_archive_path()).open("rb") as f:
            assert f.read() == b"PDF document"

        assert tika_parser.get_date() == datetime.datetime(
            2020,
            11,
            21,
            tzinfo=zoneinfo.ZoneInfo("America/Chicago"),
        )

    def test_metadata(
        self,
        httpx_mock: HTTPXMock,
        tika_parser: TikaDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        httpx_mock.add_response(
            json={
                "Content-Type": "application/vnd.oasis.opendocument.text",
                "X-TIKA:Parsed-By": [],
                "Some-key": "value",
                "dcterms:created": "2020-11-21T00:00:00",
            },
        )

        metadata = tika_parser.extract_metadata(
            sample_odt_file,
            "application/vnd.oasis.opendocument.text",
        )

        assert "dcterms:created" in [m["key"] for m in metadata]
        assert "Some-key" in [m["key"] for m in metadata]

    def test_convert_failure(
        self,
        httpx_mock: HTTPXMock,
        tika_parser: TikaDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - Document needs to be converted to PDF
        WHEN:
            - Gotenberg server returns an error
        THEN:
            - Parse error is raised
        """
        # Pretend convert to PDF response
        httpx_mock.add_response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        with pytest.raises(ParseError):
            tika_parser._convert_to_pdf(sample_odt_file)

    @pytest.mark.parametrize(
        ("setting_value", "expected_form_value"),
        [
            ("pdfa", "PDF/A-2b"),
            ("pdfa-1", "PDF/A-2b"),
            ("pdfa-2", "PDF/A-2b"),
            ("pdfa-3", "PDF/A-3b"),
        ],
    )
    def test_request_pdf_a_format(
        self,
        setting_value: str,
        expected_form_value: str,
        httpx_mock: HTTPXMock,
        settings: SettingsWrapper,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - Document needs to be converted to PDF
        WHEN:
            - Specific PDF/A format requested
        THEN:
            - Request to Gotenberg contains the expected PDF/A format string
        """
        # Parser must be created after the setting is changed so that
        # OutputTypeConfig reads the correct value at __init__ time.
        settings.OCR_OUTPUT_TYPE = setting_value
        httpx_mock.add_response(
            status_code=codes.OK,
            content=b"PDF document",
            method="POST",
        )

        with TikaDocumentParser() as parser:
            parser._convert_to_pdf(sample_odt_file)

        request = httpx_mock.get_request()

        assert request is not None

        expected_field_name = "pdfa"

        content_type = request.headers["Content-Type"]
        assert "multipart/form-data" in content_type

        boundary = content_type.split("boundary=")[1]

        parts = request.content.split(f"--{boundary}".encode())

        form_field_found = any(
            f'name="{expected_field_name}"'.encode() in part
            and expected_form_value.encode() in part
            for part in parts
        )

        assert form_field_found

        httpx_mock.reset()
