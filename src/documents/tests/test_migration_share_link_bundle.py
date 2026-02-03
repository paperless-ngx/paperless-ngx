from documents.tests.utils import TestMigrations


class TestMigrateShareLinkBundlePermissions(TestMigrations):
    migrate_from = "0007_document_content_length"
    migrate_to = "0008_sharelinkbundle"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        add_document = self.Permission.objects.get(codename="add_document")
        self.user.user_permissions.add(add_document.id)
        self.group.permissions.add(add_document.id)

    def test_share_link_permissions_granted_to_add_document_holders(self) -> None:
        share_perms = self.Permission.objects.filter(
            codename__contains="sharelinkbundle",
        )
        self.assertTrue(self.user.user_permissions.filter(pk__in=share_perms).exists())
        self.assertTrue(self.group.permissions.filter(pk__in=share_perms).exists())


class TestReverseMigrateShareLinkBundlePermissions(TestMigrations):
    migrate_from = "0008_sharelinkbundle"
    migrate_to = "0007_document_content_length"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        Group = apps.get_model("auth", "Group")
        self.Permission = apps.get_model("auth", "Permission")
        self.user = User.objects.create(username="user1")
        self.group = Group.objects.create(name="group1")
        add_document = self.Permission.objects.get(codename="add_document")
        share_perms = self.Permission.objects.filter(
            codename__contains="sharelinkbundle",
        )
        self.share_perm_ids = list(share_perms.values_list("id", flat=True))

        self.user.user_permissions.add(add_document.id, *self.share_perm_ids)
        self.group.permissions.add(add_document.id, *self.share_perm_ids)

    def test_share_link_permissions_revoked_on_reverse(self) -> None:
        self.assertFalse(
            self.user.user_permissions.filter(pk__in=self.share_perm_ids).exists(),
        )
        self.assertFalse(
            self.group.permissions.filter(pk__in=self.share_perm_ids).exists(),
        )
