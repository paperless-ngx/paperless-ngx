import json
from datetime import timedelta

from allauth.mfa.totp.internal import auth as totp_auth
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from paperless.account_sessions import ADD_CHALLENGE_SESSION_KEY
from paperless.account_sessions import account_session_cookie_name
from paperless.models import AccountSession
from paperless.models import AccountSessionGroup


class TestAccountSessions(TestCase):
    password = "test-password"

    def setUp(self):
        self.user1 = User.objects.create_user(
            username="account-one",
            password=self.password,
        )
        self.user2 = User.objects.create_user(
            username="account-two",
            password=self.password,
        )

    def enroll(self, client: Client, user: User) -> AccountSessionGroup:
        client.force_login(user)
        response = client.get(reverse("account_sessions"))
        self.assertEqual(response.json()["accounts"][0]["id"], user.pk)
        self.assertTrue(response.json()["accounts"][0]["current"])
        group = AccountSessionGroup.objects.get()
        self.assertTrue(
            group.account_sessions.filter(
                user=user,
                session_key=client.session.session_key,
            ).exists(),
        )
        return group

    def add_session(
        self,
        group: AccountSessionGroup,
        user: User,
    ) -> tuple[Client, AccountSession]:
        other_client = Client()
        other_client.force_login(user)
        membership = AccountSession.objects.create(
            group=group,
            user=user,
            session_key=other_client.session.session_key,
        )
        return other_client, membership

    def test_current_account_is_enrolled_and_returned(self):
        self.enroll(self.client, self.user1)

        response = self.client.get(reverse("account_sessions"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        accounts = response.json()["accounts"]
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["id"], self.user1.pk)
        self.assertEqual(accounts[0]["username"], self.user1.username)
        self.assertTrue(accounts[0]["current"])
        self.assertIn("last_used", accounts[0])
        group_cookie = self.client.cookies[account_session_cookie_name()]
        self.assertTrue(group_cookie["httponly"])
        self.assertEqual(group_cookie["samesite"], settings.SESSION_COOKIE_SAMESITE)

    def test_switches_to_an_enrolled_valid_session(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)

        response = self.client.post(
            reverse("account_session_switch"),
            data=json.dumps({"user_id": self.user2.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            membership2.session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user2.pk)
        self.assertIn("account_switched=1", response.json()["redirect_url"])
        self.assertNotIn("account_switch_reason", response.json()["redirect_url"])

    def test_rejects_a_stale_tab_after_another_tab_switches_user(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = membership2.session_key

        response = self.client.get(
            reverse("account_sessions"),
            HTTP_X_PAPERLESS_USER_ID=str(self.user1.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["code"], "account_session_changed")

    def test_manual_logout_activates_the_most_recent_remaining_account(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)
        membership2.last_used = timezone.now() + timedelta(seconds=1)
        membership2.save(update_fields=("last_used",))

        response = self.client.get(reverse("account_logout"))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            membership2.session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user2.pk)
        self.assertFalse(group.account_sessions.filter(user=self.user1).exists())
        self.assertTrue(
            Session.objects.filter(session_key=membership2.session_key).exists(),
        )
        self.assertIn("account_switch_reason=logout", response["Location"])

    def test_api_logout_activates_the_most_recent_remaining_account(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)

        response = self.client.post(reverse("account_session_logout_current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            membership2.session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user2.pk)
        self.assertFalse(group.account_sessions.filter(user=self.user1).exists())
        self.assertIn(
            "account_switch_reason=logout",
            response.json()["redirect_url"],
        )

    def test_removing_current_account_activates_a_remaining_account(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)

        response = self.client.delete(
            reverse("account_session_remove", args=(self.user1.pk,)),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            membership2.session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user2.pk)
        self.assertFalse(group.account_sessions.filter(user=self.user1).exists())
        self.assertIn(
            "account_switch_reason=logout",
            response.json()["redirect_url"],
        )

    def test_removing_inactive_account_invalidates_its_session(self):
        group = self.enroll(self.client, self.user1)
        other_client, membership2 = self.add_session(group, self.user2)

        response = self.client.delete(
            reverse("account_session_remove", args=(self.user2.pk,)),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            Session.objects.filter(session_key=membership2.session_key).exists(),
        )
        self.assertNotIn(SESSION_KEY, other_client.session)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user1.pk)

    def test_group_cookie_alone_cannot_switch_an_unenrolled_session(self):
        group = self.enroll(self.client, self.user1)
        foreign_client = Client()
        foreign_client.force_login(self.user2)
        foreign_client.cookies[account_session_cookie_name()] = self.client.cookies[
            account_session_cookie_name()
        ].value

        response = foreign_client.get(reverse("account_logout"))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertNotIn(SESSION_KEY, foreign_client.session)
        self.assertTrue(group.account_sessions.filter(user=self.user1).exists())
        self.assertEqual(
            foreign_client.cookies[account_session_cookie_name()].value,
            "",
        )

    def test_group_cookie_alone_cannot_enroll_a_new_login(self):
        original_group = self.enroll(self.client, self.user1)
        original_group_cookie = self.client.cookies[
            account_session_cookie_name()
        ].value
        foreign_client = Client()
        foreign_client.cookies[account_session_cookie_name()] = original_group_cookie

        response = foreign_client.post(
            reverse("account_login"),
            data={
                "login": self.user2.username,
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertSetEqual(
            set(original_group.account_sessions.values_list("user_id", flat=True)),
            {self.user1.pk},
        )
        new_group = AccountSessionGroup.objects.exclude(pk=original_group.pk).get()
        self.assertSetEqual(
            set(new_group.account_sessions.values_list("user_id", flat=True)),
            {self.user2.pk},
        )
        self.assertNotEqual(
            foreign_client.cookies[account_session_cookie_name()].value,
            original_group_cookie,
        )

    def test_add_account_can_be_cancelled_without_losing_current_account(self):
        group = self.enroll(self.client, self.user1)
        original_session_key = self.client.session.session_key

        add_response = self.client.post(reverse("account_session_add"))
        anonymous_session_key = self.client.session.session_key

        self.assertEqual(add_response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(anonymous_session_key, original_session_key)
        self.assertIn(ADD_CHALLENGE_SESSION_KEY, self.client.session)

        response = self.client.post(reverse("account_switch_cancel"))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            original_session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user1.pk)
        self.assertFalse(
            Session.objects.filter(session_key=anonymous_session_key).exists(),
        )
        self.assertEqual(group.account_sessions.count(), 1)

    def test_mfa_login_can_be_cancelled_without_losing_account_sessions(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)
        user3 = User.objects.create_user(
            username="account-three",
            password=self.password,
        )
        totp_auth.TOTP.activate(user3, totp_auth.generate_totp_secret())
        original_session_key = self.client.session.session_key
        group_cookie = self.client.cookies[account_session_cookie_name()].value

        add_response = self.client.post(reverse("account_session_add"))
        anonymous_session_key = self.client.session.session_key
        login_response = self.client.post(
            add_response.json()["redirect_url"],
            data={
                "login": user3.username,
                "password": self.password,
                "next": reverse("account_switch_complete"),
            },
        )

        self.assertRedirects(
            login_response,
            reverse("mfa_authenticate"),
            fetch_redirect_response=False,
        )
        response = self.client.post(
            reverse("account_logout"),
            data={"next": reverse("account_login")},
        )

        self.assertRedirects(
            response,
            reverse("account_login"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.cookies[account_session_cookie_name()].value,
            group_cookie,
        )
        self.assertIn(ADD_CHALLENGE_SESSION_KEY, self.client.session)
        self.assertSetEqual(
            set(group.account_sessions.values_list("user_id", flat=True)),
            {self.user1.pk, self.user2.pk},
        )
        self.assertEqual(
            Session.objects.filter(
                session_key__in=(original_session_key, membership2.session_key),
            ).count(),
            2,
        )

        login_page = self.client.get(reverse("account_login"))
        self.assertContains(login_page, "Cancel and return to the current account")
        cancel_response = self.client.post(reverse("account_switch_cancel"))

        self.assertEqual(cancel_response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            original_session_key,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user1.pk)
        self.assertFalse(
            Session.objects.filter(session_key=anonymous_session_key).exists(),
        )
        self.assertSetEqual(
            set(group.account_sessions.values_list("user_id", flat=True)),
            {self.user1.pk, self.user2.pk},
        )

    def test_add_account_uses_existing_login_and_registers_new_user(self):
        group = self.enroll(self.client, self.user1)
        add_response = self.client.post(reverse("account_session_add"))

        login_response = self.client.post(
            add_response.json()["redirect_url"],
            data={
                "login": self.user2.username,
                "password": self.password,
                "next": reverse("account_switch_complete"),
            },
        )
        self.assertEqual(login_response.status_code, status.HTTP_302_FOUND)
        response = self.client.get(login_response["Location"])

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user2.pk)
        self.assertSetEqual(
            set(group.account_sessions.values_list("user_id", flat=True)),
            {self.user1.pk, self.user2.pk},
        )
        self.assertNotIn(ADD_CHALLENGE_SESSION_KEY, self.client.session)
        self.assertNotIn("account_switch_reason", response["Location"])

    def test_logout_all_invalidates_every_enrolled_session(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)
        session_keys = [self.client.session.session_key, membership2.session_key]

        response = self.client.post(reverse("account_session_logout_all"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(AccountSessionGroup.objects.filter(pk=group.pk).exists())
        self.assertFalse(Session.objects.filter(session_key__in=session_keys).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_expired_session_is_removed_from_list(self):
        group = self.enroll(self.client, self.user1)
        _, membership2 = self.add_session(group, self.user2)
        Session.objects.filter(session_key=membership2.session_key).delete()

        response = self.client.get(reverse("account_sessions"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["accounts"]), 1)
        self.assertFalse(AccountSession.objects.filter(pk=membership2.pk).exists())

    def test_switch_mutations_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        group = self.enroll(csrf_client, self.user1)
        self.add_session(group, self.user2)

        response = csrf_client.post(
            reverse("account_session_switch"),
            data=json.dumps({"user_id": self.user2.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(int(csrf_client.session[SESSION_KEY]), self.user1.pk)

    @override_settings(AUTO_LOGIN_USERNAME="account-one")
    def test_switching_is_disabled_for_auto_login(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("account_sessions"))
        switch_response = self.client.post(
            reverse("account_session_switch"),
            data=json.dumps({"user_id": self.user2.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.json(), {"enabled": False, "accounts": []})
        self.assertEqual(switch_response.status_code, status.HTTP_409_CONFLICT)
