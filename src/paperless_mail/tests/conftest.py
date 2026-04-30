from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
import pytest_mock
from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.tests.factories import MailAccountFactory

if TYPE_CHECKING:
    from paperless_mail.tests.test_mail import BogusMailBox


@pytest.fixture()
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


@pytest.fixture()
def mail_account_handler() -> MailAccountHandler:
    return MailAccountHandler()


@pytest.fixture()
def mail_user(
    db: None,
    django_user_model,
    client: Client,
):
    """
    Create a user with the `add_mailaccount` permission and log them in via
    the test client. Returned so tests can mutate permissions if needed.
    """
    from django.contrib.auth.models import Permission

    user = django_user_model.objects.create_user("testuser")
    user.user_permissions.add(
        *Permission.objects.filter(codename__in=["add_mailaccount"]),
    )
    user.save()
    client.force_login(user)
    return user


@pytest.fixture()
def oauth_settings(settings):
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


@pytest.fixture()
def mail_mocker(db: None):
    """
    Provides a MailMocker instance with its `MailBox` and
    `queue_consumption_tasks` patches active. Cleanups registered via
    TestCase.addCleanup are run on teardown by calling doCleanups().
    """
    from paperless_mail.tests.test_mail import MailMocker

    mocker = MailMocker()
    mocker.setUp()
    try:
        yield mocker
    finally:
        mocker.doCleanups()


@pytest.fixture()
def mail_api_user(
    db: None,
    django_user_model: type[User],
) -> User:
    """
    Fully-permissioned (regular) user used by the mail API tests.

    Has every model-level permission but is NOT a Django superuser/staff:
    the owner-aware filtering and bulk_delete permission tests rely on
    django-guardian's object-level checks, and `is_superuser` short-circuits
    those checks. The name avoids `admin` to make this distinction explicit.
    """
    from django.contrib.auth.models import Permission

    user = django_user_model.objects.create_user(username="mail_api_user")
    user.user_permissions.add(*Permission.objects.all())
    user.save()
    return user


@pytest.fixture()
def mail_api_client(mail_api_user: User) -> APIClient:
    """
    DRF APIClient force-authenticated as `mail_api_user` and pinned to API v10
    via the Accept header (matches `documents/tests/conftest.py:admin_client`).
    """
    client = APIClient()
    client.force_authenticate(user=mail_api_user)
    client.credentials(HTTP_ACCEPT="application/json; version=10")
    return client


@pytest.fixture()
def bogus_mailbox(mocker: pytest_mock.MockerFixture) -> "BogusMailBox":
    """
    Patch `paperless_mail.mail.MailBox` with a `BogusMailBox` instance so the
    `/api/mail_accounts/test/` endpoint can run without a real IMAP server.
    Returns the bogus mailbox so tests can introspect/manipulate it.
    """
    from paperless_mail.tests.test_mail import BogusMailBox

    mailbox = BogusMailBox()
    mock_mailbox_cls = mocker.patch("paperless_mail.mail.MailBox")
    mock_mailbox_cls.return_value = mailbox
    return mailbox
