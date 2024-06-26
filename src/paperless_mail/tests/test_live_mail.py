import os
import warnings

import pytest

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
@pytest.mark.django_db()
class TestMailLiveServer:
    def test_process_non_gmail_server_flag(
        self,
        mail_account_handler: MailAccountHandler,
        live_mail_account: MailAccount,
    ):
        try:
            rule1 = MailRule.objects.create(
                name="testrule",
                account=live_mail_account,
                action=MailRule.MailAction.FLAG,
            )

            mail_account_handler.handle_mail_account(live_mail_account)

            rule1.delete()

        except MailError as e:
            pytest.fail(f"Failure: {e}")
        except Exception as e:
            warnings.warn(f"Unhandled exception: {e}")

    def test_process_non_gmail_server_tag(
        self,
        mail_account_handler: MailAccountHandler,
        live_mail_account: MailAccount,
    ):
        try:
            rule2 = MailRule.objects.create(
                name="testrule",
                account=live_mail_account,
                action=MailRule.MailAction.TAG,
            )

            mail_account_handler.handle_mail_account(live_mail_account)

            rule2.delete()

        except MailError as e:
            pytest.fail(f"Failure: {e}")
        except Exception as e:
            warnings.warn(f"Unhandled exception: {e}")
