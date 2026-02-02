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
