from django.contrib.auth import get_user_model

from documents.tests.utils import TestMigrations


class TestMigrateWorkflow(TestMigrations):
    migrate_from = "1043_alter_savedviewfilterrule_rule_type"
    migrate_to = "1044_workflow_workflowaction_workflowtrigger_and_more"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.get(codename="add_document")
        self.user.user_permissions.add(permission.id)
        self.group.permissions.add(permission.id)

    def test_users_with_add_documents_get_add_workflow(self):
        permission = self.Permission.objects.get(codename="add_workflow")
        self.assertTrue(self.user.has_perm(f"documents.{permission.codename}"))
        self.assertTrue(permission in self.group.permissions.all())


class TestReverseMigrateWorkflow(TestMigrations):
    migrate_from = "1044_workflow_workflowaction_workflowtrigger_and_more"
    migrate_to = "1043_alter_savedviewfilterrule_rule_type"

    def setUpBeforeMigration(self, apps):
        User = get_user_model()
        Group = apps.get_model("auth.Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.filter(
            codename="add_workflow",
        ).first()
        if permission is not None:
            self.user.user_permissions.add(permission.id)
            self.group.permissions.add(permission.id)

    def test_remove_workflow_permissions(self):
        permission = self.Permission.objects.filter(
            codename="add_workflow",
        ).first()
        if permission is not None:
            self.assertFalse(self.user.has_perm(f"documents.{permission.codename}"))
            self.assertFalse(permission in self.group.permissions.all())
