import logging
from typing import Final

from celery import Task
from celery import shared_task
from django.core.cache import cache

from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule

logger = logging.getLogger("paperless.mail.tasks")

# Cache-backed lock guarding overlapping mail-account processing runs; unlike
# a PaperlessTask row, it self-heals if the owning worker dies mid-run.
MAIL_FETCH_LOCK_KEY: Final = "paperless_mail_fetch_lock"
# Ceiling on how long a run may hold the lock; renewed after each account.
MAIL_FETCH_LOCK_TTL: Final = 30 * 60


@shared_task(bind=True)
def process_mail_accounts(self: Task, account_ids: list[int] | None = None) -> str:
    if not cache.add(MAIL_FETCH_LOCK_KEY, self.request.id, timeout=MAIL_FETCH_LOCK_TTL):
        logger.info(
            "Mail account processing is already running; skipping this run.",
        )
        return "Skipped: mail account processing already in progress."

    try:
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
                total_new_documents += MailAccountHandler().handle_mail_account(
                    account,
                )
            except MailError:
                logger.exception(f"Error while processing mail account {account}")
            # Renew the lock so a run still genuinely in progress doesn't
            # lose it to the TTL partway through a long account list.
            cache.touch(MAIL_FETCH_LOCK_KEY, MAIL_FETCH_LOCK_TTL)

        if total_new_documents > 0:
            return f"Added {total_new_documents} document(s)."
        else:
            return "No new documents were added."
    finally:
        cache.delete(MAIL_FETCH_LOCK_KEY)
