from unittest.mock import ANY

from documents.tests.utils import TestMigrations


class TestMigrateCustomFieldSelects(TestMigrations):
    migrate_from = "1056_customfieldinstance_deleted_at_and_more"
    migrate_to = "1057_alter_customfieldinstance_value_select"

    def setUpBeforeMigration(self, apps):
        CustomField = apps.get_model("documents.CustomField")
        self.old_format = CustomField.objects.create(
            name="cf1",
            data_type="select",
            extra_data={"select_options": ["Option 1", "Option 2", "Option 3"]},
        )

    def test_migrate_old_to_new_storage_path(self):
        self.old_format.refresh_from_db()

        self.assertEqual(
            self.old_format.extra_data["select_options"],
            [
                {"label": "Option 1", "id": ANY},
                {"label": "Option 2", "id": ANY},
                {"label": "Option 3", "id": ANY},
            ],
        )


class TestMigrationCustomFieldSelectsReverse(TestMigrations):
    migrate_from = "1057_alter_customfieldinstance_value_select"
    migrate_to = "1056_customfieldinstance_deleted_at_and_more"

    def setUpBeforeMigration(self, apps):
        CustomField = apps.get_model("documents.CustomField")
        self.new_format = CustomField.objects.create(
            name="cf1",
            data_type="select",
            extra_data={
                "select_options": [
                    {"label": "Option 1", "id": "id1"},
                    {"label": "Option 2", "id": "id2"},
                    {"label": "Option 3", "id": "id3"},
                ],
            },
        )

    def test_migrate_new_to_old_storage_path(self):
        self.new_format.refresh_from_db()

        self.assertEqual(
            self.new_format.extra_data["select_options"],
            [
                "Option 1",
                "Option 2",
                "Option 3",
            ],
        )
