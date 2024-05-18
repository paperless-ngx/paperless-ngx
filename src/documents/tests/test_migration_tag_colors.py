from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import TestMigrations


class TestMigrateTagColor(DirectoriesMixin, TestMigrations):
    migrate_from = "1012_fix_archive_files"
    migrate_to = "1013_migrate_tag_colour"

    def setUpBeforeMigration(self, apps):
        Tag = apps.get_model("documents", "Tag")
        self.t1_id = Tag.objects.create(name="tag1").id
        self.t2_id = Tag.objects.create(name="tag2", colour=1).id
        self.t3_id = Tag.objects.create(name="tag3", colour=5).id

    def testMimeTypesMigrated(self):
        Tag = self.apps.get_model("documents", "Tag")
        self.assertEqual(Tag.objects.get(id=self.t1_id).color, "#a6cee3")
        self.assertEqual(Tag.objects.get(id=self.t2_id).color, "#a6cee3")
        self.assertEqual(Tag.objects.get(id=self.t3_id).color, "#fb9a99")


class TestMigrateTagColorBackwards(DirectoriesMixin, TestMigrations):
    migrate_from = "1013_migrate_tag_colour"
    migrate_to = "1012_fix_archive_files"

    def setUpBeforeMigration(self, apps):
        Tag = apps.get_model("documents", "Tag")
        self.t1_id = Tag.objects.create(name="tag1").id
        self.t2_id = Tag.objects.create(name="tag2", color="#cab2d6").id
        self.t3_id = Tag.objects.create(name="tag3", color="#123456").id

    def testMimeTypesReverted(self):
        Tag = self.apps.get_model("documents", "Tag")
        self.assertEqual(Tag.objects.get(id=self.t1_id).colour, 1)
        self.assertEqual(Tag.objects.get(id=self.t2_id).colour, 9)
        self.assertEqual(Tag.objects.get(id=self.t3_id).colour, 1)
