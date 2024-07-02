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
    then reads the file contents and returns it
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
    def __init__(self, payload, content_id):
        self.payload = payload
        self.content_id = content_id
        self.content_type = "image/png"


@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg/Tika servers to test with",
)
class TestUrlCanary:
    """
    Verify certain URLs are still available so testing is valid still
    """

    def test_online_image_exception_on_not_available(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - nonexistent image is requested
        THEN:
            - An exception shall be thrown
        """
        """
        A public image is used in the html sample file. We have no control
        whether this image stays online forever, so here we check if we can detect if is not
        available anymore.
        """
        with pytest.raises(httpx.HTTPStatusError) as exec_info:
            resp = httpx.get(
                "https://upload.wikimedia.org/wikipedia/en/f/f7/nonexistent.png",
            )
            resp.raise_for_status()

        assert exec_info.value.response.status_code == httpx.codes.NOT_FOUND

    def test_is_online_image_still_available(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - A public image used in the html sample file is requested
        THEN:
            - No exception shall be thrown
        """
        """
        A public image is used in the html sample file. We have no control
        whether this image stays online forever, so here we check if it is still there
        """

        # Now check the URL used in samples/sample.html
        resp = httpx.get("https://upload.wikimedia.org/wikipedia/en/f/f7/RickRoll.png")
        resp.raise_for_status()


@pytest.mark.skipif(
    "PAPERLESS_CI_TEST" not in os.environ,
    reason="No Gotenberg/Tika servers to test with",
)
class TestParserLive:
    @staticmethod
    def imagehash(file, hash_size=18):
        return f"{average_hash(Image.open(file), hash_size)}"

    def test_get_thumbnail(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
        simple_txt_email_pdf_file: Path,
        simple_txt_email_thumbnail_file: Path,
    ):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - The Thumbnail is requested
        THEN:
            - The returned thumbnail image file is as expected
        """
        mock_generate_pdf = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf",
        )
        mock_generate_pdf.return_value = simple_txt_email_pdf_file

        thumb = mail_parser.get_thumbnail(simple_txt_email_file, "message/rfc822")

        assert thumb.exists()
        assert thumb.is_file()

        assert (
            self.imagehash(thumb) == self.imagehash(simple_txt_email_thumbnail_file)
        ), f"Created Thumbnail {thumb} differs from expected file {simple_txt_email_thumbnail_file}"

    def test_tika_parse_successful(self, mail_parser: MailDocumentParser):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called
        THEN:
            - a web request to tika shall be done and the reply es returned
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'
        expected_text = "Some Text"

        # Check successful parsing
        parsed = mail_parser.tika_parse(html)
        assert expected_text == parsed.strip()

    def test_generate_pdf_gotenberg_merging(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        merged_pdf_first: Path,
        merged_pdf_second: Path,
    ):
        """
        GIVEN:
            - Intermediary pdfs to be merged
        WHEN:
            - pdf generation is requested with html file requiring merging of pdfs
        THEN:
            - gotenberg is called to merge files and the resulting file is returned
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
    ):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from simple eml file is requested
        THEN:
            - Gotenberg is called and the resulting file is returned and look as expected.
        """

        util_call_with_backoff(mail_parser.parse, [html_email_file, "message/rfc822"])

        # Check the archive PDF
        archive_path = mail_parser.get_archive_path()
        archive_text = extract_text(archive_path)
        expected_archive_text = extract_text(html_email_pdf_file)

        # Archive includes the HTML content, so use in
        assert expected_archive_text in archive_text

        # Check the thumbnail
        generated_thumbnail = mail_parser.get_thumbnail(
            html_email_file,
            "message/rfc822",
        )
        generated_thumbnail_hash = self.imagehash(generated_thumbnail)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = self.imagehash(html_email_thumbnail_file)

        assert (
            generated_thumbnail_hash == expected_hash
        ), f"PDF looks different. Check if {generated_thumbnail} looks weird."
