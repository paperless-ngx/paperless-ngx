import asyncio
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import OAuth2Token
from httpx_oauth.oauth2 import RefreshTokenError

from paperless_mail.models import MailAccount


class PaperlessMailOAuth2Manager:
    def __init__(self):
        self._gmail_client = None
        self._outlook_client = None

    @property
    def gmail_client(self) -> GoogleOAuth2:
        if self._gmail_client is None:
            self._gmail_client = GoogleOAuth2(
                settings.GMAIL_OAUTH_CLIENT_ID,
                settings.GMAIL_OAUTH_CLIENT_SECRET,
            )
        return self._gmail_client

    @property
    def outlook_client(self) -> MicrosoftGraphOAuth2:
        if self._outlook_client is None:
            self._outlook_client = MicrosoftGraphOAuth2(
                settings.OUTLOOK_OAUTH_CLIENT_ID,
                settings.OUTLOOK_OAUTH_CLIENT_SECRET,
            )
        return self._outlook_client

    @property
    def oauth_callback_url(self) -> str:
        return f"{settings.OAUTH_CALLBACK_BASE_URL if settings.OAUTH_CALLBACK_BASE_URL is not None else settings.PAPERLESS_URL}{settings.BASE_URL}api/oauth/callback/"

    @property
    def oauth_redirect_url(self) -> str:
        return f"{'http://localhost:4200/' if settings.DEBUG else settings.BASE_URL}mail"  # e.g. "http://localhost:4200/mail" or "/mail"

    def get_gmail_authorization_url(self) -> str:
        return asyncio.run(
            self.gmail_client.get_authorization_url(
                redirect_uri=self.oauth_callback_url,
                scope=["https://mail.google.com/"],
                extras_params={"prompt": "consent", "access_type": "offline"},
            ),
        )

    def get_outlook_authorization_url(self) -> str:
        return asyncio.run(
            self.outlook_client.get_authorization_url(
                redirect_uri=self.oauth_callback_url,
                scope=[
                    "offline_access",
                    "https://outlook.office.com/IMAP.AccessAsUser.All",
                ],
            ),
        )

    def get_gmail_access_token(self, code: str) -> OAuth2Token:
        return asyncio.run(
            self.gmail_client.get_access_token(
                code=code,
                redirect_uri=self.oauth_callback_url,
            ),
        )

    def get_outlook_access_token(self, code: str) -> OAuth2Token:
        return asyncio.run(
            self.outlook_client.get_access_token(
                code=code,
                redirect_uri=self.oauth_callback_url,
            ),
        )

    def refresh_account_oauth_token(self, account: MailAccount) -> bool:
        """
        Refreshes the oauth token for the given mail account.
        """
        logger = logging.getLogger("paperless_mail")
        logger.debug(f"Attempting to refresh oauth token for account {account}")
        try:
            result: OAuth2Token
            if account.account_type == MailAccount.MailAccountType.GMAIL_OAUTH:
                result = asyncio.run(
                    self.gmail_client.refresh_token(
                        refresh_token=account.refresh_token,
                    ),
                )
            elif account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH:
                result = asyncio.run(
                    self.outlook_client.refresh_token(
                        refresh_token=account.refresh_token,
                    ),
                )
            account.password = result["access_token"]
            account.expiration = timezone.now() + timedelta(
                seconds=result["expires_in"],
            )
            account.save()
            logger.debug(f"Successfully refreshed oauth token for account {account}")
            return True
        except RefreshTokenError as e:
            logger.error(f"Failed to refresh oauth token for account {account}: {e}")
            return False
