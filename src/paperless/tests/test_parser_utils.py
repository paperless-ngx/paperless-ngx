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

    def test_tagged_pdf_with_real_text_is_born_digital(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        mocker.patch(
            "paperless.parsers.utils.extract_pdf_text",
            return_value="tiny",
        )
        mocker.patch("paperless.parsers.utils.is_tagged_pdf", return_value=True)
        text, born_digital = pdf_born_digital_text(tmp_path / "doc.pdf")
        assert text == "tiny"
        assert born_digital is True

    def test_untagged_pdf_below_min_length_is_not_born_digital(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        mocker.patch(
            "paperless.parsers.utils.extract_pdf_text",
            return_value="tiny",
        )
        mocker.patch("paperless.parsers.utils.is_tagged_pdf", return_value=False)
        text, born_digital = pdf_born_digital_text(tmp_path / "doc.pdf")
        assert text == "tiny"
        assert born_digital is False

    def test_untagged_pdf_above_min_length_is_born_digital(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        mocker.patch(
            "paperless.parsers.utils.extract_pdf_text",
            return_value="x" * 51,
        )
        mocker.patch("paperless.parsers.utils.is_tagged_pdf", return_value=False)
        _text, born_digital = pdf_born_digital_text(tmp_path / "doc.pdf")
        assert born_digital is True

    def test_no_text_is_not_born_digital(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        mocker.patch("paperless.parsers.utils.extract_pdf_text", return_value=None)
        mocker.patch("paperless.parsers.utils.is_tagged_pdf", return_value=True)
        text, born_digital = pdf_born_digital_text(tmp_path / "doc.pdf")
        assert text is None
        assert born_digital is False
