from documents.data_models import DocumentSource
from documents.tests.utils import TestMigrations


class TestMigrateWorkflow(TestMigrations):
    migrate_from = "1043_alter_savedviewfilterrule_rule_type"
    migrate_to = "1044_workflow_workflowaction_workflowtrigger_and_more"
    dependencies = (
        (
            "paperless_mail",
            "0028_alter_mailaccount_password_and_more",
        ),
    )

    def setUpBeforeMigration(self, apps):
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.get(codename="add_document")
        self.user.user_permissions.add(permission.id)
        self.group.permissions.add(permission.id)

        # create a CT to migrate
        c = apps.get_model("documents", "Correspondent").objects.create(
            name="Correspondent Name",
        )
        dt = apps.get_model("documents", "DocumentType").objects.create(
            name="DocType Name",
        )
        t1 = apps.get_model("documents", "Tag").objects.create(name="t1")
        sp = apps.get_model("documents", "StoragePath").objects.create(path="/test/")
        cf1 = apps.get_model("documents", "CustomField").objects.create(
            name="Custom Field 1",
            data_type="string",
        )
        ma = apps.get_model("paperless_mail", "MailAccount").objects.create(
            name="MailAccount 1",
        )
        mr = apps.get_model("paperless_mail", "MailRule").objects.create(
            name="MailRule 1",
            order=0,
            account=ma,
        )

        user2 = User.objects.create(username="user2")
        user3 = User.objects.create(username="user3")
        group2 = Group.objects.create(name="group2")

        ConsumptionTemplate = apps.get_model("documents", "ConsumptionTemplate")

        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
            filter_mailrule=mr,
            assign_title="Doc from {correspondent}",
            assign_correspondent=c,
            assign_document_type=dt,
            assign_storage_path=sp,
            assign_owner=user2,
        )

        ct.assign_tags.add(t1)
        ct.assign_view_users.add(user3)
        ct.assign_view_groups.add(group2)
        ct.assign_change_users.add(user3)
        ct.assign_change_groups.add(group2)
        ct.assign_custom_fields.add(cf1)
        ct.save()

    def test_users_with_add_documents_get_add_and_workflow_templates_get_migrated(self):
        permission = self.Permission.objects.get(codename="add_workflow")
        self.assertTrue(permission in self.user.user_permissions.all())
        self.assertTrue(permission in self.group.permissions.all())

        Workflow = self.apps.get_model("documents", "Workflow")
        self.assertEqual(Workflow.objects.all().count(), 1)


class TestReverseMigrateWorkflow(TestMigrations):
    migrate_from = "1044_workflow_workflowaction_workflowtrigger_and_more"
    migrate_to = "1043_alter_savedviewfilterrule_rule_type"

    def setUpBeforeMigration(self, apps):
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        permission = self.Permission.objects.filter(
            codename="add_workflow",
        ).first()
        if permission is not None:
            self.user.user_permissions.add(permission.id)
            self.group.permissions.add(permission.id)

        Workflow = apps.get_model("documents", "Workflow")
        WorkflowTrigger = apps.get_model("documents", "WorkflowTrigger")
        WorkflowAction = apps.get_model("documents", "WorkflowAction")

        trigger = WorkflowTrigger.objects.create(
            type=0,
            sources=[DocumentSource.ConsumeFolder],
            filter_path="*/path/*",
            filter_filename="*file*",
        )

        action = WorkflowAction.objects.create(
            assign_title="assign title",
        )
        workflow = Workflow.objects.create(
            name="workflow 1",
            order=0,
        )
        workflow.triggers.set([trigger])
        workflow.actions.set([action])
        workflow.save()

    def test_remove_workflow_permissions_and_migrate_workflows_to_consumption_templates(
        self,
    ):
        permission = self.Permission.objects.filter(
            codename="add_workflow",
        ).first()
        if permission is not None:
            self.assertFalse(permission in self.user.user_permissions.all())
            self.assertFalse(permission in self.group.permissions.all())

        ConsumptionTemplate = self.apps.get_model("documents", "ConsumptionTemplate")
        self.assertEqual(ConsumptionTemplate.objects.all().count(), 1)
