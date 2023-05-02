from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import TestMigrations


class TestMigrateNullCharacters(DirectoriesMixin, TestMigrations):
    migrate_from = "1014_auto_20210228_1614"
    migrate_to = "1015_remove_null_characters"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")
        self.doc = Document.objects.create(content="aaa\0bbb")

    def testMimeTypesMigrated(self):
        Document = self.apps.get_model("documents", "Document")
        self.assertNotIn("\0", Document.objects.get(id=self.doc.id).content)
