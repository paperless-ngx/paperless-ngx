import os
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from django.test import TestCase
from documents.parsers import ParseError
from documents.parsers import run_convert
from imagehash import average_hash
from paperless_mail.parsers import MailDocumentParser
from pdfminer.high_level import extract_text
from PIL import Image


class TestParserLive(TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def setUp(self) -> None:
        self.parser = MailDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    @staticmethod
    def imagehash(file, hash_size=18):
        return f"{average_hash(Image.open(file), hash_size)}"

    # Only run if convert is available
    @pytest.mark.skipif(
        "PAPERLESS_TEST_SKIP_CONVERT" in os.environ,
        reason="PAPERLESS_TEST_SKIP_CONVERT set, skipping Test",
    )
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
        mock_generate_pdf.return_value = os.path.join(
            self.SAMPLE_FILES,
            "simple_text.eml.pdf",
        )
        thumb = self.parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        self.assertTrue(os.path.isfile(thumb))

        expected = os.path.join(self.SAMPLE_FILES, "simple_text.eml.pdf.webp")

        self.assertEqual(
            self.imagehash(thumb),
            self.imagehash(expected),
            f"Created Thumbnail {thumb} differs from expected file {expected}",
        )

    @pytest.mark.skipif(
        "TIKA_LIVE" not in os.environ,
        reason="No tika server",
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

    @pytest.mark.skipif(
        "TIKA_LIVE" not in os.environ,
        reason="No tika server",
    )
    def test_tika_parse_unsuccessful(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing fails
        THEN:
            - the parser should return an empty string
        """
        # Check unsuccessful parsing
        parsed = self.parser.tika_parse(None)
        self.assertEqual("", parsed)

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
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
        with open(os.path.join(self.SAMPLE_FILES, "first.pdf"), "rb") as first:
            mock_generate_pdf_from_mail.return_value = first.read()

        with open(os.path.join(self.SAMPLE_FILES, "second.pdf"), "rb") as second:
            mock_generate_pdf_from_html.return_value = second.read()

        pdf_path = self.parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))
        self.assertTrue(os.path.isfile(pdf_path))

        extracted = extract_text(pdf_path)
        expected = (
            "first\tPDF\tto\tbe\tmerged.\n\n\x0csecond\tPDF\tto\tbe\tmerged.\n\n\x0c"
        )
        self.assertEqual(expected, extracted)

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
    def test_generate_pdf_from_mail_no_convert(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from simple eml file is requested
        THEN:
            - gotenberg is called and the resulting file is returned and contains the expected text.
        """
        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))

        pdf_path = os.path.join(self.parser.tempdir, "html.eml.pdf")

        with open(pdf_path, "wb") as file:
            file.write(self.parser.generate_pdf_from_mail(mail))

        extracted = extract_text(pdf_path)
        expected = extract_text(os.path.join(self.SAMPLE_FILES, "html.eml.pdf"))
        self.assertEqual(expected, extracted)

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
    # Only run if convert is available
    @pytest.mark.skipif(
        "PAPERLESS_TEST_SKIP_CONVERT" in os.environ,
        reason="PAPERLESS_TEST_SKIP_CONVERT set, skipping Test",
    )
    def test_generate_pdf_from_mail(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from simple eml file is requested
        THEN:
            - gotenberg is called and the resulting file is returned and look as expected.
        """
        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))

        pdf_path = os.path.join(self.parser.tempdir, "html.eml.pdf")

        with open(pdf_path, "wb") as file:
            file.write(self.parser.generate_pdf_from_mail(mail))

        converted = os.path.join(
            self.parser.tempdir,
            "html.eml.pdf.webp",
        )
        run_convert(
            density=300,
            scale="500x5000>",
            alpha="remove",
            strip=True,
            trim=False,
            auto_orient=True,
            input_file=f"{pdf_path}",  # Do net define an index to convert all pages.
            output_file=converted,
            logging_group=None,
        )
        self.assertTrue(os.path.isfile(converted))
        thumb_hash = self.imagehash(converted)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = self.imagehash(
            os.path.join(self.SAMPLE_FILES, "html.eml.pdf.webp"),
        )
        self.assertEqual(
            thumb_hash,
            expected_hash,
            f"PDF looks different. Check if {converted} looks weird.",
        )

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
    def test_generate_pdf_from_html_no_convert(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from html eml file is requested
        THEN:
            - gotenberg is called and the resulting file is returned and contains the expected text.
        """

        class MailAttachmentMock:
            def __init__(self, payload, content_id):
                self.payload = payload
                self.content_id = content_id

        result = None

        with open(os.path.join(self.SAMPLE_FILES, "sample.html")) as html_file:
            with open(os.path.join(self.SAMPLE_FILES, "sample.png"), "rb") as png_file:
                html = html_file.read()
                png = png_file.read()
                attachments = [
                    MailAttachmentMock(png, "part1.pNdUSz0s.D3NqVtPg@example.de"),
                ]
                result = self.parser.generate_pdf_from_html(html, attachments)

        pdf_path = os.path.join(self.parser.tempdir, "sample.html.pdf")

        with open(pdf_path, "wb") as file:
            file.write(result)

        extracted = extract_text(pdf_path)
        expected = extract_text(os.path.join(self.SAMPLE_FILES, "sample.html.pdf"))
        self.assertEqual(expected, extracted)

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
    # Only run if convert is available
    @pytest.mark.skipif(
        "PAPERLESS_TEST_SKIP_CONVERT" in os.environ,
        reason="PAPERLESS_TEST_SKIP_CONVERT set, skipping Test",
    )
    def test_generate_pdf_from_html(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation from html eml file is requested
        THEN:
            - gotenberg is called and the resulting file is returned and look as expected.
        """

        class MailAttachmentMock:
            def __init__(self, payload, content_id):
                self.payload = payload
                self.content_id = content_id

        result = None

        with open(os.path.join(self.SAMPLE_FILES, "sample.html")) as html_file:
            with open(os.path.join(self.SAMPLE_FILES, "sample.png"), "rb") as png_file:
                html = html_file.read()
                png = png_file.read()
                attachments = [
                    MailAttachmentMock(png, "part1.pNdUSz0s.D3NqVtPg@example.de"),
                ]
                result = self.parser.generate_pdf_from_html(html, attachments)

        pdf_path = os.path.join(self.parser.tempdir, "sample.html.pdf")

        with open(pdf_path, "wb") as file:
            file.write(result)

        converted = os.path.join(self.parser.tempdir, "sample.html.pdf.webp")
        run_convert(
            density=300,
            scale="500x5000>",
            alpha="remove",
            strip=True,
            trim=False,
            auto_orient=True,
            input_file=f"{pdf_path}",  # Do net define an index to convert all pages.
            output_file=converted,
            logging_group=None,
        )
        self.assertTrue(os.path.isfile(converted))
        thumb_hash = self.imagehash(converted)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = self.imagehash(
            os.path.join(self.SAMPLE_FILES, "sample.html.pdf.webp"),
        )

        self.assertEqual(
            thumb_hash,
            expected_hash,
            f"PDF looks different. Check if {converted} looks weird. "
            f"If Rick Astley is shown, Gotenberg loads from web which is bad for Mail content.",
        )

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
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

        # Start by Testing if nonexistent URL really throws an Exception
        self.assertRaises(
            HTTPError,
            urlopen,
            "https://upload.wikimedia.org/wikipedia/en/f/f7/nonexistent.png",
        )

    @pytest.mark.skipif(
        "GOTENBERG_LIVE" not in os.environ,
        reason="No gotenberg server",
    )
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
        urlopen("https://upload.wikimedia.org/wikipedia/en/f/f7/RickRoll.png")
