"""
Tests for RasterisedDocumentParser._convert_image_to_pdfa.

The method converts an image to a PDF/A-2b file using img2pdf (wrapping)
then pikepdf (PDF/A metadata stamping), with a fallback to plain PDF when
pikepdf stamping fails.  No Tesseract or Ghostscript is invoked.

These are unit/integration tests: img2pdf and pikepdf run for real; only
error-path branches mock the respective library call.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import img2pdf
import magic
import pikepdf
import pytest

from documents.parsers import ParseError

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from paperless.parsers.tesseract import RasterisedDocumentParser


class TestConvertImageToPdfa:
    """_convert_image_to_pdfa: output shape, error paths, DPI handling."""

    def test_valid_png_produces_pdf_bytes(
        self,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN: a valid PNG with DPI metadata
        WHEN: _convert_image_to_pdfa is called
        THEN: the returned file is non-empty and begins with the PDF magic bytes
        """
        result = tesseract_parser._convert_image_to_pdfa(simple_png_file)

        assert result.exists()
        assert magic.from_file(str(result), mime=True) == "application/pdf"

    def test_output_path_is_archive_pdf_in_tempdir(
        self,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN: any valid image
        WHEN: _convert_image_to_pdfa is called
        THEN: the returned path is exactly <tempdir>/archive.pdf
        """
        result = tesseract_parser._convert_image_to_pdfa(simple_png_file)

        assert result == Path(tesseract_parser.tempdir) / "archive.pdf"

    def test_img2pdf_failure_raises_parse_error(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN: img2pdf.convert raises an exception
        WHEN: _convert_image_to_pdfa is called
        THEN: a ParseError is raised that mentions "img2pdf conversion failed"
        """
        mocker.patch.object(img2pdf, "convert", side_effect=Exception("boom"))

        with pytest.raises(ParseError, match="img2pdf conversion failed"):
            tesseract_parser._convert_image_to_pdfa(simple_png_file)

    def test_pikepdf_stamping_failure_falls_back_to_plain_pdf(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN: pikepdf.open raises during PDF/A metadata stamping
        WHEN: _convert_image_to_pdfa is called
        THEN: no exception is raised and the returned file is still a valid PDF
              (plain PDF bytes are used as fallback)
        """
        mocker.patch.object(pikepdf, "open", side_effect=Exception("pikepdf boom"))

        result = tesseract_parser._convert_image_to_pdfa(simple_png_file)

        assert result.exists()
        assert magic.from_file(str(result), mime=True) == "application/pdf"

    def test_image_dpi_setting_applies_fixed_dpi_layout(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_no_dpi_png_file: Path,
    ) -> None:
        """
        GIVEN: parser.settings.image_dpi = 150
        WHEN: _convert_image_to_pdfa is called with a no-DPI PNG
        THEN: img2pdf.get_fixed_dpi_layout_fun is called with (150, 150)
              and the output is still a valid PDF
        """
        spy = mocker.patch.object(
            img2pdf,
            "get_fixed_dpi_layout_fun",
            wraps=img2pdf.get_fixed_dpi_layout_fun,
        )
        tesseract_parser.settings.image_dpi = 150

        result = tesseract_parser._convert_image_to_pdfa(simple_no_dpi_png_file)

        spy.assert_called_once_with((150, 150))
        assert magic.from_file(str(result), mime=True) == "application/pdf"

    def test_no_image_dpi_setting_skips_fixed_dpi_layout(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN: parser.settings.image_dpi is None (default)
        WHEN: _convert_image_to_pdfa is called
        THEN: img2pdf.get_fixed_dpi_layout_fun is never called
        """
        spy = mocker.patch.object(
            img2pdf,
            "get_fixed_dpi_layout_fun",
            wraps=img2pdf.get_fixed_dpi_layout_fun,
        )
        tesseract_parser.settings.image_dpi = None

        tesseract_parser._convert_image_to_pdfa(simple_png_file)

        spy.assert_not_called()
