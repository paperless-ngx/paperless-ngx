import os
from pathlib import Path

import pytest

from documents.tests.utils import util_call_with_backoff
from paperless.parsers.anydoc import AnydocDocumentParser

ODT_MIME = "application/vnd.oasis.opendocument.text"


@pytest.mark.django_db()
class TestAnydocParserNativePdfs:
    """
    Parses a real PDF through the pdf-inspector Rust library.  Requires no
    external services, so this runs everywhere the dependencies are installed.
    """

    def test_parse_text_based_pdf(
        self,
        anydoc_parser: AnydocDocumentParser,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - A born-digital PDF
        WHEN:
            - The document is parsed natively
        THEN:
            - Text is extracted without OCR and the page count is correct
        """
        anydoc_parser.parse(simple_digital_pdf_file, "application/pdf")

        assert "this is a test document" in anydoc_parser.get_text().lower()
        assert (
            anydoc_parser.get_page_count(
                simple_digital_pdf_file,
                "application/pdf",
            )
            == 1
        )
        # The original already is a PDF, so the archive is a byte-identical copy.
        archive = anydoc_parser.get_archive_path()
        assert archive is not None
        assert archive.read_bytes() == simple_digital_pdf_file.read_bytes()


@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg server to test with",
)
@pytest.mark.django_db()
@pytest.mark.live
@pytest.mark.gotenberg
class TestAnydocParserAgainstGotenberg:
    """
    Tests office document parsing with a real Gotenberg server for the PDF
    rendition, if the environment contains the correct value indicating such
    a server is available.
    """

    def test_basic_parse_odt(
        self,
        settings,
        anydoc_parser: AnydocDocumentParser,
        sample_odt_file: Path,
    ) -> None:
        """
        GIVEN:
            - An input ODT format document
        WHEN:
            - The document is parsed natively with Gotenberg available
        THEN:
            - Document content comes from anydoc
            - A PDF rendition is produced by Gotenberg
        """
        settings.ANYDOC_ENABLED = True

        util_call_with_backoff(anydoc_parser.parse, [sample_odt_file, ODT_MIME])

        assert "ODT test document" in anydoc_parser.get_text()
        archive = anydoc_parser.get_archive_path()
        assert archive is not None
        assert b"PDF-" in archive.read_bytes()[:10]

    def test_basic_parse_docx(
        self,
        settings,
        anydoc_parser: AnydocDocumentParser,
        sample_docx_file: Path,
    ) -> None:
        """
        GIVEN:
            - An input DOCX format document
        WHEN:
            - The document is parsed natively with Gotenberg available
        THEN:
            - Document content comes from anydoc
            - A PDF rendition is produced by Gotenberg
        """
        settings.ANYDOC_ENABLED = True

        util_call_with_backoff(
            anydoc_parser.parse,
            [
                sample_docx_file,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
        )

        assert "DOCX test document" in anydoc_parser.get_text()
        archive = anydoc_parser.get_archive_path()
        assert archive is not None
        assert b"PDF-" in archive.read_bytes()[:10]
