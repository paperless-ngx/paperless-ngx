"""Tests for should_produce_archive()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import override_settings

from documents.consumer import should_produce_archive


def _parser_instance(
    *,
    can_produce: bool = True,
    requires_rendition: bool = False,
) -> MagicMock:
    """Return a mock parser instance with the given capability flags."""
    instance = MagicMock()
    instance.can_produce_archive = can_produce
    instance.requires_pdf_rendition = requires_rendition
    return instance


@pytest.fixture()
def null_app_config(mocker) -> MagicMock:
    """Mock ApplicationConfiguration with all fields None → falls back to Django settings."""
    return mocker.MagicMock(
        output_type=None,
        pages=None,
        language=None,
        mode=None,
        archive_file_generation=None,
        image_dpi=None,
        unpaper_clean=None,
        deskew=None,
        rotate_pages=None,
        rotate_pages_threshold=None,
        max_image_pixels=None,
        color_conversion_strategy=None,
        user_args=None,
    )


@pytest.fixture(autouse=True)
def patch_app_config(mocker, null_app_config):
    """Patch BaseConfig._get_config_instance for all tests in this module."""
    mocker.patch(
        "paperless.config.BaseConfig._get_config_instance",
        return_value=null_app_config,
    )


class TestShouldProduceArchive:
    @override_settings(ARCHIVE_FILE_GENERATION="never")
    def test_never_setting_returns_false(self) -> None:
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        result = should_produce_archive(
            parser,
            "application/pdf",
            Path("/tmp/doc.pdf"),
        )
        assert result is False

    @override_settings(ARCHIVE_FILE_GENERATION="always")
    def test_always_setting_returns_true(self) -> None:
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        result = should_produce_archive(
            parser,
            "application/pdf",
            Path("/tmp/doc.pdf"),
        )
        assert result is True

    @override_settings(ARCHIVE_FILE_GENERATION="never")
    def test_requires_pdf_rendition_overrides_never(self) -> None:
        """requires_pdf_rendition=True forces archive even when setting is never."""
        parser = _parser_instance(can_produce=True, requires_rendition=True)
        result = should_produce_archive(
            parser,
            "application/pdf",
            Path("/tmp/doc.pdf"),
        )
        assert result is True

    @override_settings(ARCHIVE_FILE_GENERATION="always")
    def test_cannot_produce_archive_overrides_always(self) -> None:
        """can_produce_archive=False prevents archive even when setting is always."""
        parser = _parser_instance(can_produce=False, requires_rendition=False)
        result = should_produce_archive(parser, "text/plain", Path("/tmp/doc.txt"))
        assert result is False

    @override_settings(ARCHIVE_FILE_GENERATION="auto")
    def test_auto_image_returns_true(self) -> None:
        """auto mode: image/* MIME types always produce archive (scanned doc)."""
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        result = should_produce_archive(parser, "image/tiff", Path("/tmp/scan.tiff"))
        assert result is True

    @override_settings(ARCHIVE_FILE_GENERATION="auto")
    def test_auto_born_digital_pdf_returns_false(self) -> None:
        """auto mode: PDF with substantial text (born-digital) skips archive."""
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        long_text = "This is a born-digital PDF with lots of text content. " * 10
        with patch(
            "documents.consumer.extract_pdf_text",
            return_value=long_text,
        ):
            result = should_produce_archive(
                parser,
                "application/pdf",
                Path("/tmp/doc.pdf"),
            )
        assert result is False

    @override_settings(ARCHIVE_FILE_GENERATION="auto")
    def test_auto_scanned_pdf_no_text_returns_true(self) -> None:
        """auto mode: PDF where pdftotext returns None (scanned) produces archive."""
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        with patch(
            "documents.consumer.extract_pdf_text",
            return_value=None,
        ):
            result = should_produce_archive(
                parser,
                "application/pdf",
                Path("/tmp/scan.pdf"),
            )
        assert result is True

    @override_settings(ARCHIVE_FILE_GENERATION="auto")
    def test_auto_pdf_short_text_returns_true(self) -> None:
        """auto mode: PDF with very short text (<=50 chars) is treated as scanned."""
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        with patch(
            "documents.consumer.extract_pdf_text",
            return_value="tiny",
        ):
            result = should_produce_archive(
                parser,
                "application/pdf",
                Path("/tmp/scan.pdf"),
            )
        assert result is True

    @override_settings(ARCHIVE_FILE_GENERATION="auto")
    def test_auto_non_pdf_non_image_returns_false(self) -> None:
        """auto mode: other MIME types (e.g. email) don't produce archive by default."""
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        result = should_produce_archive(
            parser,
            "message/rfc822",
            Path("/tmp/email.eml"),
        )
        assert result is False

    @override_settings(ARCHIVE_FILE_GENERATION="always")
    def test_requires_rendition_with_can_produce_false_returns_true(self) -> None:
        """requires_pdf_rendition=True always wins, even if can_produce_archive=False."""
        parser = _parser_instance(can_produce=False, requires_rendition=True)
        result = should_produce_archive(
            parser,
            "application/pdf",
            Path("/tmp/doc.pdf"),
        )
        assert result is True
