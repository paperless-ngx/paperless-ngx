import tempfile
from pathlib import Path

from paperless_text.parsers import TextDocumentParser


class TestTextParser:
    def test_thumbnail(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        # just make sure that it does not crash
        f = text_parser.get_thumbnail(sample_txt_file, "text/plain")
        assert f.exists()
        assert f.is_file()

    def test_parse(
        self,
        text_parser: TextDocumentParser,
        sample_txt_file: Path,
    ) -> None:
        text_parser.parse(sample_txt_file, "text/plain")

        assert text_parser.get_text() == "This is a test file.\n"
        assert text_parser.get_archive_path() is None

    def test_parse_invalid_bytes(
        self,
        text_parser: TextDocumentParser,
        malformed_txt_file: Path,
    ) -> None:
        """
        GIVEN:
            - Text file which contains invalid UTF bytes
        WHEN:
            - The file is parsed
        THEN:
            - Parsing continues
            - Invalid bytes are removed
        """

        text_parser.parse(malformed_txt_file, "text/plain")

        assert text_parser.get_text() == "Pantothens�ure\n"
        assert text_parser.get_archive_path() is None

    def test_thumbnail_large_file(self, text_parser: TextDocumentParser) -> None:
        """
        GIVEN:
            - A very large text file (>50MB)
        WHEN:
            - A thumbnail is requested
        THEN:
            - A thumbnail is created without reading the entire file into memory
        """
        with tempfile.NamedTemporaryFile(
            delete=False,
            mode="w",
            encoding="utf-8",
            suffix=".txt",
        ) as tmp:
            tmp.write("A" * (51 * 1024 * 1024))  # 51 MB of 'A'
            large_file = Path(tmp.name)

            thumb = text_parser.get_thumbnail(large_file, "text/plain")
            assert thumb.exists()
            assert thumb.is_file()
            large_file.unlink()
