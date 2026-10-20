import time

from allauth.mfa import app_settings as mfa_settings
from allauth.mfa.totp.internal import auth as totp_auth
from django.test import TestCase
from django.urls import reverse

from paperless_testing.factories import UserFactory


class TestAdminAuth(TestCase):
    def test_admin_login_redirects_to_allauth(self):
        user = UserFactory(staff=True, password="testpassword")
        admin_url = reverse("admin:index")
        login_url = reverse("admin:login")
        expected_url = f"{reverse('account_login')}?next={admin_url}"

        response = self.client.get(login_url, {"next": admin_url})
        self.assertRedirects(response, expected_url)

        response = self.client.post(
            login_url,
            {"username": user.username, "password": "testpassword", "next": admin_url},
        )
        self.assertRedirects(response, expected_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_access_requires_totp_for_enrolled_staff(self):
        user = UserFactory(staff=True, password="testpassword")
        secret = totp_auth.generate_totp_secret()
        totp_auth.TOTP.activate(user, secret)
        admin_url = reverse("admin:index")
        mfa_url = reverse("mfa_authenticate")

        response = self.client.post(
            reverse("account_login"),
            {"login": user.username, "password": "testpassword", "next": admin_url},
        )
        self.assertRedirects(response, mfa_url)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.get(admin_url),
            f"{reverse('admin:login')}?next={admin_url}",
            fetch_redirect_response=False,
        )

        response = self.client.post(mfa_url, {"code": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        code = totp_auth.format_hotp_value(
            totp_auth.hotp_value(secret, int(time.time()) // mfa_settings.TOTP_PERIOD),
        )
        response = self.client.post(mfa_url, {"code": code})
        self.assertRedirects(response, admin_url)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_staff_without_totp_can_still_log_in(self):
        user = UserFactory(staff=True, password="testpassword")
        admin_url = reverse("admin:index")

        response = self.client.post(
            reverse("account_login"),
            {"login": user.username, "password": "testpassword", "next": admin_url},
        )

        self.assertRedirects(response, admin_url)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
