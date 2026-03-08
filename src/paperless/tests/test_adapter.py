import logging

import pytest
from allauth.account.adapter import get_adapter
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.http import HttpRequest
from django.urls import reverse
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture
from rest_framework.authtoken.models import Token

from paperless.adapter import DrfTokenStrategy


@pytest.mark.django_db
class TestCustomAccountAdapter:
    def test_is_open_for_signup(self, settings: SettingsWrapper) -> None:
        adapter = get_adapter()

        # With no accounts, signups should be allowed
        assert adapter.is_open_for_signup(None)

        User.objects.create_user("testuser")

        settings.ACCOUNT_ALLOW_SIGNUPS = True
        assert adapter.is_open_for_signup(None)

        settings.ACCOUNT_ALLOW_SIGNUPS = False
        assert not adapter.is_open_for_signup(None)

    def test_is_safe_url(self, settings: SettingsWrapper) -> None:
        request = HttpRequest()
        request.get_host = lambda: "example.com"
        with context.request_context(request):
            adapter = get_adapter()

            settings.ALLOWED_HOSTS = ["*"]
            # True because request host is same
            assert adapter.is_safe_url("https://example.com")
            # False despite wildcard because request host is different
            assert not adapter.is_safe_url("https://evil.com")

            settings.ALLOWED_HOSTS = ["example.com"]
            # True because request host is same
            assert adapter.is_safe_url("https://example.com")

            settings.ALLOWED_HOSTS = ["*", "example.com"]
            # False because request host is not in allowed hosts
            assert not adapter.is_safe_url("//evil.com")

    def test_pre_authenticate(
        self,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("allauth.core.internal.ratelimit.consume", return_value=True)
        adapter = get_adapter()
        request = HttpRequest()
        request.get_host = lambda: "example.com"

        settings.DISABLE_REGULAR_LOGIN = False
        adapter.pre_authenticate(request)

        settings.DISABLE_REGULAR_LOGIN = True
        with pytest.raises(ValidationError):
            adapter.pre_authenticate(request)

    def test_get_reset_password_from_key_url(self, settings: SettingsWrapper) -> None:
        request = HttpRequest()
        request.get_host = lambda: "foo.org"
        with context.request_context(request):
            adapter = get_adapter()

            settings.PAPERLESS_URL = None
            settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
            expected_url = f"https://foo.org{reverse('account_reset_password_from_key', kwargs={'uidb36': 'UID', 'key': 'KEY'})}"
            assert adapter.get_reset_password_from_key_url("UID-KEY") == expected_url

            settings.PAPERLESS_URL = "https://bar.com"
            expected_url = f"https://bar.com{reverse('account_reset_password_from_key', kwargs={'uidb36': 'UID', 'key': 'KEY'})}"
            assert adapter.get_reset_password_from_key_url("UID-KEY") == expected_url

    def test_save_user_adds_groups(
        self,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        settings.ACCOUNT_DEFAULT_GROUPS = ["group1", "group2"]
        Group.objects.create(name="group1")
        user = User.objects.create_user("testuser")
        adapter = get_adapter()
        form = mocker.MagicMock(
            cleaned_data={
                "username": "testuser",
                "email": "user@example.com",
            },
        )

        user = adapter.save_user(HttpRequest(), user, form, commit=True)

        assert user.groups.count() == 1
        assert user.groups.filter(name="group1").exists()
        assert not user.groups.filter(name="group2").exists()

    def test_fresh_install_save_creates_superuser(self, mocker: MockerFixture) -> None:
        adapter = get_adapter()
        form = mocker.MagicMock(
            cleaned_data={
                "username": "testuser",
                "email": "user@paperless-ngx.com",
            },
        )
        user = adapter.save_user(HttpRequest(), User(), form, commit=True)
        assert user.is_superuser

        form = mocker.MagicMock(
            cleaned_data={
                "username": "testuser2",
                "email": "user2@paperless-ngx.com",
            },
        )
        user2 = adapter.save_user(HttpRequest(), User(), form, commit=True)
        assert not user2.is_superuser


class TestCustomSocialAccountAdapter:
    @pytest.mark.django_db
    def test_is_open_for_signup(self, settings: SettingsWrapper) -> None:
        adapter = get_social_adapter()

        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = True
        assert adapter.is_open_for_signup(None, None)

        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = False
        assert not adapter.is_open_for_signup(None, None)

    def test_get_connect_redirect_url(self) -> None:
        adapter = get_social_adapter()
        assert adapter.get_connect_redirect_url(None, None) == reverse("base")

    @pytest.mark.django_db
    def test_save_user_adds_groups(
        self,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        settings.SOCIAL_ACCOUNT_DEFAULT_GROUPS = ["group1", "group2"]
        Group.objects.create(name="group1")
        adapter = get_social_adapter()
        user = User.objects.create_user("testuser")
        sociallogin = mocker.MagicMock(user=user)

        user = adapter.save_user(HttpRequest(), sociallogin, None)

        assert user.groups.count() == 1
        assert user.groups.filter(name="group1").exists()
        assert not user.groups.filter(name="group2").exists()

    def test_error_logged_on_authentication_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        adapter = get_social_adapter()
        with caplog.at_level(logging.INFO, logger="paperless.auth"):
            adapter.on_authentication_error(
                HttpRequest(),
                provider="test-provider",
                error="Error",
                exception="Test authentication error",
            )
        assert any("Test authentication error" in msg for msg in caplog.messages)


@pytest.mark.django_db
class TestDrfTokenStrategy:
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

        assert token_key is not None
        assert Token.objects.filter(user=user).exists()
        assert token_key == Token.objects.get(user=user).key

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

        assert token_key == existing_token.key
        assert Token.objects.filter(user=user).count() == 1

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

        assert token_key is None
        assert Token.objects.count() == 0
