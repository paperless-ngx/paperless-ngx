import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from paperless_mail.models import MailAccount

# Gmail setup guide: https://postmansmtp.com/how-to-configure-post-smtp-with-gmailgsuite-using-oauth/
# Outlok setup guide: https://medium.com/@manojkumardhakad/python-read-and-send-outlook-mail-using-oauth2-token-and-graph-api-53de606ecfa1
GMAIL_OAUTH_ENDPOINT_TOKEN = "https://accounts.google.com/o/oauth2/token"
GMAIL_OAUTH_ENDPOINT_AUTH = "https://accounts.google.com/o/oauth2/auth"
OUTLOOK_OAUTH_ENDPOINT_TOKEN = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/token"
)
OUTLOOK_OAUTH_ENDPOINT_AUTH = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
)


def get_oauth_callback_url() -> str:
    return f"{settings.OAUTH_CALLBACK_BASE_URL if settings.OAUTH_CALLBACK_BASE_URL is not None else settings.PAPERLESS_URL}{settings.BASE_URL}api/oauth/callback/"


def get_oauth_redirect_url() -> str:
    return f"{'http://localhost:4200/' if settings.DEBUG else settings.BASE_URL}mail"  # e.g. "http://localhost:4200/mail" or "/mail"


def generate_gmail_oauth_url() -> str:
    response_type = "code"
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    redirect_uri = get_oauth_callback_url()
    scope = "https://mail.google.com/"
    access_type = "offline"
    url = f"{GMAIL_OAUTH_ENDPOINT_AUTH}?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&access_type={access_type}&prompt=consent"
    return url


def generate_outlook_oauth_url() -> str:
    response_type = "code"
    client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
    redirect_uri = get_oauth_callback_url()
    scope = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"
    url = f"{OUTLOOK_OAUTH_ENDPOINT_AUTH}?response_type={response_type}&response_mode=query&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    return url


def generate_gmail_oauth_token_request_data(code: str) -> dict:
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
    scope = "https://mail.google.com/"

    return {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
        "redirect_uri": get_oauth_callback_url(),
        "grant_type": "authorization_code",
    }


def generate_outlook_oauth_token_request_data(code: str) -> dict:
    client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
    client_secret = settings.OUTLOOK_OAUTH_CLIENT_SECRET
    scope = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"

    return {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
        "redirect_uri": get_oauth_callback_url(),
        "grant_type": "authorization_code",
    }


def refresh_oauth_token(account: MailAccount) -> bool:
    """
    Refreshes the oauth token for the given mail account.
    """
    logger = logging.getLogger("paperless_mail")
    logger.debug(f"Attempting to refresh oauth token for account {account}")
    if not account.refresh_token:
        logger.error(f"Account {account}: No refresh token available.")
        return False

    if account.account_type == MailAccount.MailAccountType.GMAIL_OAUTH:
        url = GMAIL_OAUTH_ENDPOINT_TOKEN
        data = {
            "client_id": settings.GMAIL_OAUTH_CLIENT_ID,
            "client_secret": settings.GMAIL_OAUTH_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        }
    elif account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH:
        url = OUTLOOK_OAUTH_ENDPOINT_TOKEN
        data = {
            "client_id": settings.OUTLOOK_OAUTH_CLIENT_ID,
            "client_secret": settings.OUTLOOK_OAUTH_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        }

    response = httpx.post(
        url=url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = response.json()
    if response.status_code < 400 and "access_token" in data:
        account.password = data["access_token"]
        account.expiration = timezone.now() + timedelta(
            seconds=data["expires_in"],
        )
        account.save()
        logger.debug(f"Successfully refreshed oauth token for account {account}")
        return True
    else:
        logger.error(
            f"Failed to refresh oauth token for account {account}: {response}",
        )
        return False
