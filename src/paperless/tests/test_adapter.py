from allauth.account.adapter import get_adapter
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from django.conf import settings
from django.test import TestCase
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
