import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import httpx
import pytest
from django.test import TestCase
from imagehash import average_hash
from PIL import Image

from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import util_call_with_backoff
from paperless_mail.tests.test_parsers import BaseMailParserTestCase


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
class TestUrlCanary(TestCase):
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
        with self.assertRaises(httpx.HTTPStatusError) as cm:
            resp = httpx.get(
                "https://upload.wikimedia.org/wikipedia/en/f/f7/nonexistent.png",
            )
            resp.raise_for_status()

        self.assertEqual(cm.exception.response.status_code, httpx.codes.NOT_FOUND)

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
class TestParserLive(FileSystemAssertsMixin, BaseMailParserTestCase):
    @staticmethod
    def imagehash(file, hash_size=18):
        return f"{average_hash(Image.open(file), hash_size)}"

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    def test_get_thumbnail(self, mock_generate_pdf: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - The Thumbnail is requested
        THEN:
            - The returned thumbnail image file is as expected
        """
        mock_generate_pdf.return_value = self.SAMPLE_DIR / "simple_text.eml.pdf"
        thumb = self.parser.get_thumbnail(
            self.SAMPLE_DIR / "simple_text.eml",
            "message/rfc822",
        )
        self.assertIsFile(thumb)

        expected = self.SAMPLE_DIR / "simple_text.eml.pdf.webp"

        self.assertEqual(
            self.imagehash(thumb),
            self.imagehash(expected),
            f"Created Thumbnail {thumb} differs from expected file {expected}",
        )

    def test_tika_parse_successful(self):
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
        parsed = self.parser.tika_parse(html)
        self.assertEqual(expected_text, parsed.strip())

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf_gotenberg_merging(
        self,
        mock_generate_pdf_from_html: mock.MagicMock,
        mock_generate_pdf_from_mail: mock.MagicMock,
    ):
        """
        GIVEN:
            - Intermediary pdfs to be merged
        WHEN:
            - pdf generation is requested with html file requiring merging of pdfs
        THEN:
            - gotenberg is called to merge files and the resulting file is returned
        """
        mock_generate_pdf_from_mail.return_value = self.SAMPLE_DIR / "first.pdf"
        mock_generate_pdf_from_html.return_value = self.SAMPLE_DIR / "second.pdf"

        msg = self.parser.parse_file_to_message(
            self.SAMPLE_DIR / "html.eml",
        )

        _, pdf_path = util_call_with_backoff(
            self.parser.generate_pdf,
            [msg],
        )
        self.assertIsFile(pdf_path)

        extracted = extract_text(pdf_path)
        expected = (
            "first   PDF   to   be   merged.\n\x0csecond PDF   to   be   merged.\n\x0c"
        )

        self.assertEqual(expected, extracted)

    def test_generate_pdf_from_mail(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from simple eml file is requested
        THEN:
            - gotenberg is called and the resulting file is returned and look as expected.
        """

        util_call_with_backoff(
            self.parser.parse,
            [self.SAMPLE_DIR / "html.eml", "message/rfc822"],
        )

        # Check the archive PDF
        archive_path = self.parser.get_archive_path()
        archive_text = extract_text(archive_path)
        expected_archive_text = extract_text(self.SAMPLE_DIR / "html.eml.pdf")

        # Archive includes the HTML content, so use in
        self.assertIn(expected_archive_text, archive_text)

        # Check the thumbnail
        generated_thumbnail = self.parser.get_thumbnail(
            self.SAMPLE_DIR / "html.eml",
            "message/rfc822",
        )
        generated_thumbnail_hash = self.imagehash(generated_thumbnail)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = self.imagehash(self.SAMPLE_DIR / "html.eml.pdf.webp")

        self.assertEqual(
            generated_thumbnail_hash,
            expected_hash,
            f"PDF looks different. Check if {generated_thumbnail} looks weird.",
        )
