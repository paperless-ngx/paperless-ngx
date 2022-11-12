import datetime
import os
from unittest import mock

import pytest
from django.test import TestCase
from documents.parsers import ParseError
from paperless_mail.parsers import MailDocumentParser
from pdfminer.high_level import extract_text


class TestParser(TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def setUp(self) -> None:
        self.parser = MailDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    def test_get_parsed(self):
        # Check if exception is raised when parsing fails.
        with pytest.raises(ParseError):
            self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "na"))

        # Check if exception is raised when the mail is faulty.
        with pytest.raises(ParseError):
            self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "broken.eml"))

        # Parse Test file and check relevant content
        parsed1 = self.parser.get_parsed(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
        )

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
        parsed2 = self.parser.get_parsed(
            os.path.join(os.path.join(self.SAMPLE_FILES, "na")),
        )
        self.assertEqual(parsed1, parsed2)

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    @mock.patch("paperless_mail.parsers.make_thumbnail_from_pdf")
    def test_get_thumbnail(
        self,
        mock_make_thumbnail_from_pdf: mock.MagicMock,
        mock_generate_pdf: mock.MagicMock,
    ):
        mocked_return = "Passing the return value through.."
        mock_make_thumbnail_from_pdf.return_value = mocked_return

        mock_generate_pdf.return_value = "Mocked return value.."

        thumb = self.parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        self.assertEqual(
            self.parser.archive_path,
            mock_make_thumbnail_from_pdf.call_args_list[0].args[0],
        )
        self.assertEqual(
            self.parser.tempdir,
            mock_make_thumbnail_from_pdf.call_args_list[0].args[1],
        )
        self.assertEqual(mocked_return, thumb)

    @mock.patch("documents.loggers.LoggingMixin.log")
    def test_extract_metadata(self, m: mock.MagicMock):
        # Validate if warning is logged when parsing fails
        self.assertEqual([], self.parser.extract_metadata("na", "message/rfc822"))
        self.assertEqual("warning", m.call_args[0][0])

        # Validate Metadata parsing returns the expected results
        metadata = self.parser.extract_metadata(
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

    def test_parse_na(self):
        # Check if exception is raised when parsing fails.
        with pytest.raises(ParseError):
            self.parser.parse(
                os.path.join(os.path.join(self.SAMPLE_FILES, "na")),
                "message/rfc822",
            )

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_parse_html_eml(self, m, n):
        # Validate parsing returns the expected results
        self.parser.parse(os.path.join(self.SAMPLE_FILES, "html.eml"), "message/rfc822")

        text_expected = "Some Text\nand an embedded image.\n\nSubject: HTML Message\n\nFrom: Name <someone@example.de>\n\nTo: someone@example.de\n\nAttachments: IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbfile.txt (0.59 MiB)\n\nHTML content: Some Text\nand an embedded image.\nParagraph unchanged."
        self.assertEqual(text_expected, self.parser.text)
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
            self.parser.date,
        )

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_parse_simple_eml(self, m, n):
        # Validate parsing returns the expected results

        self.parser.parse(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        text_expected = "This is just a simple Text Mail.\n\nSubject: Simple Text Mail\n\nFrom: Some One <mail@someserver.de>\n\nTo: some@one.de\n\nCC: asdasd@æsdasd.de, asdadasdasdasda.asdasd@æsdasd.de\n\nBCC: fdf@fvf.de\n\n"
        self.assertEqual(text_expected, self.parser.text)
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
            self.parser.date,
        )

        # Just check if file exists, the unittest for generate_pdf() goes deeper.
        self.assertTrue(os.path.isfile(self.parser.archive_path))

    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_tika_parse(self, m):
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'
        expected_text = "Some Text"

        tika_server_original = self.parser.tika_server

        # Check if exception is raised when Tika cannot be reached.
        with pytest.raises(ParseError):
            self.parser.tika_server = ""
            self.parser.tika_parse(html)

        # Check unsuccessful parsing
        self.parser.tika_server = tika_server_original

        parsed = self.parser.tika_parse(None)
        self.assertEqual("", parsed)

        # Check successful parsing
        parsed = self.parser.tika_parse(html)
        self.assertEqual(expected_text, parsed.strip())

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf_parse_error(self, m: mock.MagicMock, n: mock.MagicMock):
        m.return_value = b""
        n.return_value = b""

        # Check if exception is raised when the pdf can not be created.
        self.parser.gotenberg_server = ""
        with pytest.raises(ParseError):
            self.parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))

    @mock.patch("paperless_mail.parsers.requests.post")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf(
        self,
        mock_generate_pdf_from_html: mock.MagicMock,
        mock_generate_pdf_from_mail: mock.MagicMock,
        mock_post: mock.MagicMock,
    ):
        # Check if exception is raised when the mail can not be parsed.
        with pytest.raises(ParseError):
            self.parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "broken.eml"))

        mock_generate_pdf_from_mail.return_value = b"Mail Return"
        mock_generate_pdf_from_html.return_value = b"HTML Return"

        mock_response = mock.MagicMock()
        mock_response.content = b"Content"
        mock_post.return_value = mock_response
        pdf_path = self.parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))
        self.assertTrue(os.path.isfile(pdf_path))

        mock_generate_pdf_from_mail.assert_called_once_with(
            self.parser.get_parsed(None),
        )
        mock_generate_pdf_from_html.assert_called_once_with(
            self.parser.get_parsed(None).html,
            self.parser.get_parsed(None).attachments,
        )
        self.assertEqual(
            self.parser.gotenberg_server + "/forms/pdfengines/merge",
            mock_post.call_args.args[0],
        )
        self.assertEqual({}, mock_post.call_args.kwargs["headers"])
        self.assertEqual(
            b"Mail Return",
            mock_post.call_args.kwargs["files"]["1_mail.pdf"][1].read(),
        )
        self.assertEqual(
            b"HTML Return",
            mock_post.call_args.kwargs["files"]["2_html.pdf"][1].read(),
        )

        mock_response.raise_for_status.assert_called_once()

        with open(pdf_path, "rb") as file:
            self.assertEqual(b"Content", file.read())

    def test_mail_to_html(self):
        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))
        html_handle = self.parser.mail_to_html(mail)

        with open(
            os.path.join(self.SAMPLE_FILES, "html.eml.html"),
        ) as html_expected_handle:
            self.assertHTMLEqual(html_expected_handle.read(), html_handle.read())

    @mock.patch("paperless_mail.parsers.requests.post")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.mail_to_html")
    def test_generate_pdf_from_mail(
        self,
        mock_mail_to_html: mock.MagicMock,
        mock_post: mock.MagicMock,
    ):
        mock_response = mock.MagicMock()
        mock_response.content = b"Content"
        mock_post.return_value = mock_response

        mock_mail_to_html.return_value = "Testresponse"

        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))

        retval = self.parser.generate_pdf_from_mail(mail)
        self.assertEqual(b"Content", retval)

        mock_generate_pdf_from_mail.assert_called_once_with(
            self.parser.get_parsed(None),
        )
        mock_generate_pdf_from_html.assert_called_once_with(
            self.parser.get_parsed(None).html,
            self.parser.get_parsed(None).attachments,
        )
        self.assertEqual(
            self.parser.gotenberg_server + "/forms/pdfengines/merge",
            mock_post.call_args.args[0],
        )
        self.assertEqual({}, mock_post.call_args.kwargs["headers"])
        self.assertEqual(
            b"Mail Return",
            mock_post.call_args.kwargs["files"]["1_mail.pdf"][1].read(),
        )
        self.assertEqual(
            b"HTML Return",
            mock_post.call_args.kwargs["files"]["2_html.pdf"][1].read(),
        )

        mock_response.raise_for_status.assert_called_once()

    def test_transform_inline_html(self):
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
                result = self.parser.transform_inline_html(html, attachments)

        resulting_html = result[-1][1].read()
        self.assertTrue(result[-1][0] == "index.html")
        self.assertTrue(result[0][0] in resulting_html)
        self.assertFalse("<script" in resulting_html.lower())

    @mock.patch("paperless_mail.parsers.requests.post")
    @mock.patch("documents.loggers.LoggingMixin.log")  # Disable log output
    def test_generate_pdf_from_html(self, m, mock_post: mock.MagicMock):
        class MailAttachmentMock:
            def __init__(self, payload, content_id):
                self.payload = payload
                self.content_id = content_id

        mock_response = mock.MagicMock()
        mock_response.content = b"Content"
        mock_post.return_value = mock_response

        result = None

        with open(os.path.join(self.SAMPLE_FILES, "sample.html")) as html_file:
            with open(os.path.join(self.SAMPLE_FILES, "sample.png"), "rb") as png_file:
                html = html_file.read()
                png = png_file.read()
                attachments = [
                    MailAttachmentMock(png, "part1.pNdUSz0s.D3NqVtPg@example.de"),
                ]
                result = self.parser.generate_pdf_from_html(html, attachments)

        self.assertEqual(
            self.parser.gotenberg_server + "/forms/chromium/convert/html",
            mock_post.call_args.args[0],
        )
        self.assertEqual({}, mock_post.call_args.kwargs["headers"])
        self.assertEqual(
            {
                "marginTop": "0.1",
                "marginBottom": "0.1",
                "marginLeft": "0.1",
                "marginRight": "0.1",
                "paperWidth": "8.27",
                "paperHeight": "11.7",
                "scale": "1.0",
            },
            mock_post.call_args.kwargs["data"],
        )

        # read to assert it is a file like object.
        mock_post.call_args.kwargs["files"]["cidpart1pNdUSz0sD3NqVtPgexamplede"][
            1
        ].read()
        mock_post.call_args.kwargs["files"]["index.html"][1].read()

        mock_response.raise_for_status.assert_called_once()

        self.assertEqual(b"Content", result)
