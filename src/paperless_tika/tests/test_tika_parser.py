import datetime
import os
from pathlib import Path
from unittest import mock

from django.test import TestCase
from requests import Response

from paperless_tika.parsers import TikaDocumentParser


class TestTikaParser(TestCase):

    def setUp(self) -> None:
        self.parser = TikaDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    @mock.patch("paperless_tika.parsers.parser.from_file")
    @mock.patch("paperless_tika.parsers.requests.post")
    def test_parse(self, post, from_file):
        from_file.return_value = {
            "content": "the content",
            "metadata": {
                "Creation-Date": "2020-11-21"
            }
        }
        response = Response()
        response._content = b"PDF document"
        response.status_code = 200
        post.return_value = response

        file = os.path.join(self.parser.tempdir, "input.odt")
        Path(file).touch()
        self.parser.parse(file, "application/vnd.oasis.opendocument.text")

        self.assertEqual(self.parser.text, "the content")
        self.assertIsNotNone(self.parser.archive_path)
        with open(self.parser.archive_path, "rb") as f:
            self.assertEqual(f.read(), b"PDF document")

        self.assertEqual(self.parser.date, datetime.datetime(2020, 11, 21))

    @mock.patch("paperless_tika.parsers.parser.from_file")
    def test_metadata(self, from_file):
        from_file.return_value = {
            "metadata": {
                "Creation-Date": "2020-11-21",
                "Some-key": "value"
            }
        }

        file = os.path.join(self.parser.tempdir, "input.odt")
        Path(file).touch()

        metadata = self.parser.extract_metadata(file, "application/vnd.oasis.opendocument.text")

        self.assertTrue("Creation-Date" in [m['key'] for m in metadata])
        self.assertTrue("Some-key" in [m['key'] for m in metadata])
