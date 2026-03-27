"""Tests for should_produce_archive()."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from documents.consumer import should_produce_archive

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
    @pytest.mark.parametrize(
        ("generation", "can_produce", "requires_rendition", "mime", "expected"),
        [
            pytest.param(
                "never",
                True,
                False,
                "application/pdf",
                False,
                id="never-returns-false",
            ),
            pytest.param(
                "always",
                True,
                False,
                "application/pdf",
                True,
                id="always-returns-true",
            ),
            pytest.param(
                "never",
                True,
                True,
                "application/pdf",
                True,
                id="requires-rendition-overrides-never",
            ),
            pytest.param(
                "always",
                False,
                False,
                "text/plain",
                False,
                id="cannot-produce-overrides-always",
            ),
            pytest.param(
                "always",
                False,
                True,
                "application/pdf",
                True,
                id="requires-rendition-wins-even-if-cannot-produce",
            ),
            pytest.param(
                "auto",
                True,
                False,
                "image/tiff",
                True,
                id="auto-image-returns-true",
            ),
            pytest.param(
                "auto",
                True,
                False,
                "message/rfc822",
                False,
                id="auto-non-pdf-non-image-returns-false",
            ),
        ],
    )
    def test_generation_setting(
        self,
        settings,
        generation: str,
        can_produce: bool,  # noqa: FBT001
        requires_rendition: bool,  # noqa: FBT001
        mime: str,
        expected: bool,  # noqa: FBT001
    ) -> None:
        settings.ARCHIVE_FILE_GENERATION = generation
        parser = _parser_instance(
            can_produce=can_produce,
            requires_rendition=requires_rendition,
        )
        assert should_produce_archive(parser, mime, Path("/tmp/doc")) is expected

    @pytest.mark.parametrize(
        ("extracted_text", "expected"),
        [
            pytest.param(
                "This is a born-digital PDF with lots of text content. " * 10,
                False,
                id="born-digital-long-text-skips-archive",
            ),
            pytest.param(None, True, id="no-text-scanned-produces-archive"),
            pytest.param("tiny", True, id="short-text-treated-as-scanned"),
        ],
    )
    def test_auto_pdf_archive_decision(
        self,
        mocker: MockerFixture,
        settings,
        extracted_text: str | None,
        expected: bool,  # noqa: FBT001
    ) -> None:
        settings.ARCHIVE_FILE_GENERATION = "auto"
        mocker.patch("documents.consumer.is_tagged_pdf", return_value=False)
        mocker.patch("documents.consumer.extract_pdf_text", return_value=extracted_text)
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        assert (
            should_produce_archive(parser, "application/pdf", Path("/tmp/doc.pdf"))
            is expected
        )

    def test_tagged_pdf_skips_archive_in_auto_mode(
        self,
        mocker: MockerFixture,
        settings,
    ) -> None:
        """Tagged PDFs (e.g. Word exports) are treated as born-digital regardless of text length."""
        settings.ARCHIVE_FILE_GENERATION = "auto"
        mocker.patch("documents.consumer.is_tagged_pdf", return_value=True)
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        assert (
            should_produce_archive(parser, "application/pdf", Path("/tmp/doc.pdf"))
            is False
        )

    def test_tagged_pdf_does_not_call_pdftotext(
        self,
        mocker: MockerFixture,
        settings,
    ) -> None:
        """When a PDF is tagged, pdftotext is not invoked (fast path)."""
        settings.ARCHIVE_FILE_GENERATION = "auto"
        mocker.patch("documents.consumer.is_tagged_pdf", return_value=True)
        mock_extract = mocker.patch("documents.consumer.extract_pdf_text")
        parser = _parser_instance(can_produce=True, requires_rendition=False)
        should_produce_archive(parser, "application/pdf", Path("/tmp/doc.pdf"))
        mock_extract.assert_not_called()
