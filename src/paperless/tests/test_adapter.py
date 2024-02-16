from unittest import mock

from allauth.account.adapter import get_adapter
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from django.conf import settings
from django.http import HttpRequest
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse


class TestCustomAccountAdapter(TestCase):
    def test_is_open_for_signup(self):
        adapter = get_adapter()

        # Test when ACCOUNT_ALLOW_SIGNUPS is True
        settings.ACCOUNT_ALLOW_SIGNUPS = True
        self.assertTrue(adapter.is_open_for_signup(None))

        # Test when ACCOUNT_ALLOW_SIGNUPS is False
        settings.ACCOUNT_ALLOW_SIGNUPS = False
        self.assertFalse(adapter.is_open_for_signup(None))

    def test_is_safe_url(self):
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


class TestCustomSocialAccountAdapter(TestCase):
    def test_is_open_for_signup(self):
        adapter = get_social_adapter()

        # Test when SOCIALACCOUNT_ALLOW_SIGNUPS is True
        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = True
        self.assertTrue(adapter.is_open_for_signup(None, None))

        # Test when SOCIALACCOUNT_ALLOW_SIGNUPS is False
        settings.SOCIALACCOUNT_ALLOW_SIGNUPS = False
        self.assertFalse(adapter.is_open_for_signup(None, None))

    def test_get_connect_redirect_url(self):
        adapter = get_social_adapter()
        request = None
        socialaccount = None

        # Test the default URL
        expected_url = reverse("base")
        self.assertEqual(
            adapter.get_connect_redirect_url(request, socialaccount),
            expected_url,
        )
