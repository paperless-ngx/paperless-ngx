import hashlib
import json
import os
import shutil
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from documents.management.commands import document_exporter
from documents.models import Document, Tag, DocumentType, Correspondent


class TestDecryptDocuments(TestCase):

    @override_settings(
        ORIGINALS_DIR=os.path.join(os.path.dirname(__file__), "samples", "originals"),
        THUMBNAIL_DIR=os.path.join(os.path.dirname(__file__), "samples", "thumb"),
        PASSPHRASE="test",
        PAPERLESS_FILENAME_FORMAT=None
    )
    @mock.patch("documents.management.commands.decrypt_documents.input")
    def test_decrypt(self, m):

        media_dir = tempfile.mkdtemp()
        originals_dir = os.path.join(media_dir, "documents", "originals")
        thumb_dir = os.path.join(media_dir, "documents", "thumbnails")
        os.makedirs(originals_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)

        override_settings(
            ORIGINALS_DIR=originals_dir,
            THUMBNAIL_DIR=thumb_dir,
            PASSPHRASE="test"
        ).enable()

        doc = Document.objects.create(checksum="9c9691e51741c1f4f41a20896af31770", title="wow", filename="0000002.pdf.gpg",  mime_type="application/pdf", storage_type=Document.STORAGE_TYPE_GPG)

        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "originals", "0000002.pdf.gpg"), os.path.join(originals_dir, "0000002.pdf.gpg"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "thumbnails", f"0000002.png.gpg"), os.path.join(thumb_dir, f"{doc.id:07}.png.gpg"))

        call_command('decrypt_documents')

        doc.refresh_from_db()

        self.assertEqual(doc.storage_type, Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(doc.filename, "0000002.pdf")
        self.assertTrue(os.path.isfile(os.path.join(originals_dir, "0000002.pdf")))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(os.path.join(thumb_dir, f"{doc.id:07}.png")))
        self.assertTrue(os.path.isfile(doc.thumbnail_path))

        with doc.source_file as f:
            checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(checksum, doc.checksum)

