from django.contrib.auth import get_user_model

from documents.tests.utils import TestMigrations


class TestMigrateConsumptionTemplate(TestMigrations):
    migrate_from = "1038_sharelink"
    migrate_to = "1039_consumptiontemplate"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.get(codename="add_document")
        self.user.user_permissions.add(permission.id)
        self.group.permissions.add(permission.id)

    def test_users_with_add_documents_get_add_consumptiontemplate(self):
        permission = self.Permission.objects.get(codename="add_consumptiontemplate")
        self.assertTrue(self.user.has_perm(f"documents.{permission.codename}"))
        self.assertTrue(permission in self.group.permissions.all())


class TestReverseMigrateConsumptionTemplate(TestMigrations):
    migrate_from = "1039_consumptiontemplate"
    migrate_to = "1038_sharelink"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.filter(
            codename="add_consumptiontemplate",
        ).first()
        if permission is not None:
            self.user.user_permissions.add(permission.id)
            self.group.permissions.add(permission.id)

    def test_remove_consumptiontemplate_permissions(self):
        permission = self.Permission.objects.filter(
            codename="add_consumptiontemplate",
        ).first()
        # can be None ? now that CTs removed
        if permission is not None:
            self.assertFalse(self.user.has_perm(f"documents.{permission.codename}"))
            self.assertFalse(permission in self.group.permissions.all())
