import logging

from celery import Task
from celery import shared_task

from documents.models import PaperlessTask
from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule

logger = logging.getLogger("paperless.mail.tasks")


@shared_task(bind=True)
def process_mail_accounts(self: Task, account_ids: list[int] | None = None) -> str:
    # A scheduled check can still be running (or queued) when the next one
    # ProcessedMail dedup only records a message once its
    # handling has finished, so an overlapping run can still pick up the same
    # not-yet-recorded message. Skip outright rather than race it.
    other_mail_fetch_running = (
        PaperlessTask.objects.filter(
            task_type=PaperlessTask.TaskType.MAIL_FETCH,
            status__in=[PaperlessTask.Status.PENDING, PaperlessTask.Status.STARTED],
        )
        .exclude(task_id=self.request.id)
        .exists()
    )
    if other_mail_fetch_running:
        logger.info(
            "Mail account processing is already running; skipping this run.",
        )
        return "Skipped: mail account processing already in progress."

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
