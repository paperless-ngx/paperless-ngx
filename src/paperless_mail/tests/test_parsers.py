import datetime
import hashlib
import os
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from django.test import TestCase
from documents.parsers import ParseError
from paperless_mail.parsers import MailDocumentParser
from pdfminer.high_level import extract_text


class TestParser(TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_get_parsed(self):
        parser = MailDocumentParser(None)

        # Check if exception is raised when parsing fails.
        with pytest.raises(ParseError):
            parser.get_parsed(os.path.join(self.SAMPLE_FILES, "na"))

        # Check if exception is raised when the mail is faulty.
        with pytest.raises(ParseError):
            parser.get_parsed(os.path.join(self.SAMPLE_FILES, "broken.eml"))

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

    @mock.patch("paperless_mail.parsers.make_thumbnail_from_pdf")
    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_get_thumbnail(self, m, mock_make_thumbnail_from_pdf: mock.MagicMock):
        parser = MailDocumentParser(None)
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        self.assertEqual(
            parser.archive_path,
            mock_make_thumbnail_from_pdf.call_args_list[0].args[0],
        )
        self.assertEqual(
            parser.tempdir,
            mock_make_thumbnail_from_pdf.call_args_list[0].args[1],
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

        text_expected = "Some Text\nand an embedded image.\n\nSubject: HTML Message\n\nFrom: Name <someone@example.de>\n\nTo: someone@example.de\n\nAttachments: IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbfile.txt (0.59 MiB)\n\nHTML content: Some Text\nand an embedded image.\nParagraph unchanged."
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

        # Validate parsing returns the expected results
        parser = MailDocumentParser(None)
        parser.parse(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        text_expected = "This is just a simple Text Mail.\n\nSubject: Simple Text Mail\n\nFrom: Some One <mail@someserver.de>\n\nTo: some@one.de\n\nCC: asdasd@æsdasd.de, asdadasdasdasda.asdasd@æsdasd.de\n\nBCC: fdf@fvf.de\n\n"
        self.assertEqual(text_expected, parser.text)
        self.assertEqual(
            datetime.datetime(
                2022,
                10,
                12,
                21,
                40,
                43,
                tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
            ),
            parser.date,
        )

        # Just check if file exists, the unittest for generate_pdf() goes deeper.
        self.assertTrue(os.path.isfile(parser.archive_path))

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

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf_parse_error(self, m: mock.MagicMock, n: mock.MagicMock):
        m.return_value = b""
        n.return_value = b""
        parser = MailDocumentParser(None)

        # Check if exception is raised when the pdf can not be created.
        parser.gotenberg_server = ""
        with pytest.raises(ParseError):
            parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_generate_pdf(self, m):
        parser = MailDocumentParser(None)

        # Check if exception is raised when the mail can not be parsed.
        with pytest.raises(ParseError):
            parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "broken.eml"))

        pdf_path = parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))
        self.assertTrue(os.path.isfile(pdf_path))

        extracted = extract_text(pdf_path)
        expected = "From Name <someone@example.de>\n\n2022-10-15 09:23\n\nSubject HTML Message\n\nTo someone@example.de\n\nAttachments IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbﬁle.txt (0.59 MiB)\n\nSome Text \n\nand an embedded image.\n\n\x0cSome Text\n\n  This image should not be shown.\n\nand an embedded image.\n\nParagraph unchanged.\n\n\x0c"
        self.assertEqual(expected, extracted)

    def test_mail_to_html(self):
        parser = MailDocumentParser(None)
        mail = parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))
        html_handle = parser.mail_to_html(mail)

        with open(
            os.path.join(self.SAMPLE_FILES, "html.eml.html"),
        ) as html_expected_handle:
            self.assertHTMLEqual(html_expected_handle.read(), html_handle.read())

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_generate_pdf_from_mail(self, m):
        parser = MailDocumentParser(None)
        mail = parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))

        pdf_path = os.path.join(parser.tempdir, "test_generate_pdf_from_mail.pdf")

        with open(pdf_path, "wb") as file:
            file.write(parser.generate_pdf_from_mail(mail))
            file.close()

        extracted = extract_text(pdf_path)
        expected = "From Name <someone@example.de>\n\n2022-10-15 09:23\n\nSubject HTML Message\n\nTo someone@example.de\n\nAttachments IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbﬁle.txt (0.59 MiB)\n\nSome Text \n\nand an embedded image.\n\n\x0c"
        self.assertEqual(expected, extracted)

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

        extracted = extract_text(pdf_path)
        expected = "Some Text\n\n  This image should not be shown.\n\nand an embedded image.\n\nParagraph unchanged.\n\n\x0c"
        self.assertEqual(expected, extracted)

    def test_is_online_image_still_available(self):
        """
        A public image is used in the html sample file. We have no control
        whether this image stays online forever, so here we check if it is still there
        """

        # Start by Testing if nonexistent URL really throws an Exception
        with pytest.raises(HTTPError):
            urlopen("https://upload.wikimedia.org/wikipedia/en/f/f7/nonexistent.png")

        # Now check the URL used in samples/sample.html
        urlopen("https://upload.wikimedia.org/wikipedia/en/f/f7/RickRoll.png")
