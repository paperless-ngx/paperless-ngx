from django.contrib.auth import get_user_model

from documents.tests.utils import TestMigrations


class TestMigrateCustomFields(TestMigrations):
    migrate_from = "1039_consumptiontemplate"
    migrate_to = "1040_customfield_customfieldinstance_and_more"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.get(codename="add_document")
        self.user.user_permissions.add(permission.id)
        self.group.permissions.add(permission.id)

    def test_users_with_add_documents_get_add_customfields(self):
        permission = self.Permission.objects.get(codename="add_customfield")
        self.assertTrue(self.user.has_perm(f"documents.{permission.codename}"))
        self.assertTrue(permission in self.group.permissions.all())


class TestReverseMigrateCustomFields(TestMigrations):
    migrate_from = "1040_customfield_customfieldinstance_and_more"
    migrate_to = "1039_consumptiontemplate"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.get(codename="add_customfield")
        self.user.user_permissions.add(permission.id)
        self.group.permissions.add(permission.id)

    def test_remove_consumptiontemplate_permissions(self):
        permission = self.Permission.objects.get(codename="add_customfield")
        self.assertFalse(self.user.has_perm(f"documents.{permission.codename}"))
        self.assertFalse(permission in self.group.permissions.all())
