import filecmp
import hashlib
import os
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from documents.file_handling import generate_filename
from documents.models import Document
from documents.tasks import update_document_content_maybe_archive_file
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin

sample_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")


@override_settings(FILENAME_FORMAT="{correspondent}/{title}")
class TestArchiver(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    def make_models(self):
        return Document.objects.create(
            checksum="A",
            title="A",
            content="first document",
            mime_type="application/pdf",
        )

    def test_archiver(self):
        doc = self.make_models()
        shutil.copy(
            sample_file,
            os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"),
        )

        call_command("document_archiver", "--processes", "1")

    def test_handle_document(self):
        doc = self.make_models()
        shutil.copy(
            sample_file,
            os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"),
        )

        update_document_content_maybe_archive_file(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNotNone(doc.archive_checksum)
        self.assertIsFile(doc.archive_path)
        self.assertIsFile(doc.source_path)
        self.assertTrue(filecmp.cmp(sample_file, doc.source_path))
        self.assertEqual(doc.archive_filename, "none/A.pdf")

    def test_unknown_mime_type(self):
        doc = self.make_models()
        doc.mime_type = "sdgfh"
        doc.save()
        shutil.copy(sample_file, doc.source_path)

        update_document_content_maybe_archive_file(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNone(doc.archive_checksum)
        self.assertIsNone(doc.archive_filename)
        self.assertIsFile(doc.source_path)

    @override_settings(FILENAME_FORMAT="{title}")
    def test_naming_priorities(self):
        doc1 = Document.objects.create(
            checksum="A",
            title="document",
            content="first document",
            mime_type="application/pdf",
            filename="document.pdf",
        )
        doc2 = Document.objects.create(
            checksum="B",
            title="document",
            content="second document",
            mime_type="application/pdf",
            filename="document_01.pdf",
        )
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, "document.pdf"))
        shutil.copy(
            sample_file,
            os.path.join(self.dirs.originals_dir, "document_01.pdf"),
        )

        update_document_content_maybe_archive_file(doc2.pk)
        update_document_content_maybe_archive_file(doc1.pk)

        doc1 = Document.objects.get(id=doc1.id)
        doc2 = Document.objects.get(id=doc2.id)

        self.assertEqual(doc1.archive_filename, "document.pdf")
        self.assertEqual(doc2.archive_filename, "document_01.pdf")


class TestDecryptDocuments(FileSystemAssertsMixin, TestCase):
    @override_settings(
        ORIGINALS_DIR=os.path.join(os.path.dirname(__file__), "samples", "originals"),
        THUMBNAIL_DIR=os.path.join(os.path.dirname(__file__), "samples", "thumb"),
        PASSPHRASE="test",
        FILENAME_FORMAT=None,
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
            PASSPHRASE="test",
        ).enable()

        doc = Document.objects.create(
            checksum="82186aaa94f0b98697d704b90fd1c072",
            title="wow",
            filename="0000004.pdf.gpg",
            mime_type="application/pdf",
            storage_type=Document.STORAGE_TYPE_GPG,
        )

        shutil.copy(
            os.path.join(
                os.path.dirname(__file__),
                "samples",
                "documents",
                "originals",
                "0000004.pdf.gpg",
            ),
            os.path.join(originals_dir, "0000004.pdf.gpg"),
        )
        shutil.copy(
            os.path.join(
                os.path.dirname(__file__),
                "samples",
                "documents",
                "thumbnails",
                "0000004.webp.gpg",
            ),
            os.path.join(thumb_dir, f"{doc.id:07}.webp.gpg"),
        )

        call_command("decrypt_documents")

        doc.refresh_from_db()

        self.assertEqual(doc.storage_type, Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(doc.filename, "0000004.pdf")
        self.assertIsFile(os.path.join(originals_dir, "0000004.pdf"))
        self.assertIsFile(doc.source_path)
        self.assertIsFile(os.path.join(thumb_dir, f"{doc.id:07}.webp"))
        self.assertIsFile(doc.thumbnail_path)

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


class TestRenamer(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @override_settings(FILENAME_FORMAT="")
    def test_rename(self):
        doc = Document.objects.create(title="test", mime_type="image/jpeg")
        doc.filename = generate_filename(doc)
        doc.archive_filename = generate_filename(doc, archive_filename=True)
        doc.save()

        Path(doc.source_path).touch()
        Path(doc.archive_path).touch()

        with override_settings(FILENAME_FORMAT="{correspondent}/{title}"):
            call_command("document_renamer")

        doc2 = Document.objects.get(id=doc.id)

        self.assertEqual(doc2.filename, "none/test.jpg")
        self.assertEqual(doc2.archive_filename, "none/test.pdf")
        self.assertIsNotFile(doc.source_path)
        self.assertIsNotFile(doc.archive_path)
        self.assertIsFile(doc2.source_path)
        self.assertIsFile(doc2.archive_path)


class TestCreateClassifier(TestCase):
    @mock.patch(
        "documents.management.commands.document_create_classifier.train_classifier",
    )
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
        doc = Document.objects.create(
            title="test",
            content="test",
            filename="test.pdf",
            checksum="abc",
        )
        Path(doc.source_path).touch()
        Path(doc.thumbnail_path).touch()

        with self.assertLogs() as capture:
            call_command("document_sanity_checker")

        self.assertEqual(len(capture.output), 2)
        self.assertIn("Checksum mismatch. Stored: abc, actual:", capture.output[1])


class TestConvertMariaDBUUID(TestCase):
    @mock.patch("django.db.connection.schema_editor")
    def test_convert(self, m):
        m.alter_field.return_value = None

        stdout = StringIO()
        call_command("convert_mariadb_uuid", stdout=stdout)

        m.assert_called_once()

        self.assertIn("Successfully converted", stdout.getvalue())


class TestPruneAuditLogs(TestCase):
    def test_prune_audit_logs(self):
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Document),
            object_id=1,
            action=LogEntry.Action.CREATE,
        )
        call_command("prune_audit_logs")

        self.assertEqual(LogEntry.objects.count(), 0)
