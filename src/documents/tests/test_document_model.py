import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from ..models import Document, Correspondent


class TestDocument(TestCase):

    def setUp(self) -> None:
        self.originals_dir = tempfile.mkdtemp()
        self.thumb_dir = tempfile.mkdtemp()

        override_settings(
            ORIGINALS_DIR=self.originals_dir,
            THUMBNAIL_DIR=self.thumb_dir,
        ).enable()

    def tearDown(self) -> None:
        shutil.rmtree(self.originals_dir)
        shutil.rmtree(self.thumb_dir)

    def test_file_deletion(self):
        document = Document.objects.create(
            correspondent=Correspondent.objects.create(name="Test0"),
            title="Title",
            content="content",
            checksum="checksum",
            mime_type="application/pdf"
        )

        file_path = document.source_path
        thumb_path = document.thumbnail_path

        Path(file_path).touch()
        Path(thumb_path).touch()

        with mock.patch("documents.signals.handlers.os.unlink") as mock_unlink:
            document.delete()
            mock_unlink.assert_any_call(file_path)
            mock_unlink.assert_any_call(thumb_path)
            self.assertEqual(mock_unlink.call_count, 2)
