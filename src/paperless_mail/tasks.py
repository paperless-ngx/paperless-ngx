import logging

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount


def process_mail_accounts():
    total_new_documents = 0
    for account in MailAccount.objects.all():
        total_new_documents += MailAccountHandler().handle_mail_account(
            account)

    if total_new_documents > 0:
        return f"Added {total_new_documents} document(s)."
    else:
        return "No new documents were added."


def process_mail_account(name):
    account = MailAccount.objects.find(name=name)
    if account:
        MailAccountHandler().handle_mail_account(account)
    else:
        logging.error("Unknown mail acccount: {}".format(name))
