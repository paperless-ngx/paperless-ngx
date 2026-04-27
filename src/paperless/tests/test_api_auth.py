import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse
from rest_framework import status


class TestApiAuthViews(TestCase):
    def test_api_auth_login_uses_allauth_login_view(self):
        response = self.client.get(reverse("rest_framework:login"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTemplateUsed(response, "account/login.html")

    def test_api_auth_login_uses_same_view_as_account_login(self):
        api_match = resolve("/api/auth/login/")
        account_match = resolve("/accounts/login/")

        self.assertIs(api_match.func.view_class, account_match.func.view_class)

    @override_settings(DISABLE_REGULAR_LOGIN=True)
    def test_api_auth_login_respects_disable_regular_login(self):
        username = f"testuser-{uuid.uuid4().hex}"
        User.objects.create_user(
            username=username,
            password="testpassword",
        )

        response = self.client.post(
            reverse("rest_framework:login"),
            data={
                "login": username,
                "password": "testpassword",
                "next": "/api/documents/",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTemplateUsed(response, "account/login.html")
        self.assertContains(response, "Regular login is disabled")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_api_auth_logout_uses_named_route(self):
        self.assertEqual(reverse("rest_framework:login"), "/api/auth/login/")
        self.assertEqual(reverse("rest_framework:logout"), "/api/auth/logout/")
