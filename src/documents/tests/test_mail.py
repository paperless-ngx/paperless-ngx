import base64
import os
import magic

from hashlib import md5
from unittest import mock

from django.conf import settings
from django.test import TestCase

from ..mail import Message, Attachment


class TestMessage(TestCase):

    def __init__(self, *args, **kwargs):

        TestCase.__init__(self, *args, **kwargs)
        self.sample = os.path.join(
            settings.BASE_DIR,
            "documents",
            "tests",
            "samples",
            "mail.txt"
        )

    def test_init(self):

        with open(self.sample, "rb") as f:

            with mock.patch("logging.StreamHandler.emit") as __:
                message = Message(f.read())

            self.assertTrue(message)
            self.assertEqual(message.subject, "Test 0")

            data = message.attachment.read()

            self.assertEqual(
                md5(data).hexdigest(), "7c89655f9e9eb7dd8cde8568e8115d59")

            self.assertEqual(
                message.attachment.content_type, "application/pdf")
            with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
                self.assertEqual(m.id_buffer(data), "application/pdf")


class TestInlineMessage(TestCase):

    def __init__(self, *args, **kwargs):

        TestCase.__init__(self, *args, **kwargs)
        self.sample = os.path.join(
            settings.BASE_DIR,
            "documents",
            "tests",
            "samples",
            "inline_mail.txt"
        )

    def test_init(self):

        with open(self.sample, "rb") as f:

            with mock.patch("logging.StreamHandler.emit") as __:
                message = Message(f.read())

            self.assertTrue(message)
            self.assertEqual(message.subject, "Paperless Inline Image")

            data = message.attachment.read()

            self.assertEqual(
                md5(data).hexdigest(), "30c00a7b42913e65f7fdb0be40b9eef3")

            self.assertEqual(
                message.attachment.content_type, "image/png")
            with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
                self.assertEqual(m.id_buffer(data), "image/png")


class TestAttachment(TestCase):

    def test_init(self):
        data = base64.encodebytes(b"0")
        self.assertEqual(Attachment(data, "application/pdf").suffix, "pdf")
        self.assertEqual(Attachment(data, "image/png").suffix, "png")
        self.assertEqual(Attachment(data, "image/jpeg").suffix, "jpeg")
        self.assertEqual(Attachment(data, "image/gif").suffix, "gif")
        self.assertEqual(Attachment(data, "image/tiff").suffix, "tiff")
        self.assertEqual(Attachment(data, "image/png").read(), data)
