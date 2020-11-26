import hashlib
import json
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from documents.management.commands import document_exporter
from documents.models import Document, Tag, DocumentType, Correspondent


class TestExporter(TestCase):

    @override_settings(
        ORIGINALS_DIR=os.path.join(os.path.dirname(__file__), "samples", "originals"),
        THUMBNAIL_DIR=os.path.join(os.path.dirname(__file__), "samples", "thumb"),
        PASSPHRASE="test"
    )
    def test_exporter(self):
        file = os.path.join(os.path.dirname(__file__), "samples", "originals", "0000001.pdf")

        with open(file, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()

        Document.objects.create(checksum=checksum, title="wow", filename="0000001.pdf", id=1, mime_type="application/pdf")
        Document.objects.create(checksum="9c9691e51741c1f4f41a20896af31770", title="wow", filename="0000002.pdf.gpg", id=2, mime_type="application/pdf", storage_type=Document.STORAGE_TYPE_GPG)
        Tag.objects.create(name="t")
        DocumentType.objects.create(name="dt")
        Correspondent.objects.create(name="c")

        target = tempfile.mkdtemp()

        call_command('document_exporter', target)

        with open(os.path.join(target, "manifest.json")) as f:
            manifest = json.load(f)

        self.assertEqual(len(manifest), 5)

        for element in manifest:
            if element['model'] == 'documents.document':
                fname = os.path.join(target, element[document_exporter.EXPORTER_FILE_NAME])
                self.assertTrue(os.path.exists(fname))
                self.assertTrue(os.path.exists(os.path.join(target, element[document_exporter.EXPORTER_THUMBNAIL_NAME])))

                with open(fname, "rb") as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
                self.assertEqual(checksum, element['fields']['checksum'])

        Document.objects.create(checksum="AAAAAAAAAAAAAAAAA", title="wow", filename="0000004.pdf", id=3, mime_type="application/pdf")

        self.assertRaises(FileNotFoundError, call_command, 'document_exporter', target)
