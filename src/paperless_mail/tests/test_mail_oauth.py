from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount


class TestMailOAuth(
    TestCase,
):
    def setUp(self) -> None:
        self.user = User.objects.create_user("testuser")
        self.client.force_login(self.user)
        self.mail_account_handler = MailAccountHandler()
        # Mock settings
        settings.GMAIL_OAUTH_CLIENT_ID = "test_gmail_client_id"
        settings.GMAIL_OAUTH_CLIENT_SECRET = "test_gmail_client_secret"
        settings.OUTLOOK_OAUTH_CLIENT_ID = "test_outlook_client_id"
        settings.OUTLOOK_OAUTH_CLIENT_SECRET = "test_outlook_client_secret"
        super().setUp()

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
            account_type=MailAccount.MailAccountType.GMAIL,
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
