"""Tests for paperless.parsers.utils helpers."""

from __future__ import annotations

import codecs
from pathlib import Path

from paperless.parsers.utils import is_tagged_pdf
from paperless.parsers.utils import read_file_handle_unicode_errors

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
