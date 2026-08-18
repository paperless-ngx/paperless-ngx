from documents.tests.utils import TestMigrations


class TestMigrateExportPermissions(TestMigrations):
    """
    The permission grant is a RunPython operation, which ``makemigrations``
    can never regenerate: deleting and recreating the migration file silently
    drops it, leaving every non-superuser without access to the feature after
    an upgrade. These tests fail loudly if that happens.
    """

    migrate_from = "0023_savedview_icon"
    migrate_to = "0024_export_destinations"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.workflow_user = User.objects.create(username="workflow_user")
        self.workflow_group = Group.objects.create(name="workflow_group")
        add_workflow = self.Permission.objects.get(codename="add_workflow")
        self.workflow_user.user_permissions.add(add_workflow.id)
        self.workflow_group.permissions.add(add_workflow.id)

        self.viewer = User.objects.create(username="viewer")
        self.viewer_group = Group.objects.create(name="viewer_group")
        view_document = self.Permission.objects.get(codename="view_document")
        self.viewer.user_permissions.add(view_document.id)
        self.viewer_group.permissions.add(view_document.id)

    def test_workflow_managers_get_export_target_permissions(self) -> None:
        target_perms = self.Permission.objects.filter(
            codename__contains="exporttarget",
        )
        self.assertEqual(
            self.workflow_user.user_permissions.filter(pk__in=target_perms).count(),
            4,
        )
        self.assertEqual(
            self.workflow_group.permissions.filter(pk__in=target_perms).count(),
            4,
        )

    def test_workflow_managers_may_export_on_demand(self) -> None:
        add_record = self.Permission.objects.filter(codename="add_exportrecord")
        self.assertTrue(
            self.workflow_user.user_permissions.filter(pk__in=add_record).exists(),
        )
        self.assertTrue(
            self.workflow_group.permissions.filter(pk__in=add_record).exists(),
        )

    def test_document_viewers_get_export_history(self) -> None:
        view_record = self.Permission.objects.filter(codename="view_exportrecord")
        self.assertTrue(
            self.viewer.user_permissions.filter(pk__in=view_record).exists(),
        )
        self.assertTrue(
            self.viewer_group.permissions.filter(pk__in=view_record).exists(),
        )

    def test_document_viewers_do_not_get_export_targets(self) -> None:
        target_perms = self.Permission.objects.filter(
            codename__contains="exporttarget",
        )
        self.assertFalse(
            self.viewer.user_permissions.filter(pk__in=target_perms).exists(),
        )
        self.assertFalse(
            self.viewer_group.permissions.filter(pk__in=target_perms).exists(),
        )


class TestReverseMigrateExportPermissions(TestMigrations):
    migrate_from = "0024_export_destinations"
    migrate_to = "0023_savedview_icon"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        export_perms = self.Permission.objects.filter(
            codename__contains="exporttarget",
        )
        self.export_perm_ids = list(export_perms.values_list("id", flat=True))
        self.user.user_permissions.add(*self.export_perm_ids)
        self.group.permissions.add(*self.export_perm_ids)

    def test_export_permissions_revoked_on_reverse(self) -> None:
        self.assertFalse(
            self.user.user_permissions.filter(pk__in=self.export_perm_ids).exists(),
        )
        self.assertFalse(
            self.group.permissions.filter(pk__in=self.export_perm_ids).exists(),
        )
