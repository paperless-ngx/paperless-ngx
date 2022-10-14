import hashlib
import os
from unittest import mock

import pytest
from django.test import TestCase
from documents.parsers import ParseError
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

    def test_get_thumbnail(self):
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

        parser = MailDocumentParser(None)
        thumb = parser.get_thumbnail(
            os.path.join(self.SAMPLE_FILES, "simple_text.eml"),
            "message/rfc822",
        )
        self.assertTrue(os.path.isfile(thumb))
        thumb_hash = hashfile(thumb)

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
