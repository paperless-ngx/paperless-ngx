from collections.abc import Generator

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import Client
from pytest_django.fixtures import SettingsWrapper

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.test_mail import MailMocker


@pytest.fixture
def greenmail_mail_account(db: None) -> Generator[MailAccount, None, None]:
    """
    Create a mail account configured for local Greenmail server.
    """
    account = MailAccountFactory(
        name="Greenmail Test",
        imap_server="localhost",
        imap_port=3143,
        imap_security=MailAccount.ImapSecurity.NONE,
        username="test@localhost",
        password="test",
    )
    yield account
    account.delete()


@pytest.fixture
def mail_account_handler() -> MailAccountHandler:
    return MailAccountHandler()


@pytest.fixture
def mail_user(db: None, django_user_model, client: Client) -> User:
    """
    Create a user with the `add_mailaccount` permission and log them in via
    the test client. Returned so tests can mutate permissions if needed.
    """
    user = django_user_model.objects.create_user("testuser")
    user.user_permissions.add(*Permission.objects.filter(codename="add_mailaccount"))
    client.force_login(user)
    return user


@pytest.fixture
def oauth_settings(settings: SettingsWrapper) -> SettingsWrapper:
    """
    Apply the OAuth callback / client-id settings the OAuth flow needs. Uses
    pytest-django's `settings` fixture so values are reverted automatically.
    """
    settings.OAUTH_CALLBACK_BASE_URL = "http://localhost:8000"
    settings.GMAIL_OAUTH_CLIENT_ID = "test_gmail_client_id"
    settings.GMAIL_OAUTH_CLIENT_SECRET = "test_gmail_client_secret"
    settings.OUTLOOK_OAUTH_CLIENT_ID = "test_outlook_client_id"
    settings.OUTLOOK_OAUTH_CLIENT_SECRET = "test_outlook_client_secret"
    return settings


@pytest.fixture
def mail_mocker(db: None) -> Generator[MailMocker, None, None]:
    """
    Provides a MailMocker instance with its `MailBox` and
    `queue_consumption_tasks` patches active. Cleanups registered via
    TestCase.addCleanup are run on teardown by calling doCleanups().
    """
    mocker = MailMocker()
    mocker.setUp()
    try:
        yield mocker
    finally:
        mocker.doCleanups()
