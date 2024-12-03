from unittest.mock import ANY

from documents.tests.utils import TestMigrations


class TestMigrateCustomFieldSelects(TestMigrations):
    migrate_from = "1059_workflowactionemail_workflowactionwebhook_and_more"
    migrate_to = "1060_alter_customfieldinstance_value_select"

    def setUpBeforeMigration(self, apps):
        CustomField = apps.get_model("documents.CustomField")
        self.old_format = CustomField.objects.create(
            name="cf1",
            data_type="select",
            extra_data={"select_options": ["Option 1", "Option 2", "Option 3"]},
        )
        Document = apps.get_model("documents.Document")
        doc = Document.objects.create(title="doc1")
        CustomFieldInstance = apps.get_model("documents.CustomFieldInstance")
        self.old_instance = CustomFieldInstance.objects.create(
            field=self.old_format,
            value_select=0,
            document=doc,
        )

    def test_migrate_old_to_new_select_fields(self):
        self.old_format.refresh_from_db()
        self.old_instance.refresh_from_db()

        self.assertEqual(
            self.old_format.extra_data["select_options"],
            [
                {"label": "Option 1", "id": ANY},
                {"label": "Option 2", "id": ANY},
                {"label": "Option 3", "id": ANY},
            ],
        )

        self.assertEqual(
            self.old_instance.value_select,
            self.old_format.extra_data["select_options"][0]["id"],
        )


class TestMigrationCustomFieldSelectsReverse(TestMigrations):
    migrate_from = "1060_alter_customfieldinstance_value_select"
    migrate_to = "1059_workflowactionemail_workflowactionwebhook_and_more"

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
        Document = apps.get_model("documents.Document")
        doc = Document.objects.create(title="doc1")
        CustomFieldInstance = apps.get_model("documents.CustomFieldInstance")
        self.new_instance = CustomFieldInstance.objects.create(
            field=self.new_format,
            value_select="id1",
            document=doc,
        )

    def test_migrate_new_to_old_select_fields(self):
        self.new_format.refresh_from_db()
        self.new_instance.refresh_from_db()

        self.assertEqual(
            self.new_format.extra_data["select_options"],
            [
                "Option 1",
                "Option 2",
                "Option 3",
            ],
        )

        self.assertEqual(
            self.new_instance.value_select,
            0,
        )
