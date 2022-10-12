import hashlib
import os

from django.test import TestCase
from paperless_mail.parsers import MailDocumentParser


class TestParser(TestCase):
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")

    def test_thumbnail(self):
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
