import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
import pytest
from imagehash import average_hash
from PIL import Image
from pytest_mock import MockerFixture

from documents.tests.utils import util_call_with_backoff
from paperless_mail.parsers import MailDocumentParser


def extract_text(pdf_path: Path) -> str:
    """
    Using pdftotext from poppler, extracts the text of a PDF into a file,
    then reads the file contents and returns it.
    """
    with tempfile.NamedTemporaryFile(
        mode="w+",
    ) as tmp:
        subprocess.run(
            [
                shutil.which("pdftotext"),
                "-q",
                "-layout",
                "-enc",
                "UTF-8",
                str(pdf_path),
                tmp.name,
            ],
            check=True,
        )
        return tmp.read()


class MailAttachmentMock:
    def __init__(self, payload: bytes, content_id: str) -> None:
        self.payload = payload
        self.content_id = content_id
        self.content_type = "image/png"


@pytest.mark.live
@pytest.mark.nginx
@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg/Tika servers to test with",
)
class TestNginxService:
    """
    Verify the local nginx server is responding correctly.
    These tests validate that the test infrastructure is working properly
    before running the actual parser tests that depend on HTTP resources.
    """

    def test_non_existent_resource_returns_404(
        self,
        nginx_base_url: str,
    ) -> None:
        """
        GIVEN:
            - Local nginx server is running
        WHEN:
            - A non-existent resource is requested
        THEN:
            - An HTTP 404 status code shall be returned
        """
        resp = httpx.get(
            f"{nginx_base_url}/assets/non-existent.png",
            timeout=5.0,
        )
        with pytest.raises(httpx.HTTPStatusError) as exec_info:
            resp.raise_for_status()

        assert exec_info.value.response.status_code == httpx.codes.NOT_FOUND

    def test_valid_resource_is_available(
        self,
        nginx_base_url: str,
    ) -> None:
        """
        GIVEN:
            - Local nginx server is running
        WHEN:
            - A valid test fixture resource is requested
        THEN:
            - The resource shall be returned with HTTP 200 status code
            - The response shall contain the expected content type
        """
        resp = httpx.get(
            f"{nginx_base_url}/assets/logo_full_white.svg",
            timeout=5.0,
        )
        resp.raise_for_status()

        assert resp.status_code == httpx.codes.OK
        assert "svg" in resp.headers.get("content-type", "").lower()

    def test_server_connectivity(
        self,
        nginx_base_url: str,
    ) -> None:
        """
        GIVEN:
            - Local test fixtures server should be running
        WHEN:
            - A request is made to the server root
        THEN:
            - The server shall respond without connection errors
        """
        try:
            resp = httpx.get(
                nginx_base_url,
                timeout=5.0,
                follow_redirects=True,
            )
            # We don't care about the status code, just that we can connect
            assert resp.status_code in {200, 404, 403}
        except httpx.ConnectError as e:
            pytest.fail(
                f"Cannot connect to nginx server at {nginx_base_url}. "
                f"Ensure the nginx container is running via docker-compose.ci-test.yml. "
                f"Error: {e}",
            )


@pytest.mark.live
@pytest.mark.gotenberg
@pytest.mark.tika
@pytest.mark.nginx
@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg/Tika servers to test with",
)
class TestParserLive:
    @staticmethod
    def imagehash(file: Path, hash_size: int = 18) -> str:
        return f"{average_hash(Image.open(file), hash_size)}"

    def test_get_thumbnail(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
        simple_txt_email_pdf_file: Path,
        simple_txt_email_thumbnail_file: Path,
    ) -> None:
        """
        GIVEN:
            - A simple text email file
            - Mocked PDF generation returning a known PDF
        WHEN:
            - The thumbnail is requested
        THEN:
            - The returned thumbnail image file shall match the expected hash
        """
        mock_generate_pdf = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf",
        )
        mock_generate_pdf.return_value = simple_txt_email_pdf_file

        thumb = mail_parser.get_thumbnail(simple_txt_email_file, "message/rfc822")

        assert thumb.exists()
        assert thumb.is_file()

        assert self.imagehash(thumb) == self.imagehash(
            simple_txt_email_thumbnail_file,
        ), (
            f"Created thumbnail {thumb} differs from expected file "
            f"{simple_txt_email_thumbnail_file}"
        )

    def test_tika_parse_successful(self, mail_parser: MailDocumentParser) -> None:
        """
        GIVEN:
            - HTML content to parse
            - Tika server is running
        WHEN:
            - Tika parsing is called
        THEN:
            - A web request to Tika shall be made
            - The parsed text content shall be returned
        """
        html = (
            '<html><head><meta http-equiv="content-type" '
            'content="text/html; charset=UTF-8"></head>'
            "<body><p>Some Text</p></body></html>"
        )
        expected_text = "Some Text"

        parsed = mail_parser.tika_parse(html)
        assert expected_text == parsed.strip()

    def test_generate_pdf_gotenberg_merging(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        merged_pdf_first: Path,
        merged_pdf_second: Path,
    ) -> None:
        """
        GIVEN:
            - Intermediary PDFs to be merged
            - An HTML email file
        WHEN:
            - PDF generation is requested with HTML file requiring merging
        THEN:
            - Gotenberg shall be called to merge files
            - The resulting merged PDF shall be returned
            - The merged PDF shall contain text from both source PDFs
        """
        mock_generate_pdf_from_html = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html",
        )
        mock_generate_pdf_from_mail = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail",
        )
        mock_generate_pdf_from_mail.return_value = merged_pdf_first
        mock_generate_pdf_from_html.return_value = merged_pdf_second

        msg = mail_parser.parse_file_to_message(html_email_file)

        _, pdf_path = util_call_with_backoff(
            mail_parser.generate_pdf,
            [msg],
        )
        assert pdf_path.exists()
        assert pdf_path.is_file()

        extracted = extract_text(pdf_path)
        expected = (
            "first   PDF   to   be   merged.\n\x0csecond PDF   to   be   merged.\n\x0c"
        )

        assert expected == extracted

    def test_generate_pdf_from_mail(
        self,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_pdf_file: Path,
        html_email_thumbnail_file: Path,
    ) -> None:
        """
        GIVEN:
            - An HTML email file
        WHEN:
            - PDF generation from the email file is requested
        THEN:
            - Gotenberg shall be called to generate the PDF
            - The archive PDF shall contain the expected content
            - The generated thumbnail shall match the expected image hash
        """
        util_call_with_backoff(mail_parser.parse, [html_email_file, "message/rfc822"])

        # Check the archive PDF
        archive_path = mail_parser.get_archive_path()
        archive_text = extract_text(archive_path)
        expected_archive_text = extract_text(html_email_pdf_file)

        # Archive includes the HTML content
        assert expected_archive_text in archive_text

        # Check the thumbnail
        generated_thumbnail = mail_parser.get_thumbnail(
            html_email_file,
            "message/rfc822",
        )
        generated_thumbnail_hash = self.imagehash(generated_thumbnail)

        # The created PDF is not reproducible, but the converted image
        # should always look the same
        expected_hash = self.imagehash(html_email_thumbnail_file)

        assert generated_thumbnail_hash == expected_hash, (
            f"PDF thumbnail differs from expected. "
            f"Generated: {generated_thumbnail}, "
            f"Hash: {generated_thumbnail_hash} vs {expected_hash}"
        )
