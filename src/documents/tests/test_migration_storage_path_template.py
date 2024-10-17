from documents.models import StoragePath
from documents.tests.utils import TestMigrations


class TestMigrateStoragePathToTemplate(TestMigrations):
    migrate_from = "1054_customfieldinstance_value_monetary_amount_and_more"
    migrate_to = "1055_alter_storagepath_path"

    def setUpBeforeMigration(self, apps):
        self.old_format = StoragePath.objects.create(
            name="sp1",
            path="Something/{title}",
        )
        self.new_format = StoragePath.objects.create(
            name="sp2",
            path="{{asn}}/{{title}}",
        )
        self.no_formatting = StoragePath.objects.create(
            name="sp3",
            path="Some/Fixed/Path",
        )

    def test_migrate_old_to_new_storage_path(self):
        self.old_format.refresh_from_db()
        self.new_format.refresh_from_db()
        self.no_formatting.refresh_from_db()

        self.assertEqual(self.old_format.path, "Something/{{ title }}")
        self.assertEqual(self.new_format.path, "{{asn}}/{{title}}")
        self.assertEqual(self.no_formatting.path, "Some/Fixed/Path")
