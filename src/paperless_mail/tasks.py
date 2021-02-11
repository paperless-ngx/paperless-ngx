import logging

from paperless_mail.mail import MailAccountHandler, MailError
from paperless_mail.models import MailAccount


logger = logging.getLogger("paperless.mail.tasks")


def process_mail_accounts():
    total_new_documents = 0
    for account in MailAccount.objects.all():
        try:
            total_new_documents += MailAccountHandler().handle_mail_account(
                account)
        except MailError:
            logger.exception(f"Error while processing mail account {account}")

    if total_new_documents > 0:
        return f"Added {total_new_documents} document(s)."
    else:
        return "No new documents were added."


def process_mail_account(name):
    try:
        account = MailAccount.objects.get(name=name)
        MailAccountHandler().handle_mail_account(account)
    except MailAccount.DoesNotExist:
        logger.error(f"Unknown mail acccount: {name}")
