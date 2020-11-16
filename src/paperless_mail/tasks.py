import logging

from paperless_mail import mail
from paperless_mail.models import MailAccount


def process_mail_accounts():
    for account in MailAccount.objects.all():
        mail.handle_mail_account(account)


def process_mail_account(name):
    account = MailAccount.objects.find(name=name)
    if account:
        mail.handle_mail_account(account)
    else:
        logging.error("Unknown mail acccount: {}".format(name))
