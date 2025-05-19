from datetime import datetime
from datetime import timedelta

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import TestMigrations


class TestMigrateDocumentCreated(DirectoriesMixin, TestMigrations):
    migrate_from = "1066_alter_workflowtrigger_schedule_offset_days"
    migrate_to = "1067_alter_document_created"

    def setUpBeforeMigration(self, apps):
        # create 600 documents
        for i in range(600):
            Document = apps.get_model("documents", "Document")
            Document.objects.create(
                title=f"test{i}",
                mime_type="application/pdf",
                filename=f"file{i}.pdf",
                created=datetime(
                    2023,
                    10,
                    1,
                    12,
                    0,
                    0,
                )
                + timedelta(days=i),
                checksum=i,
            )

    def testDocumentCreatedMigrated(self):
        Document = self.apps.get_model("documents", "Document")

        doc = Document.objects.get(id=1)
        self.assertEqual(doc.created, datetime(2023, 10, 1, 12, 0, 0).date())
