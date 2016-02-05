import os
import magic

from hashlib import md5

from django.conf import settings
from django.test import TestCase

from ...consumers.mail import MailConsumer


class TestMailConsumer(TestCase):

    def __init__(self, *args, **kwargs):

        TestCase.__init__(self, *args, **kwargs)
        self.sample = os.path.join(
            settings.BASE_DIR,
            "documents",
            "tests",
            "consumers",
            "samples",
            "mail.txt"
        )

    def test_parse(self):
        consumer = MailConsumer()
        with open(self.sample) as f:

            messages = consumer._parse_message(f.read())

            self.assertTrue(len(messages), 1)
            self.assertEqual(messages[0]["subject"], "Test 0")

            attachment = messages[0]["attachment"]
            data = attachment.read()

            self.assertEqual(
                md5(data).hexdigest(), "7c89655f9e9eb7dd8cde8568e8115d59")

            self.assertEqual(attachment.content_type, "application/pdf")
            with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
                self.assertEqual(m.id_buffer(data), "application/pdf")
