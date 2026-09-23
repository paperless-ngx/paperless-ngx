import dataclasses
import logging
from typing import Any

import pytest
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from documents.models import UiSettings
from paperless.signals import handle_failed_login
from paperless.signals import handle_social_account_updated
from paperless_testing.factories import GroupFactory
from paperless_testing.factories import UserFactory


class TestFailedLoginLogging:
    @pytest.mark.parametrize(
        ("meta", "credentials", "expected_message"),
        [
            pytest.param(
                {},
                {},
                "No authentication provided. Unable to determine IP address.",
                id="unauthenticated",
            ),
            pytest.param(
                {},
                {"username": "john lennon"},
                "Login failed for user `john lennon`. Unable to determine IP address.",
                id="no_ip",
            ),
            pytest.param(
                {"HTTP_X_FORWARDED_FOR": "177.139.233.139"},
                {"username": "john lennon"},
                "Login failed for user `john lennon` from IP `177.139.233.139`.",
                id="public_ip",
            ),
            pytest.param(
                {"HTTP_X_FORWARDED_FOR": "10.0.0.1"},
                {"username": "john lennon"},
                "Login failed for user `john lennon` from private IP `10.0.0.1`.",
                id="private_ip",
            ),
        ],
    )
    def test_handle_failed_login(
        self,
        caplog: pytest.LogCaptureFixture,
        meta: dict[str, str],
        credentials: dict[str, str],
        expected_message: str,
    ) -> None:
        """
        GIVEN:
            - A failed login, with varying request metadata and credentials
        WHEN:
            - The failed-login signal handler runs
        THEN:
            - The expected message is logged, based on what could be determined
              about the user and their IP address
        """
        request = HttpRequest()
        request.META = meta
        with caplog.at_level(logging.INFO, logger="paperless.auth"):
            handle_failed_login(None, credentials, request)

        assert caplog.messages == [expected_message]


@pytest.mark.django_db
class TestSyncSocialLoginGroups:
    @staticmethod
    def _update_social_account(
        mocker: MockerFixture,
        user: AbstractUser,
        extra_data: dict[str, Any],
    ) -> None:
        sociallogin = mocker.MagicMock(
            user=user,
            account=mocker.MagicMock(extra_data=extra_data),
        )
        handle_social_account_updated(
            sender=None,
            request=HttpRequest(),
            sociallogin=sociallogin,
        )

    @pytest.mark.parametrize(
        "sync_enabled",
        [
            pytest.param(True, id="sync_enabled"),
            pytest.param(False, id="sync_disabled"),
        ],
    )
    def test_sync_group_membership(
        self,
        settings: Settings,
        mocker: MockerFixture,
        sync_enabled: bool,  # noqa: FBT001
    ) -> None:
        """
        GIVEN:
            - A user, a social login claiming a group, and group syncing on or off
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are updated to match the claim only when syncing
              is enabled
        """
        settings.SOCIAL_ACCOUNT_SYNC_GROUPS = sync_enabled
        group = GroupFactory(name="group1")
        user = UserFactory()

        self._update_social_account(mocker, user, {"groups": ["group1"]})

        assert list(user.groups.all()) == ([group] if sync_enabled else [])

    def test_no_sync_for_inactive_user(
        self,
        settings: Settings,
        mocker: MockerFixture,
    ) -> None:
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
        settings.SOCIAL_ACCOUNT_SYNC_GROUPS = True
        settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP = "admin-group"
        settings.SOCIAL_ACCOUNT_SYNC_STAFF_GROUP = "staff-group"
        GroupFactory(name="admin-group")
        user = UserFactory(is_active=False)

        self._update_social_account(
            mocker,
            user,
            {"groups": ["admin-group", "staff-group"]},
        )

        user.refresh_from_db()
        assert list(user.groups.all()) == []
        assert not user.is_superuser
        assert not user.is_staff

    def test_no_groups_clears_existing_membership(
        self,
        settings: Settings,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Enabled group syncing, a user, and a social login with no groups
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are cleared to match the social login's groups
        """
        settings.SOCIAL_ACCOUNT_SYNC_GROUPS = True
        group = GroupFactory(name="group1")
        user = UserFactory()
        user.groups.add(group)

        self._update_social_account(mocker, user, {"groups": []})

        assert list(user.groups.all()) == []

    @pytest.mark.parametrize(
        "extra_data",
        [
            pytest.param({"userinfo": {"groups": ["group1"]}}, id="userinfo"),
            pytest.param({"id_token": {"groups": ["group1"]}}, id="id_token_fallback"),
        ],
    )
    def test_sync_group_nested_claim_locations(
        self,
        settings: Settings,
        mocker: MockerFixture,
        extra_data: dict[str, Any],
    ) -> None:
        """
        GIVEN:
            - Enabled group syncing, and `groups` nested under `userinfo` or
              `id_token` (allauth 65.11.0+ structure)
        WHEN:
            - The social login is updated via signal after login
        THEN:
            - The user's groups are updated using the nested claim
        """
        settings.SOCIAL_ACCOUNT_SYNC_GROUPS = True
        group = GroupFactory(name="group1")
        user = UserFactory()

        self._update_social_account(mocker, user, extra_data)

        assert list(user.groups.all()) == [group]

    def test_sync_superuser_claim_no_substring_match(
        self,
        settings: Settings,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Configured superuser group sync
            - Provider emits the groups claim as a bare string that merely
              *contains* the configured name
        WHEN:
            - Social login updated via signal
        THEN:
            - User is not promoted, since only an exact group match counts
        """
        settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP = "admin"
        settings.SOCIAL_ACCOUNT_SYNC_STAFF_GROUP = "admin"
        user = UserFactory()

        self._update_social_account(
            mocker,
            user,
            {"groups": "paperless-admins-readonly"},
        )

        user.refresh_from_db()
        assert not user.is_superuser
        assert not user.is_staff

    @dataclasses.dataclass(frozen=True, slots=True)
    class RoleSyncCase:
        superuser_group: str | None
        staff_group: str | None
        initial_superuser: bool
        initial_staff: bool
        claimed_groups: list[str]
        expected_superuser: bool
        expected_staff: bool
        # A usable local password, to prove it offers no protection against demotion.
        password: str | None = None

    @pytest.mark.parametrize(
        "case",
        [
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group=None,
                    initial_superuser=False,
                    initial_staff=False,
                    claimed_groups=["admin-group"],
                    expected_superuser=True,
                    expected_staff=True,
                ),
                id="superuser_enabled",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group=None,
                    initial_superuser=True,
                    initial_staff=True,
                    claimed_groups=["other-group"],
                    expected_superuser=False,
                    expected_staff=True,
                ),
                id="superuser_disabled_keeps_staff",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group=None,
                    staff_group="staff-group",
                    initial_superuser=False,
                    initial_staff=False,
                    claimed_groups=["staff-group"],
                    expected_superuser=False,
                    expected_staff=True,
                ),
                id="staff_enabled",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group=None,
                    staff_group="staff-group",
                    initial_superuser=False,
                    initial_staff=True,
                    claimed_groups=["other-group"],
                    expected_superuser=False,
                    expected_staff=False,
                ),
                id="staff_disabled",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group="staff-group",
                    initial_superuser=False,
                    initial_staff=False,
                    claimed_groups=["admin-group", "staff-group"],
                    expected_superuser=True,
                    expected_staff=True,
                ),
                id="both_groups_has_both",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group="staff-group",
                    initial_superuser=True,
                    initial_staff=True,
                    claimed_groups=["staff-group"],
                    expected_superuser=False,
                    expected_staff=True,
                ),
                id="both_groups_has_only_staff",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group="staff-group",
                    initial_superuser=True,
                    initial_staff=True,
                    claimed_groups=["other-group"],
                    expected_superuser=False,
                    expected_staff=False,
                ),
                id="both_groups_has_neither",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group=None,
                    staff_group=None,
                    initial_superuser=True,
                    initial_staff=True,
                    claimed_groups=["admin-group", "staff-group"],
                    expected_superuser=True,
                    expected_staff=True,
                ),
                id="not_configured_leaves_roles",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group="admin-group",
                    staff_group=None,
                    initial_superuser=True,
                    initial_staff=True,
                    claimed_groups=["other-group"],
                    expected_superuser=False,
                    expected_staff=True,
                    password="password123",
                ),
                id="superuser_demotes_local_user_with_usable_password",
            ),
            pytest.param(
                RoleSyncCase(
                    superuser_group=None,
                    staff_group="staff-group",
                    initial_superuser=False,
                    initial_staff=True,
                    claimed_groups=["other-group"],
                    expected_superuser=False,
                    expected_staff=False,
                    password="password123",
                ),
                id="staff_demotes_local_user_with_usable_password",
            ),
        ],
    )
    def test_sync_roles(
        self,
        settings: Settings,
        mocker: MockerFixture,
        case: RoleSyncCase,
    ) -> None:
        """
        GIVEN:
            - Various combinations of superuser/staff group sync configuration
              and a user's current roles
        WHEN:
            - The social login is updated via signal with a set of claimed groups
        THEN:
            - The user's superuser and staff flags are set to match the claim
              exactly
        """
        settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP = case.superuser_group
        settings.SOCIAL_ACCOUNT_SYNC_STAFF_GROUP = case.staff_group
        user = UserFactory(
            is_superuser=case.initial_superuser,
            is_staff=case.initial_staff,
            **({"password": case.password} if case.password else {}),
        )

        self._update_social_account(mocker, user, {"groups": case.claimed_groups})

        user.refresh_from_db()
        assert user.is_superuser == case.expected_superuser
        assert user.is_staff == case.expected_staff


@pytest.mark.django_db
class TestUserGroupDeletionCleanup:
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
        user = UserFactory()
        user2 = UserFactory()
        group = GroupFactory()

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
        assert permissions.get("default_owner") is None
        assert permissions.get("default_view_users") == []
        assert permissions.get("default_change_users") == []

        group.delete()
        ui_settings.refresh_from_db()
        permissions = ui_settings.settings.get("permissions", {})
        assert permissions.get("default_view_groups") == []
        assert permissions.get("default_change_groups") == []

    def test_user_group_deletion_error_handling(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - Existing user, referenced by ui_settings with no `settings` set
              (invalid; this probably should not happen in production)
        WHEN:
            - The user is deleted and an error occurs during the signal handling
        THEN:
            - Error is logged and the system remains stable
        """
        user = UserFactory()
        user2 = UserFactory()
        user2_id = user2.id
        UiSettings.objects.create(user=user)

        with caplog.at_level(logging.ERROR, logger="paperless.handlers"):
            user2.delete()

        assert f"Error while cleaning up user {user2_id}" in caplog.text
