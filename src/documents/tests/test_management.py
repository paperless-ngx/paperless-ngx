import hashlib
import tempfile
import filecmp
import os
import shutil
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings


from django.core.management import call_command

from documents.file_handling import generate_filename
from documents.management.commands.document_archiver import handle_document
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


sample_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")


@override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
class TestArchiver(DirectoriesMixin, TestCase):

    def make_models(self):
        return Document.objects.create(checksum="A", title="A", content="first document", mime_type="application/pdf")

    def test_archiver(self):

        doc = self.make_models()
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"))

        call_command('document_archiver')

    def test_handle_document(self):

        doc = self.make_models()
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"))

        handle_document(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNotNone(doc.archive_checksum)
        self.assertTrue(os.path.isfile(doc.archive_path))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(filecmp.cmp(sample_file, doc.source_path))
        self.assertEqual(doc.archive_filename, "none/A.pdf")

    def test_unknown_mime_type(self):
        doc = self.make_models()
        doc.mime_type = "sdgfh"
        doc.save()
        shutil.copy(sample_file, doc.source_path)

        handle_document(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNone(doc.archive_checksum)
        self.assertIsNone(doc.archive_filename)
        self.assertTrue(os.path.isfile(doc.source_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    def test_naming_priorities(self):
        doc1 = Document.objects.create(checksum="A", title="document", content="first document", mime_type="application/pdf", filename="document.pdf")
        doc2 = Document.objects.create(checksum="B", title="document", content="second document", mime_type="application/pdf", filename="document_01.pdf")
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"document.pdf"))
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"document_01.pdf"))

        handle_document(doc2.pk)
        handle_document(doc1.pk)

        doc1 = Document.objects.get(id=doc1.id)
        doc2 = Document.objects.get(id=doc2.id)

        self.assertEqual(doc1.archive_filename, "document.pdf")
        self.assertEqual(doc2.archive_filename, "document_01.pdf")


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

        doc = Document.objects.create(checksum="82186aaa94f0b98697d704b90fd1c072", title="wow", filename="0000004.pdf.gpg",  mime_type="application/pdf", storage_type=Document.STORAGE_TYPE_GPG)

        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "originals", "0000004.pdf.gpg"), os.path.join(originals_dir, "0000004.pdf.gpg"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "thumbnails", f"0000004.png.gpg"), os.path.join(thumb_dir, f"{doc.id:07}.png.gpg"))

        call_command('decrypt_documents')

        doc.refresh_from_db()

        self.assertEqual(doc.storage_type, Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(doc.filename, "0000004.pdf")
        self.assertTrue(os.path.isfile(os.path.join(originals_dir, "0000004.pdf")))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(os.path.join(thumb_dir, f"{doc.id:07}.png")))
        self.assertTrue(os.path.isfile(doc.thumbnail_path))

        with doc.source_file as f:
            checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(checksum, doc.checksum)


class TestMakeIndex(TestCase):

    @mock.patch("documents.management.commands.document_index.index_reindex")
    def test_reindex(self, m):
        call_command("document_index", "reindex")
        m.assert_called_once()

    @mock.patch("documents.management.commands.document_index.index_optimize")
    def test_optimize(self, m):
        call_command("document_index", "optimize")
        m.assert_called_once()


class TestRenamer(DirectoriesMixin, TestCase):

    @override_settings(PAPERLESS_FILENAME_FORMAT="")
    def test_rename(self):
        doc = Document.objects.create(title="test", mime_type="image/jpeg")
        doc.filename = generate_filename(doc)
        doc.archive_filename = generate_filename(doc, archive_filename=True)
        doc.save()

        Path(doc.source_path).touch()
        Path(doc.archive_path).touch()

        with override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}"):
            call_command("document_renamer")

        doc2 = Document.objects.get(id=doc.id)

        self.assertEqual(doc2.filename, "none/test.jpg")
        self.assertEqual(doc2.archive_filename, "none/test.pdf")
        self.assertFalse(os.path.isfile(doc.source_path))
        self.assertFalse(os.path.isfile(doc.archive_path))
        self.assertTrue(os.path.isfile(doc2.source_path))
        self.assertTrue(os.path.isfile(doc2.archive_path))


class TestCreateClassifier(TestCase):

    @mock.patch("documents.management.commands.document_create_classifier.train_classifier")
    def test_create_classifier(self, m):
        call_command("document_create_classifier")

        m.assert_called_once()


class TestSanityChecker(DirectoriesMixin, TestCase):

    def test_no_issues(self):
        with self.assertLogs() as capture:
            call_command("document_sanity_checker")

        self.assertEqual(len(capture.output), 1)
        self.assertIn("Sanity checker detected no issues.", capture.output[0])

    def test_errors(self):
        doc = Document.objects.create(title="test", content="test", filename="test.pdf", checksum="abc")
        Path(doc.source_path).touch()
        Path(doc.thumbnail_path).touch()

        with self.assertLogs() as capture:
            call_command("document_sanity_checker")

        self.assertEqual(len(capture.output), 1)
        self.assertIn("Checksum mismatch of document", capture.output[0])
