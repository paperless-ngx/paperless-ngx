import os

import pytest
from django.test import TestCase

from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


# Only run if the environment is setup
# And the environment is not empty (forks, I think)
@pytest.mark.skipif(
    "PAPERLESS_MAIL_TEST_HOST" not in os.environ
    or not len(os.environ["PAPERLESS_MAIL_TEST_HOST"]),
    reason="Live server testing not enabled",
)
class TestMailLiveServer(TestCase):
    def setUp(self) -> None:
        self.mail_account_handler = MailAccountHandler()
        self.account = MailAccount.objects.create(
            name="test",
            imap_server=os.environ["PAPERLESS_MAIL_TEST_HOST"],
            username=os.environ["PAPERLESS_MAIL_TEST_USER"],
            password=os.environ["PAPERLESS_MAIL_TEST_PASSWD"],
            imap_port=993,
        )

        return super().setUp()

    def tearDown(self) -> None:
        self.account.delete()
        return super().tearDown()

    def test_process_non_gmail_server_flag(self):
        try:
            rule1 = MailRule.objects.create(
                name="testrule",
                account=self.account,
                action=MailRule.MailAction.FLAG,
            )

            self.mail_account_handler.handle_mail_account(self.account)

            rule1.delete()

        except MailError as e:
            self.fail(f"Failure: {e}")
        except Exception:
            pass

    def test_process_non_gmail_server_tag(self):
        try:
            rule2 = MailRule.objects.create(
                name="testrule",
                account=self.account,
                action=MailRule.MailAction.TAG,
            )

            self.mail_account_handler.handle_mail_account(self.account)

            rule2.delete()

        except MailError as e:
            self.fail(f"Failure: {e}")
        except Exception:
            pass
