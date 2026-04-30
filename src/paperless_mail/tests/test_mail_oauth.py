from datetime import timedelta

import pytest
import pytest_mock
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from httpx_oauth.oauth2 import GetAccessTokenError
from httpx_oauth.oauth2 import RefreshTokenError
from pytest_django.fixtures import SettingsWrapper
from rest_framework import status

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.oauth import PaperlessMailOAuth2Manager
from paperless_mail.tests.factories import MailAccountFactory


@pytest.fixture()
def oauth_manager() -> PaperlessMailOAuth2Manager:
    return PaperlessMailOAuth2Manager()


@pytest.fixture()
def oauth_session(client: Client) -> Client:
    """Seed the test client session with a known oauth_state."""
    session = client.session
    session.update({"oauth_state": "test_state"})
    session.save()
    return client


class TestOAuthUrlGeneration:
    """OAuth callback / redirect URL construction by PaperlessMailOAuth2Manager."""

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            pytest.param(
                {"OAUTH_CALLBACK_BASE_URL": "http://paperless.example.com"},
                "http://paperless.example.com/api/oauth/callback/",
                id="callback-base-url-set",
            ),
            pytest.param(
                {
                    "OAUTH_CALLBACK_BASE_URL": None,
                    "PAPERLESS_URL": "http://paperless.example.com",
                },
                "http://paperless.example.com/api/oauth/callback/",
                id="falls-back-to-paperless-url",
            ),
            pytest.param(
                {
                    "OAUTH_CALLBACK_BASE_URL": None,
                    "PAPERLESS_URL": "http://paperless.example.com",
                    "BASE_URL": "/paperless/",
                },
                "http://paperless.example.com/paperless/api/oauth/callback/",
                id="respects-base-url-prefix",
            ),
        ],
    )
    def test_oauth_callback_url(
        self,
        settings: SettingsWrapper,
        oauth_manager: PaperlessMailOAuth2Manager,
        overrides: dict,
        expected: str,
    ) -> None:
        """
        GIVEN:
            - Various combinations of OAUTH_CALLBACK_BASE_URL, PAPERLESS_URL, and BASE_URL
        WHEN:
            - oauth_callback_url is read from the manager
        THEN:
            - The expected fully-qualified callback URL is produced
        """
        for key, value in overrides.items():
            setattr(settings, key, value)
        assert oauth_manager.oauth_callback_url == expected

    @pytest.mark.parametrize(
        ("debug", "expected"),
        [
            pytest.param(
                True,
                "http://localhost:4200/mail",
                id="debug-redirects-to-ng-dev",
            ),
            pytest.param(False, "/mail", id="prod-redirects-to-relative-path"),
        ],
    )
    def test_oauth_redirect_url(
        self,
        settings: SettingsWrapper,
        oauth_manager: PaperlessMailOAuth2Manager,
        debug: bool,  # noqa: FBT001
        expected: str,
    ) -> None:
        """
        GIVEN:
            - DEBUG is toggled on or off
        WHEN:
            - oauth_redirect_url is read from the manager
        THEN:
            - In DEBUG mode the Angular dev server URL is returned, otherwise a relative path
        """
        settings.DEBUG = debug
        assert oauth_manager.oauth_redirect_url == expected


@pytest.mark.django_db
class TestOAuthCallbackView:
    """End-to-end behavior of the /api/oauth/callback/ endpoint."""

    def test_no_code(
        self,
        client: Client,
        mail_user: User,
        oauth_settings: SettingsWrapper,
    ) -> None:
        """
        GIVEN:
            - OAuth client IDs and secrets configured
        WHEN:
            - The OAuth callback is called without a code parameter
        THEN:
            - 400 Bad Request is returned and no mail account is created
        """
        response = client.get("/api/oauth/callback/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not MailAccount.objects.filter(imap_server="imap.gmail.com").exists()
        assert not MailAccount.objects.filter(
            imap_server="outlook.office365.com",
        ).exists()

    def test_invalid_state(
        self,
        client: Client,
        mail_user: User,
        oauth_settings: SettingsWrapper,
    ) -> None:
        """
        GIVEN:
            - OAuth client IDs and secrets configured
        WHEN:
            - The OAuth callback is called with a state that does not match the session
        THEN:
            - 400 Bad Request is returned and no mail account is created
        """
        response = client.get(
            "/api/oauth/callback/?code=test_code&state=invalid_state",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not MailAccount.objects.filter(imap_server="imap.gmail.com").exists()
        assert not MailAccount.objects.filter(
            imap_server="outlook.office365.com",
        ).exists()

    def test_insufficient_permissions(
        self,
        client: Client,
        mail_user: User,
        oauth_settings: SettingsWrapper,
    ) -> None:
        """
        GIVEN:
            - OAuth client IDs and secrets configured
            - User without add_mailaccount permission
        WHEN:
            - The OAuth callback is called
        THEN:
            - 400 Bad Request is returned and no mail account is created
        """

        mail_user.user_permissions.remove(
            *Permission.objects.filter(codename__in=["add_mailaccount"]),
        )
        mail_user.save()

        response = client.get(
            "/api/oauth/callback/?code=test_code&scope=https://mail.google.com/",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not MailAccount.objects.filter(imap_server="imap.gmail.com").exists()
        assert not MailAccount.objects.filter(
            imap_server="outlook.office365.com",
        ).exists()

    @pytest.mark.parametrize(
        ("provider", "callback_query", "expected_imap"),
        [
            pytest.param(
                "gmail",
                "code=test_code&scope=https://mail.google.com/&state=test_state",
                "imap.gmail.com",
                id="gmail",
            ),
            pytest.param(
                "outlook",
                "code=test_code&state=test_state",
                "outlook.office365.com",
                id="outlook",
            ),
        ],
    )
    def test_success(
        self,
        client: Client,
        mail_user: User,
        oauth_settings: SettingsWrapper,
        oauth_session: Client,
        mocker: pytest_mock.MockerFixture,
        provider: str,
        callback_query: str,
        expected_imap: str,
    ) -> None:
        """
        GIVEN:
            - OAuth client IDs and secrets configured for Gmail and Outlook
            - A valid oauth_state seeded in the session
        WHEN:
            - The OAuth callback is called with a code and provider-specific scope
        THEN:
            - A redirect with oauth_success=1 is returned
            - The provider's access-token method is invoked
            - A mail account for the matching provider is created
        """
        token_payload = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }
        target = (
            "paperless_mail.oauth.PaperlessMailOAuth2Manager.get_gmail_access_token"
            if provider == "gmail"
            else "paperless_mail.oauth.PaperlessMailOAuth2Manager.get_outlook_access_token"
        )
        mocked = mocker.patch(target, return_value=token_payload)

        response = client.get(f"/api/oauth/callback/?{callback_query}")

        assert response.status_code == status.HTTP_302_FOUND
        assert "oauth_success=1" in response.url
        mocked.assert_called_once()
        assert MailAccount.objects.filter(imap_server=expected_imap).exists()

    @pytest.mark.parametrize(
        ("callback_query", "imap_server"),
        [
            pytest.param(
                "code=test_code&scope=https://mail.google.com/&state=test_state",
                "imap.gmail.com",
                id="gmail",
            ),
            pytest.param(
                "code=test_code&state=test_state",
                "outlook.office365.com",
                id="outlook",
            ),
        ],
    )
    def test_provider_error(
        self,
        client: Client,
        mail_user: User,
        oauth_settings: SettingsWrapper,
        oauth_session: Client,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
        callback_query: str,
        imap_server: str,
    ) -> None:
        """
        GIVEN:
            - OAuth client IDs and secrets configured
            - The provider's access-token endpoint raises GetAccessTokenError
        WHEN:
            - The OAuth callback is called with a code (Gmail or Outlook)
        THEN:
            - A redirect with oauth_success=0 is returned
            - No mail account is created
            - The failure is logged at ERROR level
        """
        mocker.patch(
            "httpx_oauth.oauth2.BaseOAuth2.get_access_token",
            side_effect=GetAccessTokenError("test_error"),
        )

        with caplog.at_level("ERROR", logger="paperless_mail"):
            response = client.get(f"/api/oauth/callback/?{callback_query}")

        assert response.status_code == status.HTTP_302_FOUND
        assert "oauth_success=0" in response.url
        assert not MailAccount.objects.filter(imap_server=imap_server).exists()
        assert any(
            "Error getting access token from OAuth provider" in record.message
            for record in caplog.records
        )


@pytest.mark.django_db
class TestRefreshTokenOnHandleMailAccount:
    """OAuth refresh-token flow exercised through MailAccountHandler.handle_mail_account."""

    @pytest.mark.parametrize(
        ("account_type", "name"),
        [
            pytest.param(
                MailAccount.MailAccountType.GMAIL_OAUTH,
                "Test Gmail",
                id="gmail",
            ),
            pytest.param(
                MailAccount.MailAccountType.OUTLOOK_OAUTH,
                "Test Outlook",
                id="outlook",
            ),
        ],
    )
    def test_refresh_token_called(
        self,
        mocker: pytest_mock.MockerFixture,
        mail_account_handler: MailAccountHandler,
        account_type: MailAccount.MailAccountType,
        name: str,
    ) -> None:
        """
        GIVEN:
            - An OAuth-backed mail account with a refresh token and an expired access token
        WHEN:
            - handle_mail_account is called
        THEN:
            - The OAuth refresh_token endpoint is invoked exactly once
        """
        mock_mailbox = mocker.MagicMock()
        mocker.patch(
            "paperless_mail.mail.get_mailbox",
        ).return_value.__enter__.return_value = mock_mailbox
        mock_refresh = mocker.patch(
            "httpx_oauth.oauth2.BaseOAuth2.refresh_token",
            return_value={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
            },
        )

        account = MailAccountFactory(
            name=name,
            username="test_username",
            account_type=account_type,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        mail_account_handler.handle_mail_account(account)
        mock_refresh.assert_called_once()

    def test_refresh_token_failure(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
        mail_account_handler: MailAccountHandler,
    ) -> None:
        """
        GIVEN:
            - An OAuth-backed mail account with a refresh token and an expired access token
            - The OAuth refresh_token endpoint raises RefreshTokenError
        WHEN:
            - handle_mail_account is called
        THEN:
            - 0 processed mails is returned
            - The failure is logged at ERROR level with the account context
        """
        mock_mailbox = mocker.MagicMock()
        mocker.patch(
            "paperless_mail.mail.get_mailbox",
        ).return_value.__enter__.return_value = mock_mailbox
        mock_refresh = mocker.patch(
            "httpx_oauth.oauth2.BaseOAuth2.refresh_token",
            side_effect=RefreshTokenError("test_error"),
        )

        account = MailAccountFactory(
            name="Test Gmail Mail Account",
            username="test_username",
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            is_token=True,
            refresh_token="test_refresh_token",
            expiration=timezone.now() - timedelta(days=1),
        )

        with caplog.at_level("ERROR", logger="paperless_mail"):
            result = mail_account_handler.handle_mail_account(account)

        assert result == 0
        mock_refresh.assert_called_once()
        assert any(
            f"Failed to refresh oauth token for account {account}: test_error"
            in record.message
            for record in caplog.records
        )
