"""
Focused tests for RasterisedDocumentParser.parse() mode behaviour.

These tests mock ``ocrmypdf.ocr`` so they run without a real Tesseract/OCRmyPDF
installation and execute quickly.  The intent is to verify the *control flow*
introduced by the ``produce_archive`` flag and the ``OCR_MODE=auto/off`` logic,
not to test OCRmyPDF itself.

Fixtures are pulled from conftest.py in this package.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from paperless.parsers.tesseract import RasterisedDocumentParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_TEXT = "This is a test document with enough text. " * 5  # >50 chars
_SHORT_TEXT = "Hi."  # <50 chars


def _make_extract_text(text: str | None):
    """Return a side_effect function for ``extract_text`` that returns *text*."""

    def _extract(sidecar_file, pdf_file):
        return text

    return _extract


# ---------------------------------------------------------------------------
# AUTO mode — PDF with sufficient text layer
# ---------------------------------------------------------------------------


class TestAutoModeWithText:
    """AUTO mode, original PDF has detectable text (>50 chars)."""

    def test_auto_text_no_archive_skips_ocrmypdf(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - AUTO mode, produce_archive=False
            - PDF with text > VALID_TEXT_LENGTH
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr is NOT called (early return path)
            - archive_path remains None
            - text is set from the original
        """
        # Patch extract_text to return long text (simulating detectable text layer)
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text() == _LONG_TEXT

    def test_auto_text_with_archive_calls_ocrmypdf_skip_text(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - AUTO mode, produce_archive=True
            - PDF with text > VALID_TEXT_LENGTH
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr IS called with skip_text=True
            - archive_path is set
        """
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=True,
        )

        mock_ocr.assert_called_once()
        call_kwargs = mock_ocr.call_args.kwargs
        assert call_kwargs.get("skip_text") is True
        assert "force_ocr" not in call_kwargs
        assert "redo_ocr" not in call_kwargs
        assert tesseract_parser.archive_path is not None


# ---------------------------------------------------------------------------
# AUTO mode — PDF without text layer (or too short)
# ---------------------------------------------------------------------------


class TestAutoModeNoText:
    """AUTO mode, original PDF has no detectable text (<= 50 chars)."""

    def test_auto_no_text_with_archive_calls_ocrmypdf_no_extra_flag(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        multi_page_images_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - AUTO mode, produce_archive=True
            - PDF with no text (or text <= VALID_TEXT_LENGTH)
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr IS called WITHOUT skip_text/force_ocr/redo_ocr
            - archive_path is set (since produce_archive=True)
        """
        # Return "no text" for the original; return real text for archive
        extract_call_count = 0

        def _extract_side(sidecar_file, pdf_file):
            nonlocal extract_call_count
            extract_call_count += 1
            if extract_call_count == 1:
                return None  # original has no text
            return _LONG_TEXT  # text from archive after OCR

        mocker.patch.object(tesseract_parser, "extract_text", side_effect=_extract_side)
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            multi_page_images_pdf_file,
            "application/pdf",
            produce_archive=True,
        )

        mock_ocr.assert_called_once()
        call_kwargs = mock_ocr.call_args.kwargs
        assert "skip_text" not in call_kwargs
        assert "force_ocr" not in call_kwargs
        assert "redo_ocr" not in call_kwargs
        assert tesseract_parser.archive_path is not None

    def test_auto_no_text_no_archive_calls_ocrmypdf(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        multi_page_images_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - AUTO mode, produce_archive=False
            - PDF with no text
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr IS called (no early return since no text detected)
            - archive_path is NOT set (produce_archive=False)
        """
        extract_call_count = 0

        def _extract_side(sidecar_file, pdf_file):
            nonlocal extract_call_count
            extract_call_count += 1
            if extract_call_count == 1:
                return None
            return _LONG_TEXT

        mocker.patch.object(tesseract_parser, "extract_text", side_effect=_extract_side)
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            multi_page_images_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        mock_ocr.assert_called_once()
        assert tesseract_parser.archive_path is None


# ---------------------------------------------------------------------------
# OFF mode — PDF
# ---------------------------------------------------------------------------


class TestOffModePdf:
    """OCR_MODE=off, document is a PDF."""

    def test_off_no_archive_returns_pdftotext(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - OFF mode, produce_archive=False
            - PDF with text
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr is NOT called
            - archive_path is None
            - text comes from pdftotext (extract_text)
        """
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "off"
        tesseract_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text() == _LONG_TEXT

    def test_off_with_archive_uses_ghostscript_not_ocr(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - OFF mode, produce_archive=True
            - PDF document
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr is NOT called
            - Ghostscript generate_pdfa IS called (PDF/A conversion without OCR)
            - archive_path is set
            - text comes from pdftotext, not OCR
        """
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")
        mock_gs = mocker.patch(
            "ocrmypdf._exec.ghostscript.generate_pdfa",
        )
        mocker.patch("ocrmypdf.pdfa.generate_pdfa_ps")

        tesseract_parser.settings.mode = "off"
        tesseract_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=True,
        )

        mock_ocr.assert_not_called()
        mock_gs.assert_called_once()
        assert tesseract_parser.archive_path is not None
        assert tesseract_parser.get_text() == _LONG_TEXT


# ---------------------------------------------------------------------------
# OFF mode — image
# ---------------------------------------------------------------------------


class TestOffModeImage:
    """OCR_MODE=off, document is an image (PNG)."""

    def test_off_image_no_archive_no_ocrmypdf(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN:
            - OFF mode, produce_archive=False
            - Image document (PNG)
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf.ocr is NOT called
            - archive_path is None
            - text is empty string (images have no text layer)
        """
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "off"
        tesseract_parser.parse(simple_png_file, "image/png", produce_archive=False)

        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text() == ""

    def test_off_image_with_archive_uses_img2pdf_path(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_png_file: Path,
    ) -> None:
        """
        GIVEN:
            - OFF mode, produce_archive=True
            - Image document (PNG)
        WHEN:
            - parse() is called
        THEN:
            - _convert_image_to_pdfa() is called instead of ocrmypdf.ocr
            - archive_path is set to the returned path
            - text is empty string
        """
        fake_archive = Path("/tmp/fake-archive.pdf")
        mock_convert = mocker.patch.object(
            tesseract_parser,
            "_convert_image_to_pdfa",
            return_value=fake_archive,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "off"
        tesseract_parser.parse(simple_png_file, "image/png", produce_archive=True)

        mock_convert.assert_called_once_with(simple_png_file)
        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path == fake_archive
        assert tesseract_parser.get_text() == ""


# ---------------------------------------------------------------------------
# produce_archive=False never sets archive_path for FORCE / REDO / AUTO modes
# ---------------------------------------------------------------------------


class TestProduceArchiveFalse:
    """Verify produce_archive=False never results in an archive regardless of mode."""

    @pytest.mark.parametrize("mode", ["force", "redo"])
    def test_produce_archive_false_force_redo_modes(
        self,
        mode: str,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        multi_page_images_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - FORCE or REDO mode, produce_archive=False
            - Any PDF
        WHEN:
            - parse() is called (ocrmypdf mocked to succeed)
        THEN:
            - archive_path is NOT set even though ocrmypdf ran
        """
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = mode
        tesseract_parser.parse(
            multi_page_images_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        assert tesseract_parser.archive_path is None
        assert tesseract_parser.get_text() is not None

    def test_produce_archive_false_auto_with_text(
        self,
        mocker: MockerFixture,
        tesseract_parser: RasterisedDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - AUTO mode, produce_archive=False
            - PDF with text > VALID_TEXT_LENGTH
        WHEN:
            - parse() is called
        THEN:
            - ocrmypdf is skipped entirely (early return)
            - archive_path is None
        """
        mocker.patch.object(
            tesseract_parser,
            "extract_text",
            return_value=_LONG_TEXT,
        )
        mock_ocr = mocker.patch("ocrmypdf.ocr")

        tesseract_parser.settings.mode = "auto"
        tesseract_parser.parse(
            simple_digital_pdf_file,
            "application/pdf",
            produce_archive=False,
        )

        mock_ocr.assert_not_called()
        assert tesseract_parser.archive_path is None
