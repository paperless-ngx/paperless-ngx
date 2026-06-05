from documents.tests.utils import TestMigrations


class TestMigrateFolders(TestMigrations):
    migrate_from = "0021_widen_workflow_integer_fields"
    migrate_to = "0022_folder_document_folder"

    def setUpBeforeMigration(self, apps) -> None:
        Document = apps.get_model("documents", "Document")
        self.doc1 = Document.objects.create(
            checksum="A",
            title="A",
            mime_type="application/pdf",
        )
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            mime_type="application/pdf",
        )

    def test_existing_documents_assigned_default_folder(self) -> None:
        Folder = self.apps.get_model("documents", "Folder")
        Document = self.apps.get_model("documents", "Document")

        default = Folder.objects.get(is_default=True)
        self.assertEqual(default.name, "Inbox")
        self.assertEqual(Folder.objects.filter(is_default=True).count(), 1)

        # Every existing document now has a folder
        self.assertEqual(Document.objects.filter(folder__isnull=True).count(), 0)
        self.assertEqual(
            Document.objects.get(checksum="A").folder_id,
            default.pk,
        )
        self.assertEqual(
            Document.objects.get(checksum="B").folder_id,
            default.pk,
        )


class TestMigrateFoldersReverse(TestMigrations):
    migrate_from = "0022_folder_document_folder"
    migrate_to = "0021_widen_workflow_integer_fields"

    def setUpBeforeMigration(self, apps) -> None:
        Folder = apps.get_model("documents", "Folder")
        Document = apps.get_model("documents", "Document")
        folder = Folder.objects.create(name="Inbox", is_default=True)
        self.doc = Document.objects.create(
            checksum="A",
            title="A",
            mime_type="application/pdf",
            folder=folder,
        )

    def test_reverse_removes_folder_column(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        # The folder field no longer exists after reversing
        field_names = {f.name for f in Document._meta.get_fields()}
        self.assertNotIn("folder", field_names)
