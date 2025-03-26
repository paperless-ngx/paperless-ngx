import logging

from celery import shared_task

from edoc_mail.mail import MailAccountHandler
from edoc_mail.mail import MailError
from edoc_mail.models import MailAccount

logger = logging.getLogger("edoc.mail.tasks")


@shared_task
def process_mail_accounts():
    total_new_documents = 0
    for account in MailAccount.objects.all():
        try:
            total_new_documents += MailAccountHandler().handle_mail_account(account)
        except MailError:
            logger.exception(f"Error while processing mail account {account}")

    if total_new_documents > 0:
        return f"Added {total_new_documents} document(s)."
    else:
        return "No new documents were added."
