from unittest import mock

from allauth.account.adapter import get_adapter
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.http import HttpRequest
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from paperless.adapter import DrfTokenStrategy


class TestCustomAccountAdapter(TestCase):
    def test_is_open_for_signup(self) -> None:
        adapter = get_adapter()

        # With no accounts, signups should be allowed
        self.assertTrue(adapter.is_open_for_signup(None))

        User.objects.create_user("testuser")

        # Test when ACCOUNT_ALLOW_SIGNUPS is True
        settings.ACCOUNT_ALLOW_SIGNUPS = True
        self.assertTrue(adapter.is_open_for_signup(None))

        # Test when ACCOUNT_ALLOW_SIGNUPS is False
        settings.ACCOUNT_ALLOW_SIGNUPS = False
        self.assertFalse(adapter.is_open_for_signup(None))

    def test_is_safe_url(self) -> None:
        request = HttpRequest()
        request.get_host = mock.Mock(return_value="example.com")
        with context.request_context(request):
            adapter = get_adapter()
            with override_settings(ALLOWED_HOSTS=["*"]):
                # True because request host is same
                url = "https://example.com"
                self.assertTrue(adapter.is_safe_url(url))

            url = "https://evil.com"
            # False despite wildcard because request host is different
            self.assertFalse(adapter.is_safe_url(url))

            settings.ALLOWED_HOSTS = ["example.com"]
            url = "https://example.com"
            # True because request host is same
            self.assertTrue(adapter.is_safe_url(url))

            settings.ALLOWED_HOSTS = ["*", "example.com"]
            url = "//evil.com"
            # False because request host is not in allowed hosts
            self.assertFalse(adapter.is_safe_url(url))

    @mock.patch("allauth.core.internal.ratelimit.consume", return_value=True)
    def test_pre_authenticate(self, mock_consume) -> None:
        adapter = get_adapter()
        request = HttpRequest()
        request.get_host = mock.Mock(return_value="example.com")

        settings.DISABLE_REGULAR_LOGIN = False
        adapter.pre_authenticate(request)

        settings.DISABLE_REGULAR_LOGIN = True
        with self.assertRaises(ValidationError):
            adapter.pre_authenticate(request)

    def test_get_reset_password_from_key_url(self) -> None:
        request = HttpRequest()
        request.get_host = mock.Mock(return_value="foo.org")
        with context.request_context(request):
            adapter = get_adapter()

            # Test when PAPERLESS_URL is None
            expected_url = f"https://foo.org{reverse('account_reset_password_from_key', kwargs={'uidb36': 'UID', 'key': 'KEY'})}"
            self.assertEqual(
                adapter.get_reset_password_from_key_url("UID-KEY"),
                expected_url,
            )

            # Test when PAPERLESS_URL is not None
            with override_settings(PAPERLESS_URL="https://bar.com"):
                expected_url = f"https://bar.com{reverse('account_reset_password_from_key', kwargs={'uidb36': 'UID', 'key': 'KEY'})}"
                self.assertEqual(
                    adapter.get_reset_password_from_key_url("UID-KEY"),
                    expected_url,
                )

    @override_settings(ACCOUNT_DEFAULT_GROUPS=["group1", "group2"])
    def test_save_user_adds_groups(self) -> None:
        Group.objects.create(name="group1")
        user = User.objects.create_user("testuser")
        adapter = get_adapter()
        form = mock.Mock(
            cleaned_data={
                "username": "testuser",
                "email": "user@example.com",
            },
        )

        user = adapter.save_user(HttpRequest(), user, form, commit=True)

        self.assertEqual(user.groups.count(), 1)
        self.assertTrue(user.groups.filter(name="group1").exists())
        self.assertFalse(user.groups.filter(name="group2").exists())

    def test_fresh_install_save_creates_superuser(self) -> None:
        adapter = get_adapter()
        form = mock.Mock(
            cleaned_data={
                "username": "testuser",
                "email": "user@paperless-ngx.com",
            },
        )
        user = adapter.save_user(HttpRequest(), User(), form, commit=True)
        self.assertTrue(user.is_superuser)

        # Next time, it should not create a superuser
        form = mock.Mock(
            cleaned_data={
                "username": "testuser2",
                "email": "user2@paperless-ngx.com",
            },
        )
        user2 = adapter.save_user(HttpRequest(), User(), form, commit=True)
        self.assertFalse(user2.is_superuser)


class TestCustomSocialAccountAdapter(TestCase):
    def test_is_open_for_signup(self) -> None:
        adapter = get_social_adapter()

        # Test when SOCIALACCOUNT_ALLOW_SIGNUPS is True
        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = True
        self.assertTrue(adapter.is_open_for_signup(None, None))

        # Test when SOCIALACCOUNT_ALLOW_SIGNUPS is False
        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = False
        self.assertFalse(adapter.is_open_for_signup(None, None))

    def test_get_connect_redirect_url(self) -> None:
        adapter = get_social_adapter()
        request = None
        socialaccount = None

        # Test the default URL
        expected_url = reverse("base")
        self.assertEqual(
            adapter.get_connect_redirect_url(request, socialaccount),
            expected_url,
        )

    @override_settings(SOCIAL_ACCOUNT_DEFAULT_GROUPS=["group1", "group2"])
    def test_save_user_adds_groups(self) -> None:
        Group.objects.create(name="group1")
        adapter = get_social_adapter()
        request = HttpRequest()
        user = User.objects.create_user("testuser")
        sociallogin = mock.Mock(
            user=user,
        )

        user = adapter.save_user(request, sociallogin, None)

        self.assertEqual(user.groups.count(), 1)
        self.assertTrue(user.groups.filter(name="group1").exists())
        self.assertFalse(user.groups.filter(name="group2").exists())

    def test_error_logged_on_authentication_error(self) -> None:
        adapter = get_social_adapter()
        request = HttpRequest()
        with self.assertLogs("paperless.auth", level="INFO") as log_cm:
            adapter.on_authentication_error(
                request,
                provider="test-provider",
                error="Error",
                exception="Test authentication error",
            )
        self.assertTrue(
            any("Test authentication error" in message for message in log_cm.output),
        )


class TestDrfTokenStrategy(TestCase):
    def test_create_access_token_creates_new_token(self) -> None:
        """
        GIVEN:
            - A user with no existing DRF token
        WHEN:
            - create_access_token is called
        THEN:
            - A new token is created and its key is returned
        """

        user = User.objects.create_user("testuser")
        request = HttpRequest()
        request.user = user

        strategy = DrfTokenStrategy()
        token_key = strategy.create_access_token(request)

        # Verify a token was created
        self.assertIsNotNone(token_key)
        self.assertTrue(Token.objects.filter(user=user).exists())

        # Verify the returned key matches the created token
        token = Token.objects.get(user=user)
        self.assertEqual(token_key, token.key)

    def test_create_access_token_returns_existing_token(self) -> None:
        """
        GIVEN:
            - A user with an existing DRF token
        WHEN:
            - create_access_token is called again
        THEN:
            - The same token key is returned (no new token created)
        """

        user = User.objects.create_user("testuser")
        existing_token = Token.objects.create(user=user)

        request = HttpRequest()
        request.user = user

        strategy = DrfTokenStrategy()
        token_key = strategy.create_access_token(request)

        # Verify the existing token key is returned
        self.assertEqual(token_key, existing_token.key)

        # Verify only one token exists (no duplicate created)
        self.assertEqual(Token.objects.filter(user=user).count(), 1)

    def test_create_access_token_returns_none_for_unauthenticated_user(self) -> None:
        """
        GIVEN:
            - An unauthenticated request
        WHEN:
            - create_access_token is called
        THEN:
            - None is returned and no token is created
        """

        request = HttpRequest()
        request.user = AnonymousUser()

        strategy = DrfTokenStrategy()
        token_key = strategy.create_access_token(request)

        self.assertIsNone(token_key)
        self.assertEqual(Token.objects.count(), 0)
