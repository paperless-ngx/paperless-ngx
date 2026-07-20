import logging
import random
import time

from celery import shared_task
from django.conf import settings

from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule

logger = logging.getLogger("paperless.mail.tasks")


@shared_task(bind=True)
def process_mail_accounts(self, account_ids: list[int] | None = None) -> str:
    # The beat schedule fires this task on a fixed crontab boundary, so every
    # install would otherwise hit its mail server at the exact same second.
    # Spread scheduled runs out with a small random delay. Manual runs (from
    # the UI, which pass an explicit account_ids) are left untouched so the
    # user isn't kept waiting.
    jitter = getattr(settings, "EMAIL_TASK_JITTER_SECONDS", 0)
    trigger_source = getattr(self.request, "trigger_source", None)
    if trigger_source is None:
        # Depending on the celery version the custom header may only be
        # reachable via the request's headers mapping.
        headers = getattr(self.request, "headers", None) or {}
        trigger_source = headers.get("trigger_source")
    is_scheduled = trigger_source == "scheduled"
    if jitter > 0 and account_ids is None and is_scheduled:
        delay = random.uniform(0, jitter)
        logger.debug(f"Jittering scheduled mail check by {delay:.1f}s")
        time.sleep(delay)

    total_new_documents = 0
    accounts = (
        MailAccount.objects.filter(pk__in=account_ids)
        if account_ids
        else MailAccount.objects.all()
    )
    for account in accounts:
        if not MailRule.objects.filter(account=account, enabled=True).exists():
            logger.info(f"No rules enabled for account {account}. Skipping.")
            continue
        try:
            total_new_documents += MailAccountHandler().handle_mail_account(account)
        except MailError:
            logger.exception(f"Error while processing mail account {account}")

    if total_new_documents > 0:
        return f"Added {total_new_documents} document(s)."
    else:
        return "No new documents were added."
