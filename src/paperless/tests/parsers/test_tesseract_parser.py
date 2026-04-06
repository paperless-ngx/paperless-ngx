"""
Tests for paperless.parsers.tesseract.RasterisedDocumentParser.

All tests use fixtures defined in conftest.py for parser lifecycle and
sample-file access.  Settings-dependent tests mutate parser.settings
directly rather than going through the database.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from typing import TYPE_CHECKING

import pytest
from ocrmypdf import SubprocessOutputError

from documents.parsers import ParseError
from documents.parsers import run_convert
from paperless.parsers import ParserProtocol
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.tesseract import post_process_text

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

    from paperless.tests.parsers.conftest import MakeTesseractParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_ordered_substrings(content: str, strings: list[str]) -> None:
    """Assert all *strings* appear in *content* in the given order."""
    indices: list[int] = []
    for s in strings:
        assert s in content, f"{s!r} not found in content"
        indices.append(content.index(s))
    assert indices == sorted(indices), f"Strings out of order in content: {strings}"


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestRasterisedDocumentParserProtocol:
    """Verify class-level protocol attributes and classmethods — no DB, no parser."""

    def test_class_attributes_present(self) -> None:
        assert RasterisedDocumentParser.name
        assert RasterisedDocumentParser.version
        assert RasterisedDocumentParser.author
        assert RasterisedDocumentParser.url

    def test_supported_mime_types_returns_dict(self) -> None:
        mime_types = RasterisedDocumentParser.supported_mime_types()
        assert isinstance(mime_types, dict)
        for mime in (
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/tiff",
            "image/gif",
            "image/bmp",
            "image/webp",
            "image/heic",
        ):
            assert mime in mime_types

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            pytest.param("application/pdf", 10, id="pdf"),
            pytest.param("image/jpeg", 10, id="jpeg"),
            pytest.param("image/png", 10, id="png"),
            pytest.param("image/tiff", 10, id="tiff"),
            pytest.param("image/gif", 10, id="gif"),
            pytest.param("image/bmp", 10, id="bmp"),
            pytest.param("image/webp", 10, id="webp"),
            pytest.param("image/heic", 10, id="heic"),
            pytest.param("text/plain", None, id="text-unsupported"),
            pytest.param("application/msword", None, id="word-unsupported"),
        ],
    )
    def test_score(self, mime_type: str, expected: int | None) -> None:
        assert RasterisedDocumentParser.score(mime_type, "file.pdf") == expected

    def test_isinstance_satisfies_protocol(
        self,
        tesseract_parser: RasterisedDocumentParser,
    ) -> None:
        assert isinstance(tesseract_parser, ParserProtocol)

    def test_can_produce_archive_is_true(
        self,
        tesseract_parser: RasterisedDocumentParser,
    ) -> None:
        assert tesseract_parser.can_produce_archive is True

    def test_requires_pdf_rendition_is_false(
        self,
        tesseract_parser: RasterisedDocumentParser,
    ) -> None:
        assert tesseract_parser.requires_pdf_rendition is False


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestRasterisedDocumentParserLifecycle:
    """Context-manager cleanup — no DB."""

    def test_tempdir_cleaned_up_on_exit(
        self,
        mocker: MockerFixture,
        null_app_config: MagicMock,
    ) -> None:
        mocker.patch(
            "paperless.config.BaseConfig._get_config_instance",
            return_value=null_app_config,
        )
        with RasterisedDocumentParser() as parser:
            tempdir = parser.tempdir
            assert tempdir.exists()
        assert not tempdir.exists()

    def test_tempdir_cleaned_up_after_exception(
        self,
        mocker: MockerFixture,
        null_app_config: MagicMock,
    ) -> None:
        mocker.patch(
            "paperless.config.BaseConfig._get_config_instance",
            return_value=null_app_config,
        )
        tempdir: Path | None = None
        with pytest.raises(RuntimeError):
            with RasterisedDocumentParser() as parser:
                tempdir = parser.tempdir
                raise RuntimeError("boom")
        assert tempdir is not None and not tempdir.exists()


# ---------------------------------------------------------------------------
# post_process_text
# ---------------------------------------------------------------------------


class TestPostProcessText:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            pytest.param(
                "simple     string",
                "simple string",
                id="collapse-spaces",
            ),
            pytest.param(
                "simple    newline\n   testing string",
                "simple newline\ntesting string",
                id="preserve-newline",
            ),
            pytest.param(
                "utf-8   строка с пробелами в конце  ",  # noqa: RUF001
                "utf-8 строка с пробелами в конце",  # noqa: RUF001
                id="utf8-trailing-spaces",
            ),
        ],
    )
    def test_post_process_text(self, source: str, expected: str) -> None:
        assert post_process_text(source) == expected


# ---------------------------------------------------------------------------
# Page count
# ---------------------------------------------------------------------------


class TestGetPageCount:
    def test_single_page_pdf(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        assert (
            tesseract_parser.get_page_count(
                tesseract_samples_dir / "simple-digital.pdf",
                "application/pdf",
            )
            == 1
        )

    def test_multi_page_pdf(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        assert (
            tesseract_parser.get_page_count(
                tesseract_samples_dir / "multi-page-mixed.pdf",
                "application/pdf",
            )
            == 6
        )

    def test_password_protected_returns_none(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
        caplog,
    ) -> None:
        """
        GIVEN:
            - pikepdf raises when opening a protected PDF
        WHEN:
            - Page count is requested
        THEN:
            - Returns None and logs a warning
        """
        mocker.patch("pikepdf.Pdf.open", side_effect=Exception("password required"))
        import logging

        with caplog.at_level(logging.WARNING):
            page_count = tesseract_parser.get_page_count(
                tesseract_samples_dir / "simple-digital.pdf",
                "application/pdf",
            )
        assert page_count is None
        assert any(
            "Unable to determine PDF page count" in r.message for r in caplog.records
        )

    def test_non_pdf_returns_none(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        assert (
            tesseract_parser.get_page_count(
                tesseract_samples_dir / "simple.png",
                "image/png",
            )
            is None
        )


# ---------------------------------------------------------------------------
# DPI helpers
# ---------------------------------------------------------------------------


class TestDpiHelpers:
    @pytest.mark.parametrize(
        ("filename", "expected_dpi"),
        [
            pytest.param("simple-no-dpi.png", None, id="no-dpi"),
            pytest.param("simple.png", 72, id="with-dpi"),
        ],
    )
    def test_get_dpi(
        self,
        filename: str,
        expected_dpi: int | None,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        assert (
            tesseract_parser.get_dpi(str(tesseract_samples_dir / filename))
            == expected_dpi
        )

    def test_calculate_a4_dpi(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        assert (
            tesseract_parser.calculate_a4_dpi(
                str(tesseract_samples_dir / "simple-no-dpi.png"),
            )
            == 62
        )


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------


class TestGetThumbnail:
    def test_thumbnail_is_file(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        thumb = tesseract_parser.get_thumbnail(
            tesseract_samples_dir / "simple-digital.pdf",
            "application/pdf",
        )
        assert thumb.is_file()

    def test_thumbnail_fallback_on_convert_error(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        def _raise_on_pdf(input_file, output_file, **kwargs) -> None:
            if ".pdf" in str(input_file):
                raise ParseError("Does not compute.")
            run_convert(input_file=input_file, output_file=output_file, **kwargs)

        mocker.patch("documents.parsers.run_convert", side_effect=_raise_on_pdf)

        thumb = tesseract_parser.get_thumbnail(
            tesseract_samples_dir / "simple-digital.pdf",
            "application/pdf",
        )
        assert thumb.is_file()

    def test_thumbnail_encrypted_pdf(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        thumb = tesseract_parser.get_thumbnail(
            tesseract_samples_dir / "encrypted.pdf",
            "application/pdf",
        )
        assert thumb.is_file()


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_extract_text_from_digital_pdf(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        text = tesseract_parser.extract_text(
            None,
            tesseract_samples_dir / "simple-digital.pdf",
        )
        assert text is not None
        assert "This is a test document." in text.strip()


# ---------------------------------------------------------------------------
# Parse — PDF modes
# ---------------------------------------------------------------------------


class TestParsePdf:
    def test_simple_digital_creates_archive(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - Multi-page digital PDF with sufficient text layer
            - Default settings (mode=auto, produce_archive=True)
        WHEN:
            - Document is parsed
        THEN:
            - Archive is created (AUTO mode + text present + produce_archive=True
              → PDF/A conversion via skip_text)
            - Text is extracted
        """
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-digital.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_with_form_default(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.parse(
            tesseract_samples_dir / "with-form.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    def test_with_form_redo_no_archive_when_not_requested(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "redo"
        tesseract_parser.parse(
            tesseract_samples_dir / "with-form.pdf",
            "application/pdf",
            produce_archive=False,
        )
        assert tesseract_parser.archive_path is None
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    def test_with_form_force(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "force"
        tesseract_parser.parse(
            tesseract_samples_dir / "with-form.pdf",
            "application/pdf",
        )
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            ["Please enter your name in here:", "This is a PDF document with a form."],
        )

    def test_signed_skip_mode_no_archive(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(tesseract_samples_dir / "signed.pdf", "application/pdf")
        assert tesseract_parser.archive_path is None
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            [
                "This is a digitally signed PDF, created with Acrobat Pro for the Paperless project to enable",
                "automated testing of signed/encrypted PDFs",
            ],
        )

    def test_encrypted_skip_mode_empty_text(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "encrypted.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text() == ""

    def test_gs_rendering_error_raises_parse_error(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        mocker.patch(
            "ocrmypdf.ocr",
            side_effect=SubprocessOutputError("Ghostscript PDF/A rendering failed"),
        )
        with pytest.raises(ParseError):
            tesseract_parser.parse(
                tesseract_samples_dir / "simple-digital.pdf",
                "application/pdf",
            )


# ---------------------------------------------------------------------------
# Parse — images
# ---------------------------------------------------------------------------


class TestParseImages:
    def test_simple_png(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.parse(tesseract_samples_dir / "simple.png", "image/png")
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            ["This is a test document."],
        )

    def test_simple_alpha_png(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
        tmp_path: Path,
    ) -> None:
        dest = tmp_path / "simple-alpha.png"
        shutil.copy(tesseract_samples_dir / "simple-alpha.png", dest)
        tesseract_parser.parse(dest, "image/png")
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            ["This is a test document."],
        )

    def test_no_dpi_with_default_dpi(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.image_dpi = 72
        tesseract_parser.parse(tesseract_samples_dir / "simple-no-dpi.png", "image/png")
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert "this is a test document." in tesseract_parser.get_text().lower()

    def test_no_dpi_no_fallback_raises(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        mocker.patch.object(tesseract_parser, "calculate_a4_dpi", return_value=None)
        with pytest.raises(ParseError):
            tesseract_parser.parse(
                tesseract_samples_dir / "simple-no-dpi.png",
                "image/png",
            )


# ---------------------------------------------------------------------------
# Parse — multi-page PDF
# ---------------------------------------------------------------------------


class TestParseMultiPage:
    def test_multi_page_digital(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-digital.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @pytest.mark.parametrize(
        "mode",
        [
            pytest.param("auto", id="auto"),
            pytest.param("redo", id="redo"),
            pytest.param("force", id="force"),
        ],
    )
    def test_multi_page_digital_pages_2(
        self,
        mode: str,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.pages = 2
        tesseract_parser.settings.mode = mode
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-digital.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_multi_page_images_skip(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-images.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_multi_page_images_redo_pages_2(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with image-only pages
            - OCR of only pages 1 and 2 requested
            - Mode: redo
        WHEN:
            - Document is parsed
        THEN:
            - Pages 1 and 2 extracted; page 3 absent
        """
        tesseract_parser.settings.pages = 2
        tesseract_parser.settings.mode = "redo"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-images.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        text = tesseract_parser.get_text().lower()
        assert_ordered_substrings(text, ["page 1", "page 2"])
        assert "page 3" not in text

    def test_multi_page_images_force_page_1(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with image-only pages
            - Only page 1 requested
            - Mode: force
        WHEN:
            - Document is parsed
        THEN:
            - Only page 1 extracted
        """
        tesseract_parser.settings.pages = 1
        tesseract_parser.settings.mode = "force"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-images.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        text = tesseract_parser.get_text().lower()
        assert "page 1" in text
        assert "page 2" not in text
        assert "page 3" not in text

    def test_multi_page_tiff(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - Multi-page TIFF image
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-images.tiff",
            "image/tiff",
        )
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_multi_page_tiff_alpha(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - Multi-page TIFF with alpha channel
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        dest = tmp_path / "alpha.tiff"
        shutil.copy(tesseract_samples_dir / "multi-page-images-alpha.tiff", dest)
        tesseract_parser.parse(dest, "image/tiff")
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_multi_page_tiff_alpha_srgb(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - Multi-page TIFF with alpha channel and sRGB colorspace
        WHEN:
            - Image is parsed
        THEN:
            - Text from all pages extracted
        """
        dest = tmp_path / "alpha-rgb.tiff"
        shutil.copy(tesseract_samples_dir / "multi-page-images-alpha-rgb.tiff", dest)
        tesseract_parser.parse(dest, "image/tiff")
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )


# ---------------------------------------------------------------------------
# Parse — skip_noarchive / skip_archive_file
# ---------------------------------------------------------------------------


class TestSkipArchive:
    def test_skip_noarchive_with_text_layer(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with existing text layer
            - Mode: auto, produce_archive=False
        WHEN:
            - Document is parsed
        THEN:
            - Text extracted from original; no archive created (text exists +
              produce_archive=False skips OCRmyPDF entirely)
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-digital.pdf",
            "application/pdf",
            produce_archive=False,
        )
        assert tesseract_parser.archive_path is None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    def test_skip_noarchive_image_only_creates_archive(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with image-only pages (no text layer)
            - Mode: auto, skip_archive_file: auto
        WHEN:
            - Document is parsed
        THEN:
            - Text extracted; archive created (OCR needed, no existing text)
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-images.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3"],
        )

    @pytest.mark.parametrize(
        ("produce_archive", "filename", "expect_archive"),
        [
            pytest.param(
                True,
                "multi-page-digital.pdf",
                True,
                id="produce-archive-with-text",
            ),
            pytest.param(
                True,
                "multi-page-images.pdf",
                True,
                id="produce-archive-no-text",
            ),
            pytest.param(
                False,
                "multi-page-digital.pdf",
                False,
                id="no-archive-with-text-layer",
            ),
            pytest.param(
                False,
                "multi-page-images.pdf",
                False,
                id="no-archive-no-text-layer",
            ),
        ],
    )
    def test_produce_archive_flag(
        self,
        produce_archive: bool,  # noqa: FBT001
        filename: str,
        expect_archive: bool,  # noqa: FBT001
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - Various PDFs (with and without text layers)
            - produce_archive flag set to True or False
        WHEN:
            - Document is parsed
        THEN:
            - archive_path is set if and only if produce_archive=True
            - Text is always extracted
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / filename,
            "application/pdf",
            produce_archive=produce_archive,
        )
        text = tesseract_parser.get_text().lower()
        assert_ordered_substrings(text, ["page 1", "page 2", "page 3"])
        if expect_archive:
            assert tesseract_parser.archive_path is not None
        else:
            assert tesseract_parser.archive_path is None

    def test_tagged_pdf_skips_ocr_in_auto_mode(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - A tagged PDF (e.g. exported from Word, /MarkInfo /Marked true)
            - Mode: auto, produce_archive=False
        WHEN:
            - Document is parsed
        THEN:
            - OCRmyPDF is not invoked (tagged ⇒ original_has_text=True)
            - Text is extracted from the original via pdftotext
            - No archive is produced
        """
        tesseract_parser.settings.mode = "auto"
        mock_ocr = mocker.patch("ocrmypdf.ocr")
        tesseract_parser.parse(
            tesseract_samples_dir / "simple-digital.pdf",
            "application/pdf",
            produce_archive=False,
        )
        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text()

    def test_tagged_pdf_produces_pdfa_archive_without_ocr(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - A tagged PDF (e.g. exported from Word, /MarkInfo /Marked true)
            - Mode: auto, produce_archive=True
        WHEN:
            - Document is parsed
        THEN:
            - OCRmyPDF runs with skip_text (PDF/A conversion only, no OCR)
            - Archive is produced
            - Text is preserved from the original
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "simple-digital.pdf",
            "application/pdf",
            produce_archive=True,
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.get_text()


# ---------------------------------------------------------------------------
# Parse — mixed pages / sidecar
# ---------------------------------------------------------------------------


class TestParseMixed:
    def test_multi_page_mixed_skip_mode(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with text in some pages (image) and some pages (digital)
            - Mode: auto (skip_text), skip_archive_file: always
        WHEN:
            - Document is parsed
        THEN:
            - All pages extracted; archive created; sidecar notes skipped pages
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-mixed.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 1", "page 2", "page 3", "page 4", "page 5", "page 6"],
        )
        sidecar = (tesseract_parser.tempdir / "sidecar.txt").read_text()
        assert "[OCR skipped on page(s) 4-6]" in sidecar

    def test_single_page_mixed_redo_mode(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - Single page with both text and image content
            - Mode: redo
        WHEN:
            - Document is parsed
        THEN:
            - Both text layer and image text extracted; archive created
        """
        tesseract_parser.settings.mode = "redo"
        tesseract_parser.parse(
            tesseract_samples_dir / "single-page-mixed.pdf",
            "application/pdf",
        )
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            [
                "this is some normal text, present on page 1 of the document.",
                "this is some text, but in an image, also on page 1.",
                "this is further text on page 1.",
            ],
        )
        sidecar = (tesseract_parser.tempdir / "sidecar.txt").read_text().lower()
        assert "this is some text, but in an image, also on page 1." in sidecar
        assert (
            "this is some normal text, present on page 1 of the document."
            not in sidecar
        )

    def test_multi_page_mixed_skip_noarchive(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - File with mixed pages (some with text, some image-only)
            - Mode: auto, produce_archive=False
        WHEN:
            - Document is parsed
        THEN:
            - No archive created (produce_archive=False); text from text layer present
        """
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            tesseract_samples_dir / "multi-page-mixed.pdf",
            "application/pdf",
            produce_archive=False,
        )
        assert tesseract_parser.archive_path is None
        assert_ordered_substrings(
            tesseract_parser.get_text().lower(),
            ["page 4", "page 5", "page 6"],
        )


# ---------------------------------------------------------------------------
# Parse — rotation
# ---------------------------------------------------------------------------


class TestParseRotate:
    def test_rotate_auto_mode(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.mode = "auto"
        tesseract_parser.settings.rotate = True
        tesseract_parser.parse(tesseract_samples_dir / "rotated.pdf", "application/pdf")
        assert_ordered_substrings(
            tesseract_parser.get_text(),
            [
                "This is the text that appears on the first page. It\u2019s a lot of text.",
                "Even if the pages are rotated, OCRmyPDF still gets the job done.",
                "This is a really weird file with lots of nonsense text.",
                "If you read this, it\u2019s your own fault. Also check your screen orientation.",
            ],
        )


# ---------------------------------------------------------------------------
# Parse — RTL
# ---------------------------------------------------------------------------


class TestParseRtl:
    def test_rtl_language_detected(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        """
        GIVEN:
            - PDF with RTL Arabic text in its text layer (short: 18 chars)
            - mode=off, produce_archive=True: PDF/A conversion via skip_text, no OCR engine
        WHEN:
            - Document is parsed
        THEN:
            - Arabic content is extracted from the PDF text layer (normalised for bidi)

        Note: The RTL PDF has a short text layer (< VALID_TEXT_LENGTH=50) so AUTO mode
        would attempt full OCR, which fails due to PriorOcrFoundError and falls back to
        force-ocr with English Tesseract (producing garbage).  Using mode="off" forces
        skip_text=True so the Arabic text layer is preserved through PDF/A conversion.
        """
        tesseract_parser.settings.mode = "off"
        tesseract_parser.parse(
            tesseract_samples_dir / "rtl-test.pdf",
            "application/pdf",
        )
        normalised = "".join(
            ch
            for ch in unicodedata.normalize("NFKC", tesseract_parser.get_text())
            if unicodedata.category(ch) != "Cf" and not ch.isspace()
        )
        assert "ةرازو" in normalised
        # pdftotext uses Arabic Yeh (U+064A) where ocrmypdf used Farsi Yeh (U+06CC)
        assert any(token in normalised for token in ("ةیلخادلا", "الاخليد", "ةيلخادال"))


# ---------------------------------------------------------------------------
# Parse — OCRmyPDF parameters
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOcrmypdfParameters:
    """Tests that inspect the dict passed to ocrmypdf.

    These create parsers inline via make_tesseract_parser with specific
    Django settings overrides so OcrConfig picks them up at construction time.
    """

    def test_basic_parameter_mapping(
        self,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser() as parser:
            params = parser.construct_ocrmypdf_parameters(
                input_file="input.pdf",
                output_file="output.pdf",
                sidecar_file="sidecar.txt",
                mime_type="application/pdf",
                safe_fallback=False,
            )
        assert params["input_file_or_options"] == "input.pdf"
        assert params["output_file"] == "output.pdf"
        assert params["sidecar"] == "sidecar.txt"

    @pytest.mark.parametrize(
        ("ocr_clean", "expected_clean", "expected_clean_final"),
        [
            pytest.param("none", False, False, id="clean-none"),
            pytest.param("clean", True, False, id="clean-clean"),
        ],
    )
    def test_clean_option(
        self,
        ocr_clean: str,
        *,
        expected_clean: bool,
        expected_clean_final: bool,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_CLEAN=ocr_clean) as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert ("clean" in params) == expected_clean
        assert ("clean_final" in params) == expected_clean_final

    def test_clean_final_auto_mode(
        self,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_CLEAN="clean-final", OCR_MODE="auto") as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert params["clean_final"] is True
        assert "clean" not in params

    def test_clean_final_redo_mode_falls_back_to_clean(
        self,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_CLEAN="clean-final", OCR_MODE="redo") as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert params["clean"] is True
        assert "clean_final" not in params

    @pytest.mark.parametrize(
        ("ocr_mode", "ocr_deskew", "expect_deskew"),
        [
            pytest.param("auto", True, True, id="auto-deskew-on"),
            pytest.param("redo", True, False, id="redo-deskew-off"),
            pytest.param("auto", False, False, id="auto-no-deskew"),
        ],
    )
    def test_deskew_option(
        self,
        ocr_mode: str,
        *,
        ocr_deskew: bool,
        expect_deskew: bool,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_MODE=ocr_mode, OCR_DESKEW=ocr_deskew) as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert ("deskew" in params) == expect_deskew

    def test_max_image_pixels_positive(
        self,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_MAX_IMAGE_PIXELS=1_000_001.0) as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert "max_image_mpixels" in params
        assert abs(params["max_image_mpixels"] - 1.0) < 1e-4

    def test_max_image_pixels_negative_omitted(
        self,
        make_tesseract_parser: MakeTesseractParser,
    ) -> None:
        with make_tesseract_parser(OCR_MAX_IMAGE_PIXELS=-1_000_001.0) as parser:
            params = parser.construct_ocrmypdf_parameters("", "", "", "")
        assert "max_image_mpixels" not in params


# ---------------------------------------------------------------------------
# Parse — file type matrix
# ---------------------------------------------------------------------------


class TestParserFileTypes:
    @pytest.mark.parametrize(
        ("filename", "mime_type"),
        [
            pytest.param("simple.bmp", "image/bmp", id="bmp"),
            pytest.param("simple.jpg", "image/jpeg", id="jpeg"),
            pytest.param("simple.tif", "image/tiff", id="tiff"),
        ],
    )
    def test_simple_image_contains_test_text(
        self,
        filename: str,
        mime_type: str,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.parse(tesseract_samples_dir / filename, mime_type)
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.archive_path.is_file()
        assert "this is a test document" in tesseract_parser.get_text().lower()

    def test_heic(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.parse(tesseract_samples_dir / "simple.heic", "image/heic")
        assert tesseract_parser.archive_path is not None
        assert "pizza" in tesseract_parser.get_text().lower()

    def test_gif_with_explicit_dpi(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.image_dpi = 200
        tesseract_parser.parse(tesseract_samples_dir / "simple.gif", "image/gif")
        assert tesseract_parser.archive_path is not None
        assert "this is a test document" in tesseract_parser.get_text().lower()

    def test_webp_with_explicit_dpi(
        self,
        tesseract_parser: RasterisedDocumentParser,
        tesseract_samples_dir: Path,
    ) -> None:
        tesseract_parser.settings.image_dpi = 72
        tesseract_parser.parse(tesseract_samples_dir / "document.webp", "image/webp")
        assert tesseract_parser.archive_path is not None
        assert re.search(
            r"this is a ?webp document, created 11/14/2022\.",
            tesseract_parser.get_text().lower(),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRasterisedDocumentParserRegistry:
    def test_registered_in_defaults(self) -> None:
        from paperless.parsers.registry import ParserRegistry

        registry = ParserRegistry()
        registry.register_defaults()
        assert RasterisedDocumentParser in registry._builtins

    @pytest.mark.parametrize(
        ("mime_type", "filename"),
        [
            pytest.param("application/pdf", "doc.pdf", id="pdf"),
            pytest.param("image/png", "image.png", id="png"),
            pytest.param("image/jpeg", "photo.jpg", id="jpeg"),
            pytest.param("image/tiff", "scan.tif", id="tiff"),
        ],
    )
    def test_get_parser_for_supported_mime(
        self,
        mime_type: str,
        filename: str,
    ) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        assert (
            registry.get_parser_for_file(mime_type, filename)
            is RasterisedDocumentParser
        )
