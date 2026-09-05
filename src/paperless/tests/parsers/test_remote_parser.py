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

from documents.parsers import ParseError
from paperless.models import ApplicationConfiguration
from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.remote import RemoteDocumentParser

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_django.fixtures import Settings
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
    azure_settings: Settings,
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
    azure_settings: Settings,
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
        no_engine_settings: Settings,
    ) -> None:
        no_engine_settings.REMOTE_OCR_ENGINE = "azureai"
        no_engine_settings.REMOTE_OCR_ENDPOINT = (
            "https://test.cognitiveservices.azure.com"
        )
        result = RemoteDocumentParser.score("application/pdf", "doc.pdf")
        assert result is None

    def test_score_returns_none_when_endpoint_missing(
        self,
        no_engine_settings: Settings,
    ) -> None:
        no_engine_settings.REMOTE_OCR_ENGINE = "azureai"
        no_engine_settings.REMOTE_OCR_API_KEY = "key"
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

    @pytest.mark.django_db
    def test_score_uses_app_config_when_env_unset(
        self,
        settings: Settings,
    ) -> None:
        """The app config alone is enough to activate the parser."""
        settings.REMOTE_OCR_ENGINE = None
        settings.REMOTE_OCR_API_KEY = None
        settings.REMOTE_OCR_ENDPOINT = None
        config = ApplicationConfiguration.objects.first()
        assert config is not None
        config.remote_ocr_engine = "azureai"
        config.remote_ocr_api_key = "app-config-key"
        config.remote_ocr_endpoint = "https://config.cognitiveservices.azure.com"
        config.save()

        assert RemoteDocumentParser.score("application/pdf", "doc.pdf") == 20


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
# parse() — produce_archive=False skips the remote engine (PDFs only)
# ---------------------------------------------------------------------------


class TestRemoteParserSkipsWhenNoArchiveWanted:
    """When the caller has already decided no archive is needed for a PDF
    (documents.consumer.should_produce_archive), the remote engine call is
    skipped entirely in favor of locally-extracted text.
    """

    def test_pdf_skips_azure_when_no_archive_requested(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        """
        GIVEN: produce_archive=False for a PDF
        WHEN:  parse() is called
        THEN:  Azure is never invoked, no archive is produced, and text
               comes from local pdftotext extraction
        """
        remote_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        azure_client.begin_analyze_document.assert_not_called()
        assert remote_parser.get_archive_path() is None
        assert remote_parser.get_text() != ""

    def test_pdf_no_archive_requested_text_matches_local_extraction(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN: produce_archive=False for a PDF
        WHEN:  parse() is called
        THEN:  the returned text is exactly the locally-extracted text,
               not anything from the (unused) Azure mock
        """
        mocker.patch(
            "paperless.parsers.remote.extract_pdf_text",
            return_value="Local digital text.",
        )

        remote_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        assert remote_parser.get_text() == "Local digital text."

    def test_pdf_no_archive_requested_closes_no_client(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        remote_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        azure_client.close.assert_not_called()

    def test_non_pdf_still_calls_azure_when_no_archive_requested(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        azure_client: Mock,
    ) -> None:
        """
        Images have no local-text fallback, so produce_archive=False does
        not skip the remote engine for non-PDF MIME types.
        """
        remote_parser.parse(
            simple_digital_pdf_file,
            "image/png",
            produce_archive=False,
        )

        azure_client.begin_analyze_document.assert_called_once()
        assert remote_parser.get_text() == _DEFAULT_TEXT

    @pytest.mark.usefixtures("no_engine_settings")
    def test_unconfigured_engine_takes_precedence_over_skip(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """An unconfigured engine still short-circuits before the
        produce_archive check, returning empty text as before.
        """
        remote_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        assert remote_parser.get_text() == ""
        assert remote_parser.get_archive_path() is None


# ---------------------------------------------------------------------------
# parse() — Azure failure path
# ---------------------------------------------------------------------------


class TestRemoteParserParseError:
    def test_parse_raises_parse_error_on_azure_error(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        failing_azure_client: Mock,
    ) -> None:
        with pytest.raises(ParseError, match="Azure AI Vision parsing failed"):
            remote_parser.parse(simple_digital_pdf_file, "application/pdf")

    def test_parse_closes_client_on_error(
        self,
        remote_parser: RemoteDocumentParser,
        simple_digital_pdf_file: Path,
        failing_azure_client: Mock,
    ) -> None:
        with pytest.raises(ParseError):
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

        with pytest.raises(ParseError):
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
