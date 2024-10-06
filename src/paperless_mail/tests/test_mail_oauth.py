from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.oauth import generate_gmail_oauth_url
from paperless_mail.oauth import generate_outlook_oauth_url
from paperless_mail.oauth import get_oauth_callback_url
from paperless_mail.oauth import get_oauth_redirect_url


class TestMailOAuth(
    TestCase,
):
    def setUp(self) -> None:
        self.user = User.objects.create_user("testuser")
        self.client.force_login(self.user)
        self.mail_account_handler = MailAccountHandler()
        # Mock settings
        settings.OAUTH_CALLBACK_BASE_URL = "http://localhost:8000"
        settings.GMAIL_OAUTH_CLIENT_ID = "test_gmail_client_id"
        settings.GMAIL_OAUTH_CLIENT_SECRET = "test_gmail_client_secret"
        settings.OUTLOOK_OAUTH_CLIENT_ID = "test_outlook_client_id"
        settings.OUTLOOK_OAUTH_CLIENT_SECRET = "test_outlook_client_secret"
        super().setUp()

    def test_generate_paths(self):
        """
        GIVEN:
            - Mocked settings for OAuth callback and base URLs
        WHEN:
            - get_oauth_callback_url and get_oauth_redirect_url are called
        THEN:
            - Correct URLs are generated
        """
        # Callback URL
        with override_settings(OAUTH_CALLBACK_BASE_URL="http://paperless.example.com"):
            self.assertEqual(
                get_oauth_callback_url(),
                "http://paperless.example.com/api/oauth/callback/",
            )
        with override_settings(
            OAUTH_CALLBACK_BASE_URL=None,
            PAPERLESS_URL="http://paperless.example.com",
        ):
            self.assertEqual(
                get_oauth_callback_url(),
                "http://paperless.example.com/api/oauth/callback/",
            )
        with override_settings(
            OAUTH_CALLBACK_BASE_URL=None,
            PAPERLESS_URL="http://paperless.example.com",
            BASE_URL="/paperless/",
        ):
            self.assertEqual(
                get_oauth_callback_url(),
                "http://paperless.example.com/paperless/api/oauth/callback/",
            )

        # Redirect URL
        with override_settings(DEBUG=True):
            self.assertEqual(
                get_oauth_redirect_url(),
                "http://localhost:4200/mail",
            )
        with override_settings(DEBUG=False):
            self.assertEqual(
                get_oauth_redirect_url(),
                "/mail",
            )

    def test_generate_oauth_urls(self):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs
        WHEN:
            - generate_gmail_oauth_url and generate_outlook_oauth_url are called
        THEN:
            - Correct URLs are generated
        """
        self.assertEqual(
            "https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=test_gmail_client_id&redirect_uri=http://localhost:8000/api/oauth/callback/&scope=https://mail.google.com/&access_type=offline&prompt=consent",
            generate_gmail_oauth_url(),
        )
        self.assertEqual(
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?response_type=code&response_mode=query&client_id=test_outlook_client_id&redirect_uri=http://localhost:8000/api/oauth/callback/&scope=offline_access https://outlook.office.com/IMAP.AccessAsUser.All",
            generate_outlook_oauth_url(),
        )

    @mock.patch("httpx.post")
    def test_oauth_callback_view(self, mock_post):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called with a code and scope
        THEN:
            - Gmail mail account is created
        """

        mock_post.return_value.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }

        # Test Google OAuth callback
        response = self.client.get(
            "/api/oauth/callback/?code=test_code&scope=https://mail.google.com/",
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("oauth_success=1", response.url)
        mock_post.assert_called_once()
        self.assertTrue(
            MailAccount.objects.filter(imap_server="imap.gmail.com").exists(),
        )

        # Test Outlook OAuth callback
        response = self.client.get("/api/oauth/callback/?code=test_code")
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("oauth_success=1", response.url)
        self.assertTrue(
            MailAccount.objects.filter(imap_server="outlook.office365.com").exists(),
        )

    def test_oauth_callback_view_no_code(self):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called without a code
        THEN:
            - Error is logged
        """

        response = self.client.get(
            "/api/oauth/callback/",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            MailAccount.objects.filter(imap_server="imap.gmail.com").exists(),
        )
        self.assertFalse(
            MailAccount.objects.filter(imap_server="outlook.office365.com").exists(),
        )

    @mock.patch("httpx.post")
    def test_oauth_callback_view_error(self, mock_post):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called with an error
        THEN:
            - Error is logged
        """

        mock_post.return_value.json.return_value = {
            "error": "test_error",
        }

        response = self.client.get(
            "/api/oauth/callback/?code=test_code&scope=https://mail.google.com/",
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("oauth_success=0", response.url)
        mock_post.assert_called_once()
        self.assertFalse(
            MailAccount.objects.filter(imap_server="imap.gmail.com").exists(),
        )
        self.assertFalse(
            MailAccount.objects.filter(imap_server="outlook.office365.com").exists(),
        )

    @mock.patch("paperless_mail.mail.get_mailbox")
    @mock.patch("httpx.post")
    def test_refresh_token_on_handle_mail_account(self, mock_post, mock_get_mailbox):
        """
        GIVEN:
            - Mail account with refresh token and expiration
        WHEN:
            - handle_mail_account is called
        THEN:
            - Refresh token is called
        """

        mock_mailbox = mock.MagicMock()
        mock_get_mailbox.return_value.__enter__.return_value = mock_mailbox

        mail_account = MailAccount.objects.create(
            name="test_mail_account",
            username="test_username",
            imap_security=MailAccount.ImapSecurity.SSL,
            imap_port=993,
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        mock_post.return_value.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }

        self.mail_account_handler.handle_mail_account(mail_account)
        mock_post.assert_called_once()
