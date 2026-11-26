import uuid
from unittest import mock

from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from paperless_testing.factories import UserFactory


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "NUM_PROXIES": 0,
    },
)
class TestTokenThrottle(TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(
            mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "5/min"}),
        )
        self.enterContext(
            mock.patch.object(
                ScopedRateThrottle,
                "cache",
                LocMemCache(uuid.uuid4().hex, {}),
            ),
        )

    def _request_token(self, forwarded_for, remote_addr="203.0.113.10"):
        return self.client.post(
            "/api/token/",
            {"username": "unknown", "password": "wrong"},
            HTTP_X_FORWARDED_FOR=forwarded_for,
            REMOTE_ADDR=remote_addr,
        )

    def test_untrusted_forwarded_for_cannot_bypass_limit(self):
        for attempt in range(5):
            response = self._request_token(f"198.51.100.{attempt}")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self._request_token("198.51.100.99")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "NUM_PROXIES": 1,
        },
    )
    def test_trusted_proxy_uses_client_address(self):
        for attempt in range(5):
            response = self._request_token(
                f"198.51.100.{attempt}, 192.0.2.20",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self._request_token("198.51.100.99, 192.0.2.20")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self._request_token("192.0.2.21")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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
        UserFactory(username=username, password="testpassword")

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
