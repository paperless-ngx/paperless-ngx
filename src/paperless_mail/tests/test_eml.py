import datetime
import hashlib
import os
from unittest import mock

import pytest
from django.test import TestCase
from documents.parsers import ParseError
from documents.parsers import run_convert
from paperless_mail.parsers import MailDocumentParser


class TestParser(TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_get_parsed(self):
        parser = MailDocumentParser(None)

        # Check if exception is raised when parsing fails.
        with pytest.raises(ParseError):
            parser.get_parsed(os.path.join(os.path.join(self.SAMPLE_FILES, "na")))

        # Parse Test file and check relevant content
        parsed1 = parser.get_parsed(os.path.join(self.SAMPLE_FILES, "simple_text.eml"))

        self.assertEqual(parsed1.date.year, 2022)
        self.assertEqual(parsed1.date.month, 10)
        self.assertEqual(parsed1.date.day, 12)
        self.assertEqual(parsed1.date.hour, 21)
        self.assertEqual(parsed1.date.minute, 40)
        self.assertEqual(parsed1.date.second, 43)
        self.assertEqual(parsed1.date.tzname(), "UTC+02:00")
        self.assertEqual(parsed1.from_, "mail@someserver.de")
        self.assertEqual(parsed1.subject, "Simple Text Mail")
        self.assertEqual(parsed1.text, "This is just a simple Text Mail.\n")
        self.assertEqual(parsed1.to, ("some@one.de",))

        # Check if same parsed object as before is returned, even if another file is given.
        parsed2 = parser.get_parsed(os.path.join(os.path.join(self.SAMPLE_FILES, "na")))
        self.assertEqual(parsed1, parsed2)

    @staticmethod
    def hashfile(file):
        buf_size = 65536  # An arbitrary (but fixed) buffer
        sha256 = hashlib.sha256()
        with open(file, "rb") as f:
            while True:
                data = f.read(buf_size)
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()

    def test_get_thumbnail(self):
        parser = MailDocumentParser(None)
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        self.assertTrue(os.path.isfile(thumb))
        thumb_hash = self.hashfile(thumb)

        # The created intermediary pdf is not reproducible. But the thumbnail image should always look the same.
        expected_hash = (
            "18a2513c80584e538c4a129e8a2b0ce19bf0276eab9c95b72fa93e941db38d12"
        )
        self.assertEqual(
            thumb_hash,
            expected_hash,
            "Thumbnail file hash not as expected.",
        )

    @mock.patch("documents.loggers.LoggingMixin.log")
    def test_extract_metadata(self, m: mock.MagicMock):
        parser = MailDocumentParser(None)

        # Validate if warning is logged when parsing fails
        self.assertEqual([], parser.extract_metadata("na", "message/rfc822"))
        self.assertEqual("warning", m.call_args[0][0])

        # Validate Metadata parsing returns the expected results
        metadata = parser.extract_metadata(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )

        self.assertTrue(
            {"namespace": "", "prefix": "", "key": "attachments", "value": ""}
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "",
                "key": "date",
                "value": "2022-10-12 21:40:43 UTC+02:00",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "content-language",
                "value": "en-US",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "content-type",
                "value": "text/plain; charset=UTF-8; format=flowed",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "date",
                "value": "Wed, 12 Oct 2022 21:40:43 +0200",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "delivered-to",
                "value": "mail@someserver.de",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "from",
                "value": "Some One <mail@someserver.de>",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "message-id",
                "value": "<6e99e34d-e20a-80c4-ea61-d8234b612be9@someserver.de>",
            }
            in metadata,
        )
        self.assertTrue(
            {"namespace": "", "prefix": "header", "key": "mime-version", "value": "1.0"}
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "received",
                "value": "from mail.someserver.org ([::1])\n\tby e1acdba3bd07 with LMTP\n\tid KBKZGD2YR2NTCgQAjubtDA\n\t(envelope-from <mail@someserver.de>)\n\tfor <mail@someserver.de>; Wed, 10 Oct 2022 11:40:46 +0200, from [127.0.0.1] (localhost [127.0.0.1]) by localhost (Mailerdaemon) with ESMTPSA id 2BC9064C1616\n\tfor <some@one.de>; Wed, 12 Oct 2022 21:40:46 +0200 (CEST)",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "return-path",
                "value": "<mail@someserver.de>",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "subject",
                "value": "Simple Text Mail",
            }
            in metadata,
        )
        self.assertTrue(
            {"namespace": "", "prefix": "header", "key": "to", "value": "some@one.de"}
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "user-agent",
                "value": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101\n Thunderbird/102.3.1",
            }
            in metadata,
        )
        self.assertTrue(
            {
                "namespace": "",
                "prefix": "header",
                "key": "x-last-tls-session-version",
                "value": "TLSv1.3",
            }
            in metadata,
        )

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_parse(self, m):
        parser = MailDocumentParser(None)

        # Check if exception is raised when parsing fails.
        with pytest.raises(ParseError):
            parser.parse(
                os.path.join(os.path.join(self.SAMPLE_FILES, "na")),
                "message/rfc822",
            )

        # Validate parsing returns the expected results
        parser.parse(os.path.join(self.SAMPLE_FILES, "html.eml"), "message/rfc822")

        text_expected = "Some Text\nand an embedded image.\n\nSubject: HTML Message\n\nFrom: Name <someone@example.de>\n\nTo: someone@example.de\n\nAttachments: IntM6gnXFm00FEV5.png (6.89 KiB)\n\nHTML content: Some Text\nand an embedded image.Attachments: IntM6gnXFm00FEV5.png (6.89 KiB)\n\n"
        self.assertEqual(text_expected, parser.text)
        self.assertEqual(
            datetime.datetime(
                2022,
                10,
                15,
                11,
                23,
                19,
                tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
            ),
            parser.date,
        )
        self.assertTrue(os.path.isfile(parser.archive_path))

        converted = os.path.join(parser.tempdir, "converted.webp")
        run_convert(
            density=300,
            scale="500x5000>",
            alpha="remove",
            strip=True,
            trim=False,
            auto_orient=True,
            input_file=f"{parser.archive_path}",  # Do net define an index to convert all pages.
            output_file=converted,
            logging_group=None,
        )
        self.assertTrue(os.path.isfile(converted))
        thumb_hash = self.hashfile(converted)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = (
            "174f9c81f9aeda63b64375fa2fe675fd542677c1ba7a32fc19e09ffc4d461e12"
        )
        self.assertEqual(
            thumb_hash,
            expected_hash,
            "PDF looks different.",
        )

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_tika_parse(self, m):
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'
        expected_text = "\n\n\n\n\n\n\n\n\nSome Text\n"

        parser = MailDocumentParser(None)
        tika_server_original = parser.tika_server

        # Check if exception is raised when Tika cannot be reached.
        with pytest.raises(ParseError):
            parser.tika_server = ""
            parser.tika_parse(html)

        # Check unsuccessful parsing
        parser.tika_server = tika_server_original

        parsed = parser.tika_parse(None)
        self.assertEqual("", parsed)

        # Check successful parsing
        parsed = parser.tika_parse(html)
        self.assertEqual(expected_text, parsed)

    def test_transform_inline_html(self):
        class MailAttachmentMock:
            def __init__(self, payload, content_id):
                self.payload = payload
                self.content_id = content_id

        parser = MailDocumentParser(None)

        result = None

        with open(os.path.join(self.SAMPLE_FILES, "sample.html")) as html_file:
            with open(os.path.join(self.SAMPLE_FILES, "sample.png"), "rb") as png_file:
                html = html_file.read()
                png = png_file.read()
                attachments = [
                    MailAttachmentMock(png, "part1.pNdUSz0s.D3NqVtPg@example.de"),
                ]
                result = parser.transform_inline_html(html, attachments)

        resulting_html = result[-1][1].read()
        self.assertTrue(result[-1][0] == "index.html")
        self.assertTrue(result[0][0] in resulting_html)
        self.assertFalse("<script" in resulting_html.lower())

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_generate_pdf_from_html(self, m):
        class MailAttachmentMock:
            def __init__(self, payload, content_id):
                self.payload = payload
                self.content_id = content_id

        parser = MailDocumentParser(None)

        result = None

        with open(os.path.join(self.SAMPLE_FILES, "sample.html")) as html_file:
            with open(os.path.join(self.SAMPLE_FILES, "sample.png"), "rb") as png_file:
                html = html_file.read()
                png = png_file.read()
                attachments = [
                    MailAttachmentMock(png, "part1.pNdUSz0s.D3NqVtPg@example.de"),
                ]
                result = parser.generate_pdf_from_html(html, attachments)

        pdf_path = os.path.join(parser.tempdir, "test_generate_pdf_from_html.pdf")

        with open(pdf_path, "wb") as file:
            file.write(result)
            file.close()

        converted = os.path.join(parser.tempdir, "test_generate_pdf_from_html.webp")
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
        thumb_hash = self.hashfile(converted)

        # The created pdf is not reproducible. But the converted image should always look the same.
        expected_hash = (
            "88dee024ec77b1139b77913547717bd7e94f53651d489c54a7084d30a82e389e"
        )
        self.assertEqual(
            thumb_hash,
            expected_hash,
            "PDF looks different.",
        )
