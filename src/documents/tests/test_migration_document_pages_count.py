import os
import shutil
from pathlib import Path

from django.conf import settings

from documents.tests.utils import TestMigrations


def source_path_before(self):
    if self.filename:
        fname = str(self.filename)

    return os.path.join(settings.ORIGINALS_DIR, fname)


class TestMigrateDocumentPagesCount(TestMigrations):
    migrate_from = "1052_document_transaction_id"
    migrate_to = "1053_document_pages_count"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")
        doc = Document.objects.create(
            title="test1",
            mime_type="application/pdf",
            filename="file1.pdf",
        )
        self.doc_id = doc.id
        shutil.copy(
            Path(__file__).parent / "samples" / "simple.pdf",
            source_path_before(doc),
        )

    def testDocumentPagesCountMigrated(self):
        Document = self.apps.get_model("documents", "Document")

        doc = Document.objects.get(id=self.doc_id)
        self.assertEqual(doc.pages_count, 1)


class TestMigrateDocumentPagesCountBackwards(TestMigrations):
    migrate_from = "1053_document_pages_count"
    migrate_to = "1052_document_transaction_id"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")
        doc = Document.objects.create(
            title="test1",
            mime_type="application/pdf",
            filename="file1.pdf",
            pages_count=8,
        )
        self.doc_id = doc.id

    def test_remove_number_of_pages_to_pages_count(self):
        Document = self.apps.get_model("documents", "Document")
        self.assertFalse(
            "pages_count" in [field.name for field in Document._meta.get_fields()],
        )
