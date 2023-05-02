import os
import shutil

from django.conf import settings
from django.test import override_settings

from documents.parsers import get_default_file_extension
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import TestMigrations

STORAGE_TYPE_UNENCRYPTED = "unencrypted"
STORAGE_TYPE_GPG = "gpg"


def source_path_before(self):
    if self.filename:
        fname = str(self.filename)
    else:
        fname = f"{self.pk:07}.{self.file_type}"
        if self.storage_type == STORAGE_TYPE_GPG:
            fname += ".gpg"

    return os.path.join(settings.ORIGINALS_DIR, fname)


def file_type_after(self):
    return get_default_file_extension(self.mime_type)


def source_path_after(doc):
    if doc.filename:
        fname = str(doc.filename)
    else:
        fname = f"{doc.pk:07}{file_type_after(doc)}"
        if doc.storage_type == STORAGE_TYPE_GPG:
            fname += ".gpg"  # pragma: no cover

    return os.path.join(settings.ORIGINALS_DIR, fname)


@override_settings(PASSPHRASE="test")
class TestMigrateMimeType(DirectoriesMixin, TestMigrations):
    migrate_from = "1002_auto_20201111_1105"
    migrate_to = "1003_mime_types"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")
        doc = Document.objects.create(
            title="test",
            file_type="pdf",
            filename="file1.pdf",
        )
        self.doc_id = doc.id
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            source_path_before(doc),
        )

        doc2 = Document.objects.create(
            checksum="B",
            file_type="pdf",
            storage_type=STORAGE_TYPE_GPG,
        )
        self.doc2_id = doc2.id
        shutil.copy(
            os.path.join(
                os.path.dirname(__file__),
                "samples",
                "documents",
                "originals",
                "0000004.pdf.gpg",
            ),
            source_path_before(doc2),
        )

    def testMimeTypesMigrated(self):
        Document = self.apps.get_model("documents", "Document")

        doc = Document.objects.get(id=self.doc_id)
        self.assertEqual(doc.mime_type, "application/pdf")

        doc2 = Document.objects.get(id=self.doc2_id)
        self.assertEqual(doc2.mime_type, "application/pdf")


@override_settings(PASSPHRASE="test")
class TestMigrateMimeTypeBackwards(DirectoriesMixin, TestMigrations):
    migrate_from = "1003_mime_types"
    migrate_to = "1002_auto_20201111_1105"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            filename="file1.pdf",
        )
        self.doc_id = doc.id
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            source_path_after(doc),
        )

    def testMimeTypesReverted(self):
        Document = self.apps.get_model("documents", "Document")

        doc = Document.objects.get(id=self.doc_id)
        self.assertEqual(doc.file_type, "pdf")
