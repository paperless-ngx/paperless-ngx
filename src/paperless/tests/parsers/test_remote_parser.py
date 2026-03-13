"""
Tests for paperless.parsers.remote.RemoteDocumentParser.

All tests use the context-manager protocol for parser lifecycle.  The Azure
AI client is always mocked via the ``mocker`` fixture so no real network
calls are made.  Django settings are overridden via the pytest-django
``settings`` fixture (or the ``azure_settings`` / ``no_engine_settings``
helpers defined in conftest.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from paperless.parsers import ParserProtocol
from paperless.parsers.remote import RemoteDocumentParser

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_azure_mock(text: str = "Extracted text.") -> Mock:
    """Return a configured mock Azure DocumentIntelligenceClient."""
    mock_client = Mock()
    mock_poller = Mock()
    mock_poller.wait.return_value = None
    mock_poller.details = {"operation_id": "fake-op-id"}
    mock_poller.result.return_value.content = text
    mock_client.begin_analyze_document.return_value = mock_poller
    mock_client.get_analyze_result_pdf.return_value = [b"%PDF-1.4 FAKE"]
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

    def test_returns_full_set_when_not_configured(
        self,
        no_engine_settings: SettingsWrapper,
    ) -> None:
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

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "image/webp",
        ],
    )
    def test_score_returns_20_when_configured(
        self,
        azure_settings: SettingsWrapper,
        mime_type: str,
    ) -> None:
        result = RemoteDocumentParser.score(mime_type, "doc.pdf")
        assert result == 20

    @pytest.mark.parametrize(
        "mime_type",
        ["application/pdf", "image/png", "image/jpeg"],
    )
    def test_score_returns_none_when_no_engine(
        self,
        no_engine_settings: SettingsWrapper,
        mime_type: str,
    ) -> None:
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

    def test_score_returns_none_for_unsupported_mime_type(
        self,
        azure_settings: SettingsWrapper,
    ) -> None:
        result = RemoteDocumentParser.score("text/plain", "doc.txt")
        assert result is None

    def test_score_higher_than_tesseract_default(
        self,
        azure_settings: SettingsWrapper,
    ) -> None:
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
# parse() — happy path with Azure mock
# ---------------------------------------------------------------------------


class TestRemoteParserParse:
    def test_parse_returns_text_from_azure(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = _make_azure_mock("Hello from Azure.")
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        assert remote_parser.get_text() == "Hello from Azure."

    def test_parse_sets_archive_path(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = _make_azure_mock()
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        archive = remote_parser.get_archive_path()
        assert archive is not None
        assert archive.exists()
        assert archive.suffix == ".pdf"

    def test_parse_closes_client_on_success(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = _make_azure_mock()
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        mock_client.close.assert_called_once()

    def test_parse_sets_empty_text_when_not_configured(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        no_engine_settings: SettingsWrapper,
    ) -> None:
        remote_parser.parse(sample_pdf_file, "application/pdf")

        assert remote_parser.get_text() == ""
        assert remote_parser.get_archive_path() is None

    def test_get_text_none_before_parse(
        self,
        remote_parser: RemoteDocumentParser,
    ) -> None:
        assert remote_parser.get_text() is None

    def test_get_date_always_none(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = _make_azure_mock()
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        assert remote_parser.get_date() is None


# ---------------------------------------------------------------------------
# parse() — Azure failure path
# ---------------------------------------------------------------------------


class TestRemoteParserParseError:
    def test_parse_returns_none_on_azure_error(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = Mock()
        mock_client.begin_analyze_document.side_effect = RuntimeError("network failure")
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        assert remote_parser.get_text() is None

    def test_parse_closes_client_on_error(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = Mock()
        mock_client.begin_analyze_document.side_effect = RuntimeError("network failure")
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )

        remote_parser.parse(sample_pdf_file, "application/pdf")

        mock_client.close.assert_called_once()

    def test_parse_logs_error_on_azure_failure(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
        azure_settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mock_client = Mock()
        mock_client.begin_analyze_document.side_effect = RuntimeError("network failure")
        mocker.patch(
            "azure.ai.documentintelligence.DocumentIntelligenceClient",
            return_value=mock_client,
        )
        mock_log = mocker.patch("paperless.parsers.remote.logger")

        remote_parser.parse(sample_pdf_file, "application/pdf")

        mock_log.error.assert_called_once()
        assert "Azure AI Vision parsing failed" in mock_log.error.call_args[0][0]


# ---------------------------------------------------------------------------
# get_page_count()
# ---------------------------------------------------------------------------


class TestRemoteParserPageCount:
    def test_page_count_for_pdf(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
    ) -> None:
        count = remote_parser.get_page_count(sample_pdf_file, "application/pdf")
        assert isinstance(count, int)
        assert count >= 1

    def test_page_count_returns_none_for_image_mime(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
    ) -> None:
        count = remote_parser.get_page_count(sample_pdf_file, "image/png")
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
        sample_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(sample_pdf_file, "image/png")
        assert result == []

    def test_extract_metadata_pdf_returns_list(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(sample_pdf_file, "application/pdf")
        assert isinstance(result, list)

    def test_extract_metadata_pdf_entries_have_required_keys(
        self,
        remote_parser: RemoteDocumentParser,
        sample_pdf_file: Path,
    ) -> None:
        result = remote_parser.extract_metadata(sample_pdf_file, "application/pdf")
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

    def test_get_parser_returns_remote_when_configured(
        self,
        azure_settings: SettingsWrapper,
    ) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        parser_cls = registry.get_parser_for_file("application/pdf", "doc.pdf")

        assert parser_cls is RemoteDocumentParser

    def test_get_parser_returns_none_for_pdf_when_not_configured(
        self,
        no_engine_settings: SettingsWrapper,
    ) -> None:
        """With no tesseract parser registered yet, PDF has no handler if remote is off."""
        from paperless.parsers.registry import ParserRegistry

        registry = ParserRegistry()
        registry.register_defaults()
        parser_cls = registry.get_parser_for_file("application/pdf", "doc.pdf")

        assert parser_cls is None
