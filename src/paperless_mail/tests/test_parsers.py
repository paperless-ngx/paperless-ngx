import datetime
from pathlib import Path
from unittest import mock

import httpx
from django.test import TestCase

from documents.parsers import ParseError
from documents.tests.utils import FileSystemAssertsMixin
from paperless_mail.parsers import MailDocumentParser
from paperless_tika.tests.utils import HttpxMockMixin


class BaseMailParserTestCase(TestCase):
    """
    Basic setup for the below test cases
    """

    SAMPLE_DIR = Path(__file__).parent / "samples"

    def setUp(self) -> None:
        super().setUp()
        self.parser = MailDocumentParser(logging_group=None)

    def tearDown(self) -> None:
        super().tearDown()
        self.parser.cleanup()


class TestEmailFileParsing(FileSystemAssertsMixin, BaseMailParserTestCase):
    """
    Tests around reading a file and parsing it into a
    MailMessage
    """

    def test_parse_error_missing_file(self):
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A nonexistent file should be parsed
        THEN:
            - An Exception is thrown
        """
        # Check if exception is raised when parsing fails.
        test_file = self.SAMPLE_DIR / "doesntexist.eml"

        self.assertIsNotFile(test_file)
        self.assertRaises(
            ParseError,
            self.parser.parse,
            test_file,
            "messages/rfc822",
        )

    def test_parse_error_invalid_email(self):
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
            self.parser.parse,
            self.SAMPLE_DIR / "broken.eml",
            "messages/rfc822",
        )

    def test_parse_simple_text_email_file(self):
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A .eml file should be parsed
        THEN:
            - The content of the mail should be available in the parse result.
        """
        # Parse Test file and check relevant content
        parsed1 = self.parser.parse_file_to_message(
            self.SAMPLE_DIR / "simple_text.eml",
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


class TestEmailMetadataExtraction(BaseMailParserTestCase):
    """
    Tests extraction of metadata from an email
    """

    def test_extract_metadata_fail(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - Metadata extraction is triggered for nonexistent file
        THEN:
            - A log warning should be generated
        """
        # Validate if warning is logged when parsing fails
        with self.assertLogs("paperless.parsing.mail", level="WARNING") as cm:
            self.assertEqual([], self.parser.extract_metadata("na", "message/rfc822"))
            self.assertIn(
                "WARNING:paperless.parsing.mail:Error while fetching document metadata for na",
                cm.output[0],
            )

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
            self.SAMPLE_DIR / "simple_text.eml",
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


class TestEmailThumbnailGenerate(BaseMailParserTestCase):
    """
    Tests the correct generation of an thumbnail for an email
    """

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

        test_file = self.SAMPLE_DIR / "simple_text.eml"

        thumb = self.parser.get_thumbnail(
            test_file,
            "message/rfc822",
        )

        mock_generate_pdf.assert_called_once()
        mock_make_thumbnail_from_pdf.assert_called_once_with(
            "Mocked return value..",
            self.parser.tempdir,
            None,
        )

        self.assertEqual(mocked_return, thumb)


class TestTikaHtmlParse(HttpxMockMixin, BaseMailParserTestCase):
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
        self.httpx_mock.add_response(
            json={"Content-Type": "text/html", "X-TIKA:Parsed-By": []},
        )
        parsed = self.parser.tika_parse("None")
        self.assertEqual("", parsed)

    def test_tika_parse(self):
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

        self.httpx_mock.add_response(
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": expected_text,
            },
        )
        parsed = self.parser.tika_parse(html)
        self.assertEqual(expected_text, parsed.strip())
        self.assertIn("http://localhost:9998", str(self.httpx_mock.get_request().url))

    def test_tika_parse_exception(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called and an exception is thrown on the request
        THEN:
            - a ParseError Exception is thrown
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'

        self.httpx_mock.add_response(status_code=httpx.codes.INTERNAL_SERVER_ERROR)

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


class TestParser(FileSystemAssertsMixin, HttpxMockMixin, BaseMailParserTestCase):
    def test_parse_no_file(self):
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
            self.SAMPLE_DIR / "na.eml",
            "message/rfc822",
        )

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    def test_parse_eml_simple(self, mock_generate_pdf: mock.MagicMock):
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
            self.SAMPLE_DIR / "simple_text.eml",
            "message/rfc822",
        )
        text_expected = (
            "Subject: Simple Text Mail\n\n"
            "From: Some One <mail@someserver.de>\n\n"
            "To: some@one.de\n\n"
            "CC: asdasd@æsdasd.de, asdadasdasdasda.asdasd@æsdasd.de\n\n"
            "BCC: fdf@fvf.de\n\n"
            "\n\nThis is just a simple Text Mail."
        )
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
        mock_generate_pdf.assert_called()

    @mock.patch("paperless_mail.parsers.MailDocumentParser.generate_pdf")
    def test_parse_eml_html(self, mock_generate_pdf: mock.MagicMock):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is done with html mail
        THEN:
            - Tika is called, parsed information from non html parts is available
        """
        # Validate parsing returns the expected results
        text_expected = (
            "Subject: HTML Message\n\n"
            "From: Name <someone@example.de>\n\n"
            "To: someone@example.de\n\n"
            "Attachments: IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbfile.txt (600.24 KiB)\n\n"
            "HTML content: tika return\n\n"
            "Some Text and an embedded image."
        )

        self.httpx_mock.add_response(
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "tika return",
            },
        )

        self.parser.parse(self.SAMPLE_DIR / "html.eml", "message/rfc822")

        mock_generate_pdf.assert_called_once()
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

    def test_generate_pdf_parse_error(self):
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation is requested but gotenberg fails
        THEN:
            - a ParseError Exception is thrown
        """
        self.httpx_mock.add_response(status_code=httpx.codes.INTERNAL_SERVER_ERROR)

        self.assertRaises(
            ParseError,
            self.parser.parse,
            self.SAMPLE_DIR / "simple_text.eml",
            "message/rfc822",
        )

    def test_generate_pdf_simple_email(self):
        """
        GIVEN:
            - Simple text email with no HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is called to generate a PDF from HTML
            - Archive file is generated
        """

        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=(self.SAMPLE_DIR / "simple_text.eml.pdf").read_bytes(),
        )

        self.parser.parse(self.SAMPLE_DIR / "simple_text.eml", "message/rfc822")

        self.assertIsNotNone(self.parser.archive_path)

    def test_generate_pdf_html_email(self):
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is called to generate a PDF from HTML
            - Gotenberg is used to merge the two PDFs
            - Archive file is generated
        """
        self.httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=(self.SAMPLE_DIR / "html.eml.pdf").read_bytes(),
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            content=b"Pretend merged PDF content",
        )
        self.parser.parse(self.SAMPLE_DIR / "html.eml", "message/rfc822")

        self.assertIsNotNone(self.parser.archive_path)

    def test_generate_pdf_html_email_html_to_pdf_failure(self):
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
            - Conversion of email HTML content to PDF fails
        THEN:
            - ParseError is raised
        """
        self.httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=(self.SAMPLE_DIR / "html.eml.pdf").read_bytes(),
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            status_code=httpx.codes.INTERNAL_SERVER_ERROR,
        )
        with self.assertRaises(ParseError):
            self.parser.parse(self.SAMPLE_DIR / "html.eml", "message/rfc822")

    def test_generate_pdf_html_email_merge_failure(self):
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
            - Merging of PDFs fails
        THEN:
            - ParseError is raised
        """
        self.httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=(self.SAMPLE_DIR / "html.eml.pdf").read_bytes(),
        )
        self.httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            status_code=httpx.codes.INTERNAL_SERVER_ERROR,
        )
        with self.assertRaises(ParseError):
            self.parser.parse(self.SAMPLE_DIR / "html.eml", "message/rfc822")

    def test_mail_to_html(self):
        """
        GIVEN:
            - Email message with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Resulting HTML is as expected
        """
        mail = self.parser.parse_file_to_message(self.SAMPLE_DIR / "html.eml")
        html_file = self.parser.mail_to_html(mail)
        expected_html_file = self.SAMPLE_DIR / "html.eml.html"

        self.assertHTMLEqual(expected_html_file.read_text(), html_file.read_text())

    def test_generate_pdf_from_mail(
        self,
    ):
        """
        GIVEN:
            - Email message with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is used to convert HTML to PDF
        """

        self.httpx_mock.add_response(content=b"Content")

        mail = self.parser.parse_file_to_message(self.SAMPLE_DIR / "html.eml")

        retval = self.parser.generate_pdf_from_mail(mail)
        self.assertEqual(b"Content", retval.read_bytes())

        request = self.httpx_mock.get_request()

        self.assertEqual(
            str(request.url),
            "http://localhost:3000/forms/chromium/convert/html",
        )
