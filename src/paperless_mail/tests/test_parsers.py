import datetime
import os
from unittest import mock

from django.test import TestCase
from documents.parsers import ParseError
from documents.tests.utils import FileSystemAssertsMixin
from paperless_mail.parsers import MailDocumentParser


class TestParser(FileSystemAssertsMixin, TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def setUp(self) -> None:
        self.parser = MailDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        self.parser.cleanup()

    def test_get_parsed_missing_file(self):
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A nonexistent file should be parsed
        THEN:
            - An Exception is thrown
        """
        # Check if exception is raised when parsing fails.
        self.assertRaises(
            ParseError,
            self.parser.get_parsed,
            os.path.join(self.SAMPLE_FILES, "na"),
        )

    def test_get_parsed_broken_file(self):
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A faulty file should be parsed
        THEN:
            - An Exception is thrown
        """
        # Check if exception is raised when the mail is faulty.
        self.assertRaises(
            ParseError,
            self.parser.get_parsed,
            os.path.join(self.SAMPLE_FILES, "broken.eml"),
        )

    def test_get_parsed_simple_text_mail(self):
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A .eml file should be parsed
        THEN:
            - The content of the mail should be available in the parse result.
        """
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

    def test_get_parsed_reparse(self):
        """
        GIVEN:
            - An E-Mail was parsed
        WHEN:
            - Another .eml file should be parsed
        THEN:
            - The parser should not retry to parse and return the old results
        """
        # Parse Test file and check relevant content
        parsed1 = self.parser.get_parsed(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
        )
        # Check if same parsed object as before is returned, even if another file is given.
        parsed2 = self.parser.get_parsed(
            os.path.join(os.path.join(self.SAMPLE_FILES, "html.eml")),
        )
        self.assertEqual(parsed1, parsed2)

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    @mock.patch("paperless_mail.parsers.make_thumbnail_from_pdf")
    def test_get_thumbnail(
        self,
        mock_make_thumbnail_from_pdf: mock.MagicMock,
        mock_generate_pdf: mock.MagicMock,
    ):
        """
        GIVEN:
            - An E-Mail was parsed
        WHEN:
            - The Thumbnail is requested
        THEN:
            - The parser should call the functions which generate the thumbnail
        """
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
    def test_extract_metadata_fail(self, m: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - Metadata extraction is triggered for nonexistent file
        THEN:
            - A log warning should be generated
        """
        # Validate if warning is logged when parsing fails
        self.assertEqual([], self.parser.extract_metadata("na", "message/rfc822"))
        self.assertEqual("warning", m.call_args[0][0])

    def test_extract_metadata(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - Metadata extraction is triggered
        THEN:
            - metadata is returned
        """
        # Validate Metadata parsing returns the expected results
        metadata = self.parser.extract_metadata(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )

        self.assertIn(
            {"namespace": "", "prefix": "", "key": "attachments", "value": ""},
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "",
                "key": "date",
                "value": "2022-10-12 21:40:43 UTC+02:00",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "content-language",
                "value": "en-US",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "content-type",
                "value": "text/plain; charset=UTF-8; format=flowed",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "date",
                "value": "Wed, 12 Oct 2022 21:40:43 +0200",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "delivered-to",
                "value": "mail@someserver.de",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "from",
                "value": "Some One <mail@someserver.de>",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "message-id",
                "value": "<6e99e34d-e20a-80c4-ea61-d8234b612be9@someserver.de>",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "mime-version",
                "value": "1.0",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "received",
                "value": "from mail.someserver.org ([::1])\n\tby e1acdba3bd07 with LMTP\n\tid KBKZGD2YR2NTCgQAjubtDA\n\t(envelope-from <mail@someserver.de>)\n\tfor <mail@someserver.de>; Wed, 10 Oct 2022 11:40:46 +0200, from [127.0.0.1] (localhost [127.0.0.1]) by localhost (Mailerdaemon) with ESMTPSA id 2BC9064C1616\n\tfor <some@one.de>; Wed, 12 Oct 2022 21:40:46 +0200 (CEST)",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "return-path",
                "value": "<mail@someserver.de>",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "subject",
                "value": "Simple Text Mail",
            },
            metadata,
        )
        self.assertIn(
            {"namespace": "", "prefix": "header", "key": "to", "value": "some@one.de"},
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "user-agent",
                "value": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101\n Thunderbird/102.3.1",
            },
            metadata,
        )
        self.assertIn(
            {
                "namespace": "",
                "prefix": "header",
                "key": "x-last-tls-session-version",
                "value": "TLSv1.3",
            },
            metadata,
        )

    def test_parse_na(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is attempted with nonexistent file
        THEN:
            - Exception is thrown
        """
        # Check if exception is raised when parsing fails.
        self.assertRaises(
            ParseError,
            self.parser.parse,
            os.path.join(self.SAMPLE_FILES, "na"),
            "message/rfc822",
        )

    @mock.patch("paperless_mail.parsers.MailDocumentParser.tika_parse")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    def test_parse_html_eml(self, n, mock_tika_parse: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is done with html mail
        THEN:
            - Tika is called, parsed information from non html parts is available
        """
        # Validate parsing returns the expected results
        text_expected = "Subject: HTML Message\n\nFrom: Name <someone@example.de>\n\nTo: someone@example.de\n\nAttachments: IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbfile.txt (600.24 KiB)\n\nHTML content: tika return\n\nSome Text and an embedded image."
        mock_tika_parse.return_value = "tika return"

        self.parser.parse(os.path.join(self.SAMPLE_FILES, "html.eml"), "message/rfc822")

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
    def test_parse_simple_eml(self, m: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is done with non html mail
        THEN:
            - parsed information is available
        """
        # Validate parsing returns the expected results

        self.parser.parse(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        text_expected = "Subject: Simple Text Mail\n\nFrom: Some One <mail@someserver.de>\n\nTo: some@one.de\n\nCC: asdasd@æsdasd.de, asdadasdasdasda.asdasd@æsdasd.de\n\nBCC: fdf@fvf.de\n\n\n\nThis is just a simple Text Mail."
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

        # Just check if tried to generate archive, the unittest for generate_pdf() goes deeper.
        m.assert_called()

    @mock.patch("paperless_mail.parsers.parser.from_buffer")
    def test_tika_parse_unsuccessful(self, mock_from_buffer: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing fails
        THEN:
            - the parser should return an empty string
        """
        # Check unsuccessful parsing
        mock_from_buffer.return_value = {"content": None}
        parsed = self.parser.tika_parse(None)
        self.assertEqual("", parsed)

    @mock.patch("paperless_mail.parsers.parser.from_buffer")
    def test_tika_parse(self, mock_from_buffer: mock.MagicMock):
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
        mock_from_buffer.return_value = {"content": expected_text}
        parsed = self.parser.tika_parse(html)
        self.assertEqual(expected_text, parsed.strip())
        mock_from_buffer.assert_called_with(html, self.parser.tika_server)

    @mock.patch("paperless_mail.parsers.parser.from_buffer")
    def test_tika_parse_exception(self, mock_from_buffer: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called and an exception is thrown on the request
        THEN:
            - a ParseError Exception is thrown
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'

        # Check ParseError
        def my_side_effect():
            raise Exception("Test")

        mock_from_buffer.side_effect = my_side_effect
        self.assertRaises(ParseError, self.parser.tika_parse, html)

    def test_tika_parse_unreachable(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called but tika is not available
        THEN:
            - a ParseError Exception is thrown
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'

        # Check if exception is raised when Tika cannot be reached.
        self.parser.tika_server = ""
        self.assertRaises(ParseError, self.parser.tika_parse, html)

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf_parse_error(self, m: mock.MagicMock, n: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation is requested but gotenberg can not be reached
        THEN:
            - a ParseError Exception is thrown
        """
        m.return_value = b""
        n.return_value = b""

        # Check if exception is raised when the pdf can not be created.
        self.parser.gotenberg_server = ""
        self.assertRaises(
            ParseError,
            self.parser.generate_pdf,
            os.path.join(self.SAMPLE_FILES, "html.eml"),
        )

    def test_generate_pdf_exception(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation is requested but parsing throws an exception
        THEN:
            - a ParseError Exception is thrown
        """
        # Check if exception is raised when the mail can not be parsed.
        self.assertRaises(
            ParseError,
            self.parser.generate_pdf,
            os.path.join(self.SAMPLE_FILES, "broken.eml"),
        )

    @mock.patch("paperless_mail.parsers.requests.post")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_mail")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf_from_html")
    def test_generate_pdf(
        self,
        mock_generate_pdf_from_html: mock.MagicMock,
        mock_generate_pdf_from_mail: mock.MagicMock,
        mock_post: mock.MagicMock,
    ):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation is requested
        THEN:
            - gotenberg is called and the resulting file is returned
        """
        mock_generate_pdf_from_mail.return_value = b"Mail Return"
        mock_generate_pdf_from_html.return_value = b"HTML Return"

        mock_response = mock.MagicMock()
        mock_response.content = b"Content"
        mock_post.return_value = mock_response
        pdf_path = self.parser.generate_pdf(os.path.join(self.SAMPLE_FILES, "html.eml"))
        self.assertIsFile(pdf_path)

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
        """
        GIVEN:
            - Fresh start
        WHEN:
            - conversion from eml to html is requested
        THEN:
            - html should be returned
        """
        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))
        html_handle = self.parser.mail_to_html(mail)
        html_received = html_handle.read()

        with open(
            os.path.join(self.SAMPLE_FILES, "html.eml.html"),
        ) as html_expected_handle:
            html_expected = html_expected_handle.read()

            self.assertHTMLEqual(html_expected, html_received)

    @mock.patch("paperless_mail.parsers.requests.post")
    @mock.patch("paperless_mail.parsers.MailDocumentParser.mail_to_html")
    def test_generate_pdf_from_mail(
        self,
        mock_mail_to_html: mock.MagicMock,
        mock_post: mock.MagicMock,
    ):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - conversion of PDF from .eml is requested
        THEN:
            - gotenberg should be called with valid intermediary html files, the resulting pdf is returned
        """
        mock_response = mock.MagicMock()
        mock_response.content = b"Content"
        mock_post.return_value = mock_response

        mock_mail_to_html.return_value = "Testresponse"

        mail = self.parser.get_parsed(os.path.join(self.SAMPLE_FILES, "html.eml"))

        retval = self.parser.generate_pdf_from_mail(mail)
        self.assertEqual(b"Content", retval)

        mock_mail_to_html.assert_called_once_with(mail)
        self.assertEqual(
            self.parser.gotenberg_server + "/forms/chromium/convert/html",
            mock_post.call_args.args[0],
        )
        self.assertDictEqual({}, mock_post.call_args.kwargs["headers"])
        self.assertDictEqual(
            {
                "marginTop": "0.1",
                "marginBottom": "0.1",
                "marginLeft": "0.1",
                "marginRight": "0.1",
                "paperWidth": "8.27",
                "paperHeight": "11.7",
                "scale": "1.0",
                "pdfFormat": "PDF/A-2b",
            },
            mock_post.call_args.kwargs["data"],
        )
        self.assertEqual(
            "Testresponse",
            mock_post.call_args.kwargs["files"]["html"][1],
        )
        self.assertEqual(
            "output.css",
            mock_post.call_args.kwargs["files"]["css"][0],
        )

        mock_response.raise_for_status.assert_called_once()

    def test_transform_inline_html(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - transforming of html content from an email with an inline image attachment is requested
        THEN:
            - html is returned and sanitized
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
                result = self.parser.transform_inline_html(html, attachments)

        resulting_html = result[-1][1].read()
        self.assertTrue(result[-1][0] == "index.html")
        self.assertIn(result[0][0], resulting_html)
        self.assertNotIn("<script", resulting_html.lower())

    @mock.patch("paperless_mail.parsers.requests.post")
    def test_generate_pdf_from_html(self, mock_post: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - generating pdf from html with inline attachments is attempted
        THEN:
            - gotenberg is called with the correct parameters and the resulting pdf is returned
        """

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
        self.assertDictEqual({}, mock_post.call_args.kwargs["headers"])
        self.assertDictEqual(
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
