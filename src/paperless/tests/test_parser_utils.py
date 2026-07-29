"""Tests for paperless.parsers.utils helpers."""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from paperless.parsers.utils import is_tagged_pdf
from paperless.parsers.utils import pdf_born_digital_text
from paperless.parsers.utils import post_process_text
from paperless.parsers.utils import read_file_handle_unicode_errors

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

SAMPLES = Path(__file__).parent / "samples" / "tesseract"


class TestReadFileHandleUnicodeErrors:
    def test_plain_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "plain.txt"
        f.write_bytes(b"hello world")
        assert read_file_handle_unicode_errors(f) == "hello world"

    def test_utf8_bom(self, tmp_path: Path) -> None:
        f = tmp_path / "bom.txt"
        f.write_bytes(codecs.BOM_UTF8 + b"hello")
        assert read_file_handle_unicode_errors(f) == "hello"

    def test_utf16_le(self, tmp_path: Path) -> None:
        f = tmp_path / "utf16le.txt"
        f.write_bytes(codecs.BOM_UTF16_LE + "hello".encode("utf-16-le"))
        assert read_file_handle_unicode_errors(f) == "hello"

    def test_utf16_be(self, tmp_path: Path) -> None:
        f = tmp_path / "utf16be.txt"
        f.write_bytes(codecs.BOM_UTF16_BE + "hello".encode("utf-16-be"))
        assert read_file_handle_unicode_errors(f) == "hello"

    def test_nul_bytes_stripped(self, tmp_path: Path) -> None:
        f = tmp_path / "null-bytes.txt"
        f.write_bytes(b"foo\x00bar")
        assert read_file_handle_unicode_errors(f) == "foobar"

    def test_invalid_utf8_replaced(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.txt"
        f.write_bytes(b"ok\x80\x81bad")
        result = read_file_handle_unicode_errors(f)
        assert "ok" in result
        assert "bad" in result
        assert "\x00" not in result


class TestIsTaggedPdf:
    def test_tagged_pdf_returns_true(self) -> None:
        assert is_tagged_pdf(SAMPLES / "simple-digital.pdf") is True

    def test_untagged_pdf_returns_false(self) -> None:
        assert is_tagged_pdf(SAMPLES / "multi-page-images.pdf") is False

    def test_nonexistent_path_returns_false(self) -> None:
        assert is_tagged_pdf(Path("/nonexistent/file.pdf")) is False

    def test_corrupt_pdf_returns_false(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        assert is_tagged_pdf(bad) is False


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
            pytest.param(None, None, id="none-input"),
            pytest.param("", None, id="empty-string"),
            pytest.param("   \n\x0c  \n ", None, id="whitespace-and-formfeed-only"),
        ],
    )
    def test_post_process_text(
        self,
        source: str | None,
        expected: str | None,
    ) -> None:
        assert post_process_text(source) == expected


class TestPdfBornDigitalText:
    """Regression coverage for GH #13387.

    should_produce_archive() and RasterisedDocumentParser.parse() must agree
    on whether a PDF has real text, so both go through this one function.
    """

    @pytest.mark.parametrize(
        ("extracted", "tagged", "expected_text", "expected_born_digital"),
        [
            pytest.param("tiny", True, "tiny", True, id="tagged-with-real-text"),
            pytest.param("tiny", False, "tiny", False, id="untagged-below-min-length"),
            pytest.param(
                "x" * 51,
                False,
                "x" * 51,
                True,
                id="untagged-above-min-length",
            ),
            pytest.param(None, True, None, False, id="tagged-but-no-text"),
        ],
    )
    def test_born_digital_decision(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        extracted: str | None,
        tagged: bool,  # noqa: FBT001
        expected_text: str | None,
        expected_born_digital: bool,  # noqa: FBT001
    ) -> None:
        """
        GIVEN:
            - A PDF whose pdftotext output and /MarkInfo tag status vary
        WHEN:
            - pdf_born_digital_text() is called
        THEN:
            - The normalized text and born-digital verdict match; the tag
              alone never counts as "has text"
        """
        mocker.patch(
            "paperless.parsers.utils.extract_pdf_text",
            return_value=extracted,
        )
        mocker.patch("paperless.parsers.utils.is_tagged_pdf", return_value=tagged)
        text, born_digital = pdf_born_digital_text(tmp_path / "doc.pdf")
        assert text == expected_text
        assert born_digital is expected_born_digital

    def test_tagged_but_textless_pdf_is_not_born_digital(
        self,
        tagged_no_text_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - A real PDF that is tagged (/MarkInfo /Marked true) but whose
              only "text" is layout padding (a stray form-feed byte)
        WHEN:
            - pdf_born_digital_text() is called with no mocking
        THEN:
            - The normalized text is None and the PDF is not treated as
              born-digital. The raw, unnormalized pdftotext output is
              non-empty for this file, which is exactly what caused the
              archive decision to disagree with the OCR decision in #13387.
        """
        text, born_digital = pdf_born_digital_text(tagged_no_text_pdf_file)
        assert text is None
        assert born_digital is False
