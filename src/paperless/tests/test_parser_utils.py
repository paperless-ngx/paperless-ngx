"""Tests for paperless.parsers.utils helpers."""

from __future__ import annotations

from pathlib import Path

from paperless.parsers.utils import is_tagged_pdf

SAMPLES = Path(__file__).parent / "samples" / "tesseract"


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
