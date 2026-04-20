from collections.abc import Generator

import pytest

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.tests.factories import MailAccountFactory


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
