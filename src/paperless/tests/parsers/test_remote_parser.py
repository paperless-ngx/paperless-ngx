"""
Tests for paperless.parsers.remote.RemoteDocumentParser.

All tests use the context-manager protocol for parser lifecycle.

Fixture layout
--------------
make_azure_mock  — factory (defined here; specific to this module)
azure_client     — composes azure_settings + make_azure_mock + patch;
                   use when a test needs the client to succeed
failing_azure_client
                 — composes azure_settings + patch with RuntimeError;
                   use when a test needs the client to fail
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.remote import RemoteDocumentParser

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture


# ---------------------------------------------------------------------------
# Module-local fixtures
# ---------------------------------------------------------------------------

_AZURE_CLIENT_TARGET = "azure.ai.documentintelligence.DocumentIntelligenceClient"
_DEFAULT_TEXT = "Extracted text."


@pytest.fixture()
def make_azure_mock() -> Callable[[str], Mock]:
    """Return a factory that builds a mock Azure DocumentIntelligenceClient.

    Usage::

        mock_client = make_azure_mock()            # default extracted text
        mock_client = make_azure_mock("My text.")  # custom extracted text
    """

    def _factory(text: str = _DEFAULT_TEXT) -> Mock:
        mock_client = Mock()
        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_poller.details = {"operation_id": "fake-op-id"}
        mock_poller.result.return_value.content = text
        mock_client.begin_analyze_document.return_value = mock_poller
        mock_client.get_analyze_result_pdf.return_value = [b"%PDF-1.4 FAKE"]
        return mock_client

    return _factory


@pytest.fixture()
def azure_client(
    azure_settings: SettingsWrapper,
    make_azure_mock: Callable[[str], Mock],
    mocker: MockerFixture,
) -> Mock:
    """Patch the Azure DI client with a succeeding mock and return the instance.

    Implicitly applies ``azure_settings`` so tests using this fixture do not
    also need ``@pytest.mark.usefixtures("azure_settings")``.
    """
    mock_client = make_azure_mock()
    mocker.patch(_AZURE_CLIENT_TARGET, return_value=mock_client)
    return mock_client


@pytest.fixture()
def failing_azure_client(
    azure_settings: SettingsWrapper,
    mocker: MockerFixture,
) -> Mock:
    """Patch the Azure DI client to raise RuntimeError on every call.

    Implicitly applies ``azure_settings``.  Returns the mock instance so
    tests can assert on calls such as ``close()``.
    """
    mock_client = Mock()
    mock_client.begin_analyze_document.side_effect = RuntimeError("network failure")
    mocker.patch(_AZURE_CLIENT_TARGET, return_value=mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# Protocol contract
# ---------------------------------------------------------------------------


class TestRemoteParserProtocol:
    """Verify that RemoteDocumentParser satisfies the ParserProtocol contract."""

    def test_isinstance_satisfies_protocol(
        self,
        remote_parser: RemoteDocumentParser,
    ) -> None:
        assert isinstance(remote_parser, ParserProtocol)

    def test_class_attributes_present(self) -> None:
        assert isinstance(RemoteDocumentParser.name, str) and RemoteDocumentParser.name
        assert (
            isinstance(RemoteDocumentParser.version, str)
            and RemoteDocumentParser.version
        )
        assert (
            isinstance(RemoteDocumentParser.author, str) and RemoteDocumentParser.author
        )
        assert isinstance(RemoteDocumentParser.url, str) and RemoteDocumentParser.url


# ---------------------------------------------------------------------------
# supported_mime_types
# ---------------------------------------------------------------------------


class TestRemoteParserSupportedMimeTypes:
    """supported_mime_types() always returns the full set regardless of config."""

    def test_returns_dict(self) -> None:
        mime_types = RemoteDocumentParser.supported_mime_types()
        assert isinstance(mime_types, dict)

    def test_includes_all_expected_types(self) -> None:
        mime_types = RemoteDocumentParser.supported_mime_types()
        expected = {
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "image/webp",
        }
        assert expected == set(mime_types.keys())

    @pytest.mark.usefixtures("no_engine_settings")
    def test_returns_full_set_when_not_configured(self) -> None:
        """
        GIVEN: No remote engine is configured
        WHEN:  supported_mime_types() is called
        THEN:  The full MIME type dict is still returned (score() handles activation)
        """
        mime_types = RemoteDocumentParser.supported_mime_types()
        assert len(mime_types) == 7


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


class TestRemoteParserScore:
    """score() encodes the activation logic: None when unconfigured, 20 when active."""

    @pytest.mark.usefixtures("azure_settings")
    @pytest.mark.parametrize(
        "mime_type",
        [
            pytest.param("application/pdf", id="pdf"),
            pytest.param("image/png", id="png"),
            pytest.param("image/jpeg", id="jpeg"),
            pytest.param("image/tiff", id="tiff"),
            pytest.param("image/bmp", id="bmp"),
            pytest.param("image/gif", id="gif"),
            pytest.param("image/webp", id="webp"),
        ],
    )
    def test_score_returns_20_when_configured(self, mime_type: str) -> None:
        result = RemoteDocumentParser.score(mime_type, "doc.pdf")
        assert result == 20

    @pytest.mark.usefixtures("no_engine_settings")
    @pytest.mark.parametrize(
        "mime_type",
        [
            pytest.param("application/pdf", id="pdf"),
            pytest.param("image/png", id="png"),
            pytest.param("image/jpeg", id="jpeg"),
        ],
    )
    def test_score_returns_none_when_no_engine(self, mime_type: str) -> None:
        result = RemoteDocumentParser.score(mime_type, "doc.pdf")
        assert result is None

    def test_score_returns_none_when_api_key_missing(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.REMOTE_OCR_ENGINE = "azureai"
        settings.REMOTE_OCR_API_KEY = None
        settings.REMOTE_OCR_ENDPOINT = "https://test.cognitiveservices.azure.com"
        result = RemoteDocumentParser.score("application/pdf", "doc.pdf")
        assert result is None

    def test_score_returns_none_when_endpoint_missing(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.REMOTE_OCR_ENGINE = "azureai"
        settings.REMOTE_OCR_API_KEY = "key"
        settings.REMOTE_OCR_ENDPOINT = None
        result = RemoteDocumentParser.score("application/pdf", "doc.pdf")
        assert result is None

    @pytest.mark.usefixtures("azure_settings")
    def test_score_returns_none_for_unsupported_mime_type(self) -> None:
        result = RemoteDocumentParser.score("text/plain", "doc.txt")
        assert result is None

    @pytest.mark.usefixtures("azure_settings")
    def test_score_higher_than_tesseract_default(self) -> None:
        """Remote parser (20) outranks the tesseract default (10) when configured."""
        score = RemoteDocumentParser.score("application/pdf", "doc.pdf")
        assert score is not None and score > 10


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestRemoteParserProperties:
    def test_can_produce_archive_is_true(
        self,
        remote_parser: RemoteDocumentParser,
    ) -> None:
        assert remote_parser.can_produce_archive is True

    def test_requires_pdf_rendition_is_false(
        self,
        remote_parser: RemoteDocumentParser,
    ) -> None:
        assert remote_parser.requires_pdf_rendition is False


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestRemoteParserLifecycle:
    def test_context_manager_cleans_up_tempdir(self) -> None:
        with RemoteDocumentParser() as parser:
            tempdir = parser._tempdir
            assert tempdir.exists()
        assert not tempdir.exists()

    def test_context_manager_cleans_up_after_exception(self) -> None:
        tempdir: Path | None = None
        with pytest.raises(RuntimeError):
            with RemoteDocumentParser() as parser:
                tempdir = parser._tempdir
                raise RuntimeError("boom")
        assert tempdir is not None
        assert not tempdir.exists()


# ---------------------------------------------------------------------------
# parse() — happy path
# ---------------------------------------------------------------------------


class TestRemoteParserParse:
    def test_parse_returns_text_from_azure(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        assert remote_parser.get_text() == _DEFAULT_TEXT

    def test_parse_sets_archive_path(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        archive = remote_parser.get_archive_path()
        assert archive is not None
        assert archive.exists()
        assert archive.suffix == ".pdf"

    def test_parse_closes_client_on_success(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        remote_parser.configure(ParserContext())
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        azure_client.close.assert_called_once()

    @pytest.mark.usefixtures("no_engine_settings")
    def test_parse_sets_empty_text_when_not_configured(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        assert remote_parser.get_text() == ""
        assert remote_parser.get_archive_path() is None

    def test_get_text_empty_before_parse(
        self,
        remote_parser: RemoteDocumentParser,
    ) -> None:
        assert remote_parser.get_text() == ""

    def test_get_date_always_none(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        assert remote_parser.get_date() is None


# ---------------------------------------------------------------------------
# parse() — Azure failure path
# ---------------------------------------------------------------------------


class TestRemoteParserParseError:
    def test_parse_returns_empty_on_azure_error(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        failing_azure_client: Mock,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        assert remote_parser.get_text() == ""

    def test_parse_closes_client_on_error(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        failing_azure_client: Mock,
    ) -> None:
        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        failing_azure_client.close.assert_called_once()

    def test_parse_logs_error_on_azure_failure(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        failing_azure_client: Mock,
        mocker: MockerFixture,
    ) -> None:
        mock_log = mocker.patch("paperless.parsers.remote.logger")

        remote_parser.parse(simple_digital_pdf_file, "application/pdf")

        mock_log.exception.assert_called_once()
        assert "Azure AI Vision parsing failed" in mock_log.exception.call_args[0][0]


# ---------------------------------------------------------------------------
# get_page_count()
# ---------------------------------------------------------------------------


class TestRemoteParserPageCount:
    def test_page_count_for_pdf(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        count = remote_parser.get_page_count(simple_digital_pdf_file, "application/pdf")
        assert isinstance(count, int)
        assert count >= 1

    def test_page_count_returns_none_for_image_mime(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        count = remote_parser.get_page_count(simple_digital_pdf_file, "image/png")
        assert count is None

    def test_page_count_returns_none_for_invalid_pdf(
        self,
        remote_parser: RemoteDocumentParser,
        tmp_path: Path,
    ) -> None:
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"not a pdf at all")
        count = remote_parser.get_page_count(bad_pdf, "application/pdf")
        assert count is None


# ---------------------------------------------------------------------------
# extract_metadata()
# ---------------------------------------------------------------------------


class TestRemoteParserMetadata:
    def test_extract_metadata_non_pdf_returns_empty(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(simple_digital_pdf_file, "image/png")
        assert result == []

    def test_extract_metadata_pdf_returns_list(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(
            simple_digital_pdf_file,
            "application/pdf",
        )
        assert isinstance(result, list)

    def test_extract_metadata_pdf_entries_have_required_keys(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(
            simple_digital_pdf_file,
            "application/pdf",
        )
        for entry in result:
            assert "namespace" in entry
            assert "prefix" in entry
            assert "key" in entry
            assert "value" in entry
            assert isinstance(entry["value"], str)

    def test_extract_metadata_does_not_raise_on_invalid_pdf(
        self,
        remote_parser: RemoteDocumentParser,
        tmp_path: Path,
    ) -> None:
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"not a pdf at all")
        result = remote_parser.extract_metadata(bad_pdf, "application/pdf")
        assert result == []


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRemoteParserRegistry:
    def test_registered_in_defaults(self) -> None:
        from paperless.parsers.registry import ParserRegistry

        registry = ParserRegistry()
        registry.register_defaults()

        assert RemoteDocumentParser in registry._builtins

    @pytest.mark.usefixtures("azure_settings")
    def test_get_parser_returns_remote_when_configured(self) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        parser_cls = registry.get_parser_for_file("application/pdf", "doc.pdf")

        assert parser_cls is RemoteDocumentParser

    @pytest.mark.usefixtures("no_engine_settings")
    def test_get_parser_returns_none_for_unsupported_type_when_not_configured(
        self,
    ) -> None:
        """With remote off and a truly unsupported MIME type, registry returns None."""
        from paperless.parsers.registry import ParserRegistry

        registry = ParserRegistry()
        registry.register_defaults()
        parser_cls = registry.get_parser_for_file(
            "application/x-unknown-format",
            "doc.xyz",
        )

        assert parser_cls is None


# ---------------------------------------------------------------------------
# Mistral engine — helpers
# ---------------------------------------------------------------------------

_MISTRAL_URL = "https://api.mistral.ai/v1/ocr"


def _mistral_response(text: str = _DEFAULT_TEXT) -> dict:
    """Build a minimal Mistral OCR API response with one positioned block."""
    return {
        "pages": [
            {
                "index": 0,
                "markdown": text,
                "dimensions": {"dpi": 200, "width": 800, "height": 1000},
                "blocks": [{"bbox": [50, 50, 700, 120], "markdown": text}],
            },
        ],
        "model": "mistral-ocr-latest",
        "usage_info": {},
    }


class TestMistralHelpers:
    """Unit tests for the pure, framework-independent Mistral helpers."""

    def test_pages_to_text_joins_and_skips_blank(self) -> None:
        from paperless.parsers.remote import _mistral_pages_to_text

        pages = [
            {"markdown": "Page one."},
            {"markdown": "   "},
            {"markdown": "Page two."},
            {},
        ]
        assert _mistral_pages_to_text(pages) == "Page one.\n\nPage two."

    def test_data_uri_roundtrip(self) -> None:
        import base64

        from paperless.parsers.remote import _data_uri

        uri = _data_uri("application/pdf", b"%PDF-1.4 hello")
        assert uri.startswith("data:application/pdf;base64,")
        payload = uri.split(",", 1)[1]
        assert base64.b64decode(payload) == b"%PDF-1.4 hello"

    @pytest.mark.parametrize(
        "block",
        [
            pytest.param({"bbox": [1, 2, 3, 4]}, id="list"),
            pytest.param(
                {"bbox": {"left": 1, "top": 2, "right": 3, "bottom": 4}},
                id="edge-dict",
            ),
            pytest.param(
                {
                    "top_left_x": 1,
                    "top_left_y": 2,
                    "bottom_right_x": 3,
                    "bottom_right_y": 4,
                },
                id="corner-keys",
            ),
        ],
    )
    def test_block_bounding_box_variants(self, block: dict) -> None:
        from paperless.parsers.remote import _block_bounding_box

        assert _block_bounding_box(block) == (1.0, 2.0, 3.0, 4.0)

    def test_block_bounding_box_missing_returns_none(self) -> None:
        from paperless.parsers.remote import _block_bounding_box

        assert _block_bounding_box({"markdown": "no box"}) is None

    def test_build_ocr_page_uses_blocks(self) -> None:
        from paperless.parsers.remote import _build_ocr_page

        page = _build_ocr_page(_mistral_response()["pages"][0], 800, 1000, 200)
        assert page.ocr_class == "ocr_page"
        words = page.words
        assert words and words[0].text == _DEFAULT_TEXT

    def test_build_ocr_page_falls_back_to_markdown(self) -> None:
        from paperless.parsers.remote import _build_ocr_page

        page_data = {"index": 0, "markdown": "Only text, no boxes."}
        page = _build_ocr_page(page_data, 800, 1000, 200)
        assert any(w.text == "Only text, no boxes." for w in page.words)


# ---------------------------------------------------------------------------
# Mistral engine — score()
# ---------------------------------------------------------------------------


class TestMistralScore:
    @pytest.mark.usefixtures("mistral_settings")
    def test_score_returns_20_when_configured(self) -> None:
        assert RemoteDocumentParser.score("application/pdf", "doc.pdf") == 20

    def test_score_returns_20_without_endpoint(
        self,
        settings: SettingsWrapper,
    ) -> None:
        """Mistral does not require an endpoint (it defaults to the hosted API)."""
        settings.REMOTE_OCR_ENGINE = "mistral"
        settings.REMOTE_OCR_API_KEY = "key"
        settings.REMOTE_OCR_ENDPOINT = None
        assert RemoteDocumentParser.score("application/pdf", "doc.pdf") == 20

    def test_score_returns_none_when_api_key_missing(
        self,
        settings: SettingsWrapper,
    ) -> None:
        settings.REMOTE_OCR_ENGINE = "mistral"
        settings.REMOTE_OCR_API_KEY = None
        settings.REMOTE_OCR_ENDPOINT = None
        assert RemoteDocumentParser.score("application/pdf", "doc.pdf") is None


# ---------------------------------------------------------------------------
# Mistral engine — parse()
# ---------------------------------------------------------------------------


class TestMistralParse:
    def test_parse_returns_text(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
    ) -> None:
        httpx_mock.add_response(url=_MISTRAL_URL, json=_mistral_response())

        remote_parser.parse(simple_png_file, "image/png")

        assert remote_parser.get_text() == _DEFAULT_TEXT

    def test_parse_builds_valid_archive_pdf(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
    ) -> None:
        import pikepdf

        httpx_mock.add_response(url=_MISTRAL_URL, json=_mistral_response())

        remote_parser.parse(simple_png_file, "image/png")

        archive = remote_parser.get_archive_path()
        assert archive is not None
        assert archive.exists()
        assert archive.suffix == ".pdf"
        with pikepdf.open(archive) as pdf:
            assert len(pdf.pages) == 1

    def test_parse_archive_is_searchable(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
    ) -> None:
        extract_text = pytest.importorskip("pdfminer.high_level").extract_text

        httpx_mock.add_response(
            url=_MISTRAL_URL,
            json=_mistral_response("Rechnung Grüße"),
        )

        remote_parser.parse(simple_png_file, "image/png")

        archive = remote_parser.get_archive_path()
        assert archive is not None
        assert "Rechnung Grüße" in extract_text(str(archive))

    def test_parse_sends_expected_request(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
    ) -> None:
        import json

        httpx_mock.add_response(url=_MISTRAL_URL, json=_mistral_response())

        remote_parser.parse(simple_png_file, "image/png")

        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer test-api-key"
        body = json.loads(request.content)
        assert body["model"] == "mistral-ocr-latest"
        assert body["include_blocks"] is True
        assert body["document"]["type"] == "image_url"
        assert body["document"]["image_url"].startswith("data:image/png;base64,")

    @pytest.mark.usefixtures("no_engine_settings")
    def test_parse_sets_empty_text_when_not_configured(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
    ) -> None:
        remote_parser.parse(simple_png_file, "image/png")

        assert remote_parser.get_text() == ""
        assert remote_parser.get_archive_path() is None


# ---------------------------------------------------------------------------
# Mistral engine — failure path
# ---------------------------------------------------------------------------


class TestMistralParseError:
    def test_parse_returns_empty_on_http_error(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
    ) -> None:
        httpx_mock.add_response(url=_MISTRAL_URL, status_code=500)

        remote_parser.parse(simple_png_file, "image/png")

        assert remote_parser.get_text() == ""
        assert remote_parser.get_archive_path() is None

    def test_parse_logs_error_on_failure(
        self,
        remote_parser: RemoteDocumentParser,
        simple_png_file: Path,
        mistral_settings: SettingsWrapper,
        httpx_mock,
        mocker: MockerFixture,
    ) -> None:
        httpx_mock.add_response(url=_MISTRAL_URL, status_code=500)
        mock_log = mocker.patch("paperless.parsers.remote.logger")

        remote_parser.parse(simple_png_file, "image/png")

        mock_log.exception.assert_called_once()
        assert "Mistral OCR parsing failed" in mock_log.exception.call_args[0][0]
