import datetime
import os
import zoneinfo
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings
from httpx import Request
from httpx import Response
from rest_framework import status

from documents.parsers import ParseError
from paperless_tika.parsers import TikaDocumentParser
from paperless_tika.tests.utils import HttpxMockMixin


class TestTikaParser(HttpxMockMixin, TestCase):
    def setUp(self) -> None:
        self.parser = TikaDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    @override_settings(TIME_ZONE="America/Chicago")
    def test_parse(self):
        # Pretend parse response
        self.httpx_mock.add_response(
            json={
                "Content-Type": "application/vnd.oasis.opendocument.text",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "the content",
                "dcterms:created": "2020-11-21T00:00:00",
            },
        )
        # Pretend convert to PDF response
        self.httpx_mock.add_response(content=b"PDF document")

        file = Path(os.path.join(self.parser.tempdir, "input.odt"))
        file.touch()

        self.parser.parse(file, "application/vnd.oasis.opendocument.text")

        self.assertEqual(self.parser.text, "the content")
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertEqual(f.read(), b"PDF document")

        self.assertEqual(
            self.parser.date,
            datetime.datetime(
                2020,
                11,
                21,
                tzinfo=zoneinfo.ZoneInfo("America/Chicago"),
            ),
        )

    def test_metadata(self):
        self.httpx_mock.add_response(
            json={
                "Content-Type": "application/vnd.oasis.opendocument.text",
                "X-TIKA:Parsed-By": [],
                "Some-key": "value",
                "dcterms:created": "2020-11-21T00:00:00",
            },
        )

        file = Path(os.path.join(self.parser.tempdir, "input.odt"))
        file.touch()

        metadata = self.parser.extract_metadata(
            file,
            "application/vnd.oasis.opendocument.text",
        )

        self.assertTrue("dcterms:created" in [m["key"] for m in metadata])
        self.assertTrue("Some-key" in [m["key"] for m in metadata])

    def test_convert_failure(self):
        """
        GIVEN:
            - Document needs to be converted to PDF
        WHEN:
            - Gotenberg server returns an error
        THEN:
            - Parse error is raised
        """
        # Pretend convert to PDF response
        self.httpx_mock.add_response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        file = Path(os.path.join(self.parser.tempdir, "input.odt"))
        file.touch()

        with self.assertRaises(ParseError):
            self.parser.convert_to_pdf(file, None)

    @mock.patch("paperless_tika.parsers.httpx.post")
    def test_request_pdf_a_format(self, post: mock.Mock):
        """
        GIVEN:
            - Document needs to be converted to PDF
        WHEN:
            - Specific PDF/A format requested
        THEN:
            - Request to Gotenberg contains the expected PDF/A format string
        """
        file = Path(os.path.join(self.parser.tempdir, "input.odt"))
        file.touch()

        response = Response(status_code=status.HTTP_200_OK)
        response.request = Request("POST", "/somewhere/")
        post.return_value = response

        for setting, expected_key in [
            ("pdfa", "PDF/A-2b"),
            ("pdfa-2", "PDF/A-2b"),
            ("pdfa-1", "PDF/A-1a"),
            ("pdfa-3", "PDF/A-3b"),
        ]:
            with override_settings(OCR_OUTPUT_TYPE=setting):
                self.parser.convert_to_pdf(file, None)

                post.assert_called_once()
                _, kwargs = post.call_args

                self.assertEqual(kwargs["data"]["pdfFormat"], expected_key)

                post.reset_mock()
