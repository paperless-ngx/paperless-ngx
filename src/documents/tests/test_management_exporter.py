import hashlib
import json
import os
import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from documents.management.commands import document_exporter
from documents.models import Document, Tag, DocumentType, Correspondent
from documents.sanity_checker import check_sanity
from documents.tests.utils import DirectoriesMixin, paperless_environment


class TestExportImport(DirectoriesMixin, TestCase):

    @override_settings(
        PASSPHRASE="test"
    )
    def test_exporter(self):
        shutil.rmtree(os.path.join(self.dirs.media_dir, "documents"))
        shutil.copytree(os.path.join(os.path.dirname(__file__), "samples", "documents"), os.path.join(self.dirs.media_dir, "documents"))

        file = os.path.join(self.dirs.originals_dir, "0000001.pdf")

        d1 = Document.objects.create(content="Content", checksum="42995833e01aea9b3edee44bbfdd7ce1", archive_checksum="62acb0bcbfbcaa62ca6ad3668e4e404b", title="wow", filename="0000001.pdf", mime_type="application/pdf")
        d2 = Document.objects.create(content="Content", checksum="9c9691e51741c1f4f41a20896af31770", title="wow", filename="0000002.pdf.gpg", mime_type="application/pdf", storage_type=Document.STORAGE_TYPE_GPG)
        t1 = Tag.objects.create(name="t")
        dt1 = DocumentType.objects.create(name="dt")
        c1 = Correspondent.objects.create(name="c")

        d1.tags.add(t1)
        d1.correspondents = c1
        d1.document_type = dt1
        d1.save()
        d2.save()

        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)

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

                if document_exporter.EXPORTER_ARCHIVE_NAME in element:
                    fname = os.path.join(target, element[document_exporter.EXPORTER_ARCHIVE_NAME])
                    self.assertTrue(os.path.exists(fname))

                    with open(fname, "rb") as f:
                        checksum = hashlib.md5(f.read()).hexdigest()
                    self.assertEqual(checksum, element['fields']['archive_checksum'])

        with paperless_environment() as dirs:
            self.assertEqual(Document.objects.count(), 2)
            Document.objects.all().delete()
            Correspondent.objects.all().delete()
            DocumentType.objects.all().delete()
            Tag.objects.all().delete()
            self.assertEqual(Document.objects.count(), 0)

            call_command('document_importer', target)
            self.assertEqual(Document.objects.count(), 2)
            messages = check_sanity()
            # everything is alright after the test
            self.assertEqual(len(messages), 0, str([str(m) for m in messages]))

    @override_settings(
        PAPERLESS_FILENAME_FORMAT="{title}"
    )
    def test_exporter_with_filename_format(self):
        self.test_exporter()

    def test_export_missing_files(self):

        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        Document.objects.create(checksum="AAAAAAAAAAAAAAAAA", title="wow", filename="0000004.pdf", mime_type="application/pdf")
        self.assertRaises(FileNotFoundError, call_command, 'document_exporter', target)
