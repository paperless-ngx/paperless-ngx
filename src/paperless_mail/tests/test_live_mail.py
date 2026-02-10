import pytest

from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


@pytest.mark.live
@pytest.mark.greenmail
@pytest.mark.django_db
class TestMailGreenmail:
    """
    Mail tests using local Greenmail server
    """

    def test_process_flag(
        self,
        mail_account_handler: MailAccountHandler,
        greenmail_mail_account: MailAccount,
    ) -> None:
        """
        Test processing mail with FLAG action.
        """
        rule = MailRule.objects.create(
            name="testrule",
            account=greenmail_mail_account,
            action=MailRule.MailAction.FLAG,
        )

        try:
            mail_account_handler.handle_mail_account(greenmail_mail_account)
        except MailError as e:
            pytest.fail(f"Failure: {e}")
        finally:
            rule.delete()

    def test_process_tag(
        self,
        mail_account_handler: MailAccountHandler,
        greenmail_mail_account: MailAccount,
    ) -> None:
        """
        Test processing mail with TAG action.
        """
        rule = MailRule.objects.create(
            name="testrule",
            account=greenmail_mail_account,
            action=MailRule.MailAction.TAG,
            action_parameter="TestTag",
        )

        try:
            mail_account_handler.handle_mail_account(greenmail_mail_account)
        except MailError as e:
            pytest.fail(f"Failure: {e}")
        finally:
            rule.delete()
