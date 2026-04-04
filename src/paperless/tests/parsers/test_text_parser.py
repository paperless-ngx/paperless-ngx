"""
Tests for paperless.parsers.text.TextDocumentParser.

All tests use the context-manager protocol for parser lifecycle.  Sample
files are provided by session-scoped fixtures defined in conftest.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.text import TextDocumentParser


class TestTextParserProtocol:
    """Verify that TextDocumentParser satisfies the ParserProtocol contract."""

    def test_isinstance_satisfies_protocol(
        self,
        text_parser: TextDocumentParser,
    ) -> None:
        assert isinstance(text_parser, ParserProtocol)

    def test_class_attributes_present(self) -> None:
        assert isinstance(TextDocumentParser.name, str) and TextDocumentParser.name
        assert (
            isinstance(TextDocumentParser.version, str) and TextDocumentParser.version
        )
        assert isinstance(TextDocumentParser.author, str) and TextDocumentParser.author
        assert isinstance(TextDocumentParser.url, str) and TextDocumentParser.url

    def test_supported_mime_types_returns_dict(self) -> None:
        mime_types = TextDocumentParser.supported_mime_types()
        assert isinstance(mime_types, dict)
        assert "text/plain" in mime_types
        assert "text/csv" in mime_types
        assert "application/csv" in mime_types

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            ("text/plain", 10),
            ("text/csv", 10),
            ("application/csv", 10),
            ("application/pdf", None),
            ("image/png", None),
        ],
    )
    def test_score(self, mime_type: str, expected: int | None) -> None:
        assert TextDocumentParser.score(mime_type, "file.txt") == expected

    def test_can_produce_archive_is_false(
        self,
        text_parser: TextDocumentParser,
    ) -> None:
        assert text_parser.can_produce_archive is False

    def test_requires_pdf_rendition_is_false(
        self,
        text_parser: TextDocumentParser,
    ) -> None:
        assert text_parser.requires_pdf_rendition is False


class TestTextParserLifecycle:
    """Verify context-manager behaviour and temporary directory cleanup."""

    def test_context_manager_cleans_up_tempdir(self) -> None:
        with TextDocumentParser() as parser:
            tempdir = parser._tempdir
            assert tempdir.exists()
        assert not tempdir.exists()

    def test_context_manager_cleans_up_after_exception(self) -> None:
        tempdir: Path | None = None
        with pytest.raises(RuntimeError):
            with TextDocumentParser() as parser:
                tempdir = parser._tempdir
                raise RuntimeError("boom")
        assert tempdir is not None
        assert not tempdir.exists()


class TestTextParserParse:
    """Verify parse() and the result accessors."""

    def test_parse_valid_utf8(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        text_parser.configure(ParserContext())
        text_parser.parse(sample_txt_file, "text/plain")

        assert text_parser.get_text() == "This is a test file.\n"

    def test_parse_returns_none_for_archive_path(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        text_parser.configure(ParserContext())
        text_parser.parse(sample_txt_file, "text/plain")

        assert text_parser.get_archive_path() is None

    def test_parse_returns_none_for_date(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        text_parser.configure(ParserContext())
        text_parser.parse(sample_txt_file, "text/plain")

        assert text_parser.get_date() is None

    def test_parse_invalid_utf8_bytes_replaced(
        self,
        text_parser: TextDocumentParser,
        malformed_txt_file: Path,
    ) -> None:
        """
        GIVEN:
            - A text file containing invalid UTF-8 byte sequences
        WHEN:
            - The file is parsed
        THEN:
            - Parsing succeeds
            - Invalid bytes are replaced with the Unicode replacement character
        """
        text_parser.configure(ParserContext())
        text_parser.parse(malformed_txt_file, "text/plain")

        assert text_parser.get_text() == "Pantothens\ufffdure\n"

    def test_get_text_none_before_parse(
        self,
        text_parser: TextDocumentParser,
    ) -> None:
        assert text_parser.get_text() is None


class TestTextParserThumbnail:
    """Verify thumbnail generation."""

    def test_thumbnail_exists_and_is_file(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        thumb = text_parser.get_thumbnail(sample_txt_file, "text/plain")

        assert thumb.exists()
        assert thumb.is_file()

    def test_thumbnail_large_file_does_not_read_all(
        self,
        text_parser: TextDocumentParser,
    ) -> None:
        """
        GIVEN:
            - A text file larger than 50 MB
        WHEN:
            - A thumbnail is requested
        THEN:
            - The thumbnail is generated without loading the full file
        """
        with tempfile.NamedTemporaryFile(
            delete=False,
            mode="w",
            encoding="utf-8",
            suffix=".txt",
        ) as tmp:
            tmp.write("A" * (51 * 1024 * 1024))
            large_file = Path(tmp.name)

        try:
            thumb = text_parser.get_thumbnail(large_file, "text/plain")
            assert thumb.exists()
            assert thumb.is_file()
        finally:
            large_file.unlink(missing_ok=True)

    def test_get_page_count_returns_none(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        assert text_parser.get_page_count(sample_txt_file, "text/plain") is None


class TestTextParserMetadata:
    """Verify extract_metadata behaviour."""

    def test_extract_metadata_returns_empty_list(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        result = text_parser.extract_metadata(sample_txt_file, "text/plain")

        assert result == []

    def test_extract_metadata_returns_list_type(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        result = text_parser.extract_metadata(sample_txt_file, "text/plain")

        assert isinstance(result, list)

    def test_extract_metadata_ignores_mime_type(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        """extract_metadata returns [] regardless of the mime_type argument."""
        assert text_parser.extract_metadata(sample_txt_file, "application/pdf") == []
        assert text_parser.extract_metadata(sample_txt_file, "text/csv") == []


class TestTextParserRegistry:
    """Verify that TextDocumentParser is registered by default."""

    def test_registered_in_defaults(self) -> None:
        from paperless.parsers.registry import ParserRegistry

        registry = ParserRegistry()
        registry.register_defaults()

        assert TextDocumentParser in registry._builtins

    def test_get_parser_for_text_plain(self) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        parser_cls = registry.get_parser_for_file("text/plain", "doc.txt")

        assert parser_cls is TextDocumentParser

    def test_get_parser_for_text_csv(self) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        parser_cls = registry.get_parser_for_file("text/csv", "data.csv")

        assert parser_cls is TextDocumentParser

    def test_get_parser_for_unknown_type_returns_none(self) -> None:
        from paperless.parsers.registry import get_parser_registry

        registry = get_parser_registry()
        parser_cls = registry.get_parser_for_file(
            "application/x-unknown-format",
            "doc.xyz",
        )

        assert parser_cls is None
