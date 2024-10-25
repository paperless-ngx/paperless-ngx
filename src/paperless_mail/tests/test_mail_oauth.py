from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from httpx_oauth.oauth2 import GetAccessTokenError
from httpx_oauth.oauth2 import RefreshTokenError
from rest_framework import status

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.oauth import PaperlessMailOAuth2Manager


class TestMailOAuth(
    TestCase,
):
    def setUp(self) -> None:
        self.user = User.objects.create_user("testuser")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "add_mailaccount",
                ],
            ),
        )
        self.user.save()
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
        oauth_manager = PaperlessMailOAuth2Manager()
        with override_settings(OAUTH_CALLBACK_BASE_URL="http://paperless.example.com"):
            self.assertEqual(
                oauth_manager.oauth_callback_url,
                "http://paperless.example.com/api/oauth/callback/",
            )
        with override_settings(
            OAUTH_CALLBACK_BASE_URL=None,
            PAPERLESS_URL="http://paperless.example.com",
        ):
            self.assertEqual(
                oauth_manager.oauth_callback_url,
                "http://paperless.example.com/api/oauth/callback/",
            )
        with override_settings(
            OAUTH_CALLBACK_BASE_URL=None,
            PAPERLESS_URL="http://paperless.example.com",
            BASE_URL="/paperless/",
        ):
            self.assertEqual(
                oauth_manager.oauth_callback_url,
                "http://paperless.example.com/paperless/api/oauth/callback/",
            )

        # Redirect URL
        with override_settings(DEBUG=True):
            self.assertEqual(
                oauth_manager.oauth_redirect_url,
                "http://localhost:4200/mail",
            )
        with override_settings(DEBUG=False):
            self.assertEqual(
                oauth_manager.oauth_redirect_url,
                "/mail",
            )

    @mock.patch(
        "paperless_mail.oauth.PaperlessMailOAuth2Manager.get_gmail_access_token",
    )
    @mock.patch(
        "paperless_mail.oauth.PaperlessMailOAuth2Manager.get_outlook_access_token",
    )
    def test_oauth_callback_view_success(
        self,
        mock_get_outlook_access_token,
        mock_get_gmail_access_token,
    ):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called with a code and scope
            - OAuth callback is called with a code and no scope
        THEN:
            - Gmail mail account is created
            - Outlook mail account is created
        """

        mock_get_gmail_access_token.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }
        mock_get_outlook_access_token.return_value = {
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
        mock_get_gmail_access_token.assert_called_once()
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

    @mock.patch("httpx_oauth.oauth2.BaseOAuth2.get_access_token")
    def test_oauth_callback_view_fails(self, mock_get_access_token):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called and get access token returns an error
        THEN:
            - No mail account is created
            - Error is logged
        """
        mock_get_access_token.side_effect = GetAccessTokenError("test_error")

        with self.assertLogs("paperless_mail", level="ERROR") as cm:
            # Test Google OAuth callback
            response = self.client.get(
                "/api/oauth/callback/?code=test_code&scope=https://mail.google.com/",
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertIn("oauth_success=0", response.url)
            self.assertFalse(
                MailAccount.objects.filter(imap_server="imap.gmail.com").exists(),
            )

            # Test Outlook OAuth callback
            response = self.client.get("/api/oauth/callback/?code=test_code")
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertIn("oauth_success=0", response.url)
            self.assertFalse(
                MailAccount.objects.filter(
                    imap_server="outlook.office365.com",
                ).exists(),
            )

            self.assertIn("Error getting access token: test_error", cm.output[0])

    def test_oauth_callback_view_insufficient_permissions(self):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
            - User without add_mailaccount permission
        WHEN:
            - OAuth callback is called
        THEN:
            - 400 bad request returned, no mail accounts are created
        """
        self.user.user_permissions.remove(
            *Permission.objects.filter(
                codename__in=[
                    "add_mailaccount",
                ],
            ),
        )
        self.user.save()

        response = self.client.get(
            "/api/oauth/callback/?code=test_code&scope=https://mail.google.com/",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            MailAccount.objects.filter(imap_server="imap.gmail.com").exists(),
        )
        self.assertFalse(
            MailAccount.objects.filter(imap_server="outlook.office365.com").exists(),
        )

    def test_oauth_callback_view_no_code(self):
        """
        GIVEN:
            - Mocked settings for Gmail and Outlook OAuth client IDs and secrets
        WHEN:
            - OAuth callback is called without a code
        THEN:
            - 400 bad request returned, no mail accounts are created
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

    @mock.patch("paperless_mail.mail.get_mailbox")
    @mock.patch(
        "httpx_oauth.oauth2.BaseOAuth2.refresh_token",
    )
    def test_refresh_token_on_handle_mail_account(
        self,
        mock_refresh_token,
        mock_get_mailbox,
    ):
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
            name="Test Gmail Mail Account",
            username="test_username",
            imap_security=MailAccount.ImapSecurity.SSL,
            imap_port=993,
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        mock_refresh_token.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }

        self.mail_account_handler.handle_mail_account(mail_account)
        mock_refresh_token.assert_called_once()
        mock_refresh_token.reset_mock()

        mock_refresh_token.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
        }
        outlook_mail_account = MailAccount.objects.create(
            name="Test Outlook Mail Account",
            username="test_username",
            imap_security=MailAccount.ImapSecurity.SSL,
            imap_port=993,
            account_type=MailAccount.MailAccountType.OUTLOOK_OAUTH,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        self.mail_account_handler.handle_mail_account(outlook_mail_account)
        mock_refresh_token.assert_called_once()

    @mock.patch("paperless_mail.mail.get_mailbox")
    @mock.patch(
        "httpx_oauth.oauth2.BaseOAuth2.refresh_token",
    )
    def test_refresh_token_on_handle_mail_account_fails(
        self,
        mock_refresh_token,
        mock_get_mailbox,
    ):
        """
        GIVEN:
            - Mail account with refresh token and expiration
        WHEN:
            - handle_mail_account is called
            - Refresh token is called but fails
        THEN:
            - Error is logged
            - 0 processed mails is returned
        """

        mock_mailbox = mock.MagicMock()
        mock_get_mailbox.return_value.__enter__.return_value = mock_mailbox

        mail_account = MailAccount.objects.create(
            name="Test Gmail Mail Account",
            username="test_username",
            imap_security=MailAccount.ImapSecurity.SSL,
            imap_port=993,
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        mock_refresh_token.side_effect = RefreshTokenError("test_error")

        with self.assertLogs("paperless_mail", level="ERROR") as cm:
            # returns 0 processed mails
            self.assertEqual(
                self.mail_account_handler.handle_mail_account(mail_account),
                0,
            )
            mock_refresh_token.assert_called_once()
            self.assertIn(
                f"Failed to refresh oauth token for account {mail_account}: test_error",
                cm.output[0],
            )
