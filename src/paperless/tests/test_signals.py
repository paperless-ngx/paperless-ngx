from unittest.mock import Mock

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase
from django.test import override_settings

from documents.models import UiSettings
from paperless.signals import handle_failed_login
from paperless.signals import handle_social_account_updated


class TestFailedLoginLogging(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.creds = {
            "username": "john lennon",
        }

    def test_unauthenticated(self) -> None:
        """
        GIVEN:
            - Request with no authentication provided
        WHEN:
            - Request provided to signal handler
        THEN:
            - Unable to determine logged for unauthenticated user
        """
        request = HttpRequest()
        request.META = {}
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, {}, request)
            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:No authentication provided. Unable to determine IP address.",
                ],
            )

    def test_none(self) -> None:
        """
        GIVEN:
            - Request with no IP possible
        WHEN:
            - Request provided to signal handler
        THEN:
            - Unable to determine logged
        """
        request = HttpRequest()
        request.META = {}
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon`. Unable to determine IP address.",
                ],
            )

    def test_public(self) -> None:
        """
        GIVEN:
            - Request with publicly routeable IP
        WHEN:
            - Request provided to signal handler
        THEN:
            - Expected IP is logged
        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "177.139.233.139",
        }
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon` from IP `177.139.233.139`.",
                ],
            )

    def test_private(self) -> None:
        """
        GIVEN:
            - Request with private range IP
        WHEN:
            - Request provided to signal handler
        THEN:
            - Expected IP is logged
            - IP is noted to be a private IP
        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "10.0.0.1",
        }
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon` from private IP `10.0.0.1`.",
                ],
            )


class TestSyncSocialLoginGroups(TestCase):
    @override_settings(SOCIAL_ACCOUNT_SYNC_GROUPS=True)
    def test_sync_enabled(self) -> None:
        """
        GIVEN:
            - Enabled group syncing, a user, and a social login
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are updated to match the social login's groups
        """
        group = Group.objects.create(name="group1")
        user = User.objects.create_user(username="testuser")
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["group1"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        self.assertEqual(list(user.groups.all()), [group])

    @override_settings(SOCIAL_ACCOUNT_SYNC_GROUPS=False)
    def test_sync_disabled(self) -> None:
        """
        GIVEN:
            - Disabled group syncing, a user, and a social login
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are not updated
        """
        Group.objects.create(name="group1")
        user = User.objects.create_user(username="testuser")
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["group1"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        self.assertEqual(list(user.groups.all()), [])

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_GROUPS=True,
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="staff-group",
    )
    def test_no_sync_for_inactive_user(self) -> None:
        """
        GIVEN:
            - Enabled group, superuser, and staff syncing
            - A deactivated user with a matching social login
        WHEN:
            - The social login is updated via signal
        THEN:
            - Groups and roles are left untouched, since the login itself
              would be rejected for a deactivated user anyway
        """
        Group.objects.create(name="admin-group")
        user = User.objects.create_user(
            username="inactive_user",
            is_active=False,
            is_superuser=False,
            is_staff=False,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["admin-group", "staff-group"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertEqual(list(user.groups.all()), [])
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    @override_settings(SOCIAL_ACCOUNT_SYNC_GROUPS=True)
    def test_no_groups(self) -> None:
        """
        GIVEN:
            - Enabled group syncing, a user, and a social login with no groups
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are cleared to match the social login's groups
        """
        group = Group.objects.create(name="group1")
        user = User.objects.create_user(username="testuser")
        user.groups.add(group)
        user.save()
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": [],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        self.assertEqual(list(user.groups.all()), [])

    @override_settings(SOCIAL_ACCOUNT_SYNC_GROUPS=True)
    def test_userinfo_groups(self) -> None:
        """
        GIVEN:
            - Enabled group syncing, and `groups` nested under `userinfo`
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are updated using `userinfo.groups`
        """
        group = Group.objects.create(name="group1")
        user = User.objects.create_user(username="testuser")
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "userinfo": {
                        "groups": ["group1"],
                    },
                },
            ),
        )

        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )

        self.assertEqual(list(user.groups.all()), [group])

    @override_settings(SOCIAL_ACCOUNT_SYNC_GROUPS=True)
    def test_id_token_groups_fallback(self) -> None:
        """
        GIVEN:
            - Enabled group syncing, and `groups` only under `id_token`
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are updated using `id_token.groups`
        """
        group = Group.objects.create(name="group1")
        user = User.objects.create_user(username="testuser")
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "id_token": {
                        "groups": ["group1"],
                    },
                },
            ),
        )

        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )

        self.assertEqual(list(user.groups.all()), [group])

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="admin",
    )
    def test_sync_superuser_claim_no_substring_match(self) -> None:
        """
        GIVEN:
            - Configured superuser group sync
            - Provider emits the groups claim as a bare string, and the user's
              only group merely *contains* the configured name
        WHEN:
            - Social login updated via signal
        THEN:
            - User is not promoted, since only an exact group match counts
        """
        user = User.objects.create_user(
            username="testuser",
            is_superuser=False,
            is_staff=False,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": "paperless-admins-readonly",
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP=None,
    )
    def test_sync_superuser_enabled(self) -> None:
        """
        GIVEN:
            - Configured superuser group sync, and user with that group
        WHEN:
            - Social login updated via signal
        THEN:
            - User becomes superuser and staff
        """
        user = User.objects.create_user(
            username="testuser_s_e",
            is_superuser=False,
            is_staff=False,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["admin-group"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP=None,
    )
    def test_sync_superuser_disabled(self) -> None:
        """
        GIVEN:
            - Configured superuser group sync, and user without that group
        WHEN:
            - Social login updated via signal
        THEN:
            - User loses superuser status but preserves staff status if they had it
        """
        user = User.objects.create_user(
            username="testuser_s_d",
            is_superuser=True,
            is_staff=True,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["other-group"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP=None,
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="staff-group",
    )
    def test_sync_staff_enabled(self) -> None:
        """
        GIVEN:
            - Configured staff group sync, and user with that group
        WHEN:
            - Social login updated via signal
        THEN:
            - User becomes staff
        """
        user = User.objects.create_user(
            username="testuser_st_e",
            is_superuser=False,
            is_staff=False,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["staff-group"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP=None,
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="staff-group",
    )
    def test_sync_staff_disabled(self) -> None:
        """
        GIVEN:
            - Configured staff group sync, and user without that group
        WHEN:
            - Social login updated via signal
        THEN:
            - User loses staff status
        """
        user = User.objects.create_user(
            username="testuser_st_d",
            is_superuser=False,
            is_staff=True,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(
                extra_data={
                    "groups": ["other-group"],
                },
            ),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="staff-group",
    )
    def test_sync_both_groups(self) -> None:
        """
        GIVEN:
            - Configured both superuser and staff group sync
        WHEN:
            - Social login updated via signal
        THEN:
            - Roles are correctly assigned/revoked according to groups
        """
        # Case 1: has both
        user = User.objects.create_user(
            username="testuser_b_1",
            is_superuser=False,
            is_staff=False,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(extra_data={"groups": ["admin-group", "staff-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

        # Case 2: has only staff
        user2 = User.objects.create_user(
            username="testuser_b_2",
            is_superuser=True,
            is_staff=True,
        )
        sociallogin2 = Mock(
            user=user2,
            account=Mock(extra_data={"groups": ["staff-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin2,
        )
        user2.refresh_from_db()
        self.assertFalse(user2.is_superuser)
        self.assertTrue(user2.is_staff)

        # Case 3: has neither
        user3 = User.objects.create_user(
            username="testuser_b_3",
            is_superuser=True,
            is_staff=True,
        )
        sociallogin3 = Mock(
            user=user3,
            account=Mock(extra_data={"groups": ["other-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin3,
        )
        user3.refresh_from_db()
        self.assertFalse(user3.is_superuser)
        self.assertFalse(user3.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP=None,
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP=None,
    )
    def test_no_sync_when_not_configured(self) -> None:
        """
        GIVEN:
            - No sync settings configured
        WHEN:
            - Social login updated via signal
        THEN:
            - Existing roles are not modified
        """
        user = User.objects.create_user(
            username="testuser_n_s",
            is_superuser=True,
            is_staff=True,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(extra_data={"groups": ["admin-group", "staff-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP=None,
    )
    def test_sync_superuser_demotes_local_user_without_group(self) -> None:
        """
        GIVEN:
            - Configured superuser group sync
            - User with a usable (local) password, but without the group
        WHEN:
            - Social login updated via signal
        THEN:
            - User's superuser status is demoted, matching the group claim exactly
        """
        user = User.objects.create_user(
            username="local_admin",
            password="password123",
            is_superuser=True,
            is_staff=True,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(extra_data={"groups": ["other-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP="admin-group",
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP=None,
    )
    def test_sync_superuser_demotes_last_admin(self) -> None:
        """
        GIVEN:
            - Configured superuser group sync
            - User without the group, and no other active superuser exists
        WHEN:
            - Social login updated via signal
        THEN:
            - User's superuser status is demoted, even though they are the last admin
        """
        user = User.objects.create_user(
            username="last_admin",
            is_superuser=True,
            is_staff=True,
        )
        user.set_unusable_password()
        user.save()

        sociallogin = Mock(
            user=user,
            account=Mock(extra_data={"groups": ["other-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    @override_settings(
        SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP=None,
        SOCIAL_ACCOUNT_SYNC_STAFF_GROUP="staff-group",
    )
    def test_sync_staff_demotes_local_user_without_group(self) -> None:
        """
        GIVEN:
            - Configured staff group sync
            - User with a usable (local) password, but without the group
        WHEN:
            - Social login updated via signal
        THEN:
            - User's staff status is demoted, matching the group claim exactly
        """
        user = User.objects.create_user(
            username="local_staff",
            password="password123",
            is_superuser=False,
            is_staff=True,
        )
        sociallogin = Mock(
            user=user,
            account=Mock(extra_data={"groups": ["other-group"]}),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )
        user.refresh_from_db()
        self.assertFalse(user.is_staff)


class TestUserGroupDeletionCleanup(TestCase):
    """
    Test that when a user or group is deleted, references are cleaned up properly
    from ui_settings
    """

    def test_user_group_deletion_cleanup(self) -> None:
        """
        GIVEN:
            - Existing user
            - Existing group
        WHEN:
            - The user is deleted
            - The group is deleted
        THEN:
            - References in ui_settings are cleaned up
        """
        user = User.objects.create_user(username="testuser")
        user2 = User.objects.create_user(username="testuser2")
        group = Group.objects.create(name="testgroup")

        ui_settings = UiSettings.objects.create(
            user=user,
            settings={
                "permissions": {
                    "default_owner": user2.id,
                    "default_view_users": [user2.id],
                    "default_change_users": [user2.id],
                    "default_view_groups": [group.id],
                    "default_change_groups": [group.id],
                },
            },
        )

        user2.delete()
        ui_settings.refresh_from_db()
        permissions = ui_settings.settings.get("permissions", {})
        self.assertIsNone(permissions.get("default_owner"))
        self.assertEqual(permissions.get("default_view_users"), [])
        self.assertEqual(permissions.get("default_change_users"), [])

        group.delete()
        ui_settings.refresh_from_db()
        permissions = ui_settings.settings.get("permissions", {})
        self.assertEqual(permissions.get("default_view_groups"), [])
        self.assertEqual(permissions.get("default_change_groups"), [])

    def test_user_group_deletion_error_handling(self) -> None:
        """
        GIVEN:
            - Existing user and group
        WHEN:
            - The user is deleted and an error occurs during the signal handling
        THEN:
            - Error is logged and the system remains stable
        """
        user = User.objects.create_user(username="testuser")
        user2 = User.objects.create_user(username="testuser2")
        user2_id = user2.id
        Group.objects.create(name="testgroup")

        UiSettings.objects.create(
            user=user,
        )  # invalid, no settings, this probably should not happen in production

        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            user2.delete()
            self.assertIn(
                f"Error while cleaning up user {user2_id}",
                cm.output[0],
            )
