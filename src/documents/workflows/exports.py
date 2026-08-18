import logging

from celery import shared_task
from django.utils import timezone

from documents.models import ExportRecord

logger = logging.getLogger("paperless.workflows.exports")


@shared_task(
    bind=True,
    max_retries=3,
)
def export_document(self, record_id: int) -> str:
    """
    Deliver the document referenced by an ExportRecord to its target.

    Transient failures retry with backoff; once retries are exhausted the
    record is marked failed and the exception re-raised so the failure is
    loud — a silently failed export reads as delivered.
    """
    from documents.export.delivery import deliver_export_record

    record = (
        ExportRecord.objects.select_related("target", "action", "document")
        .filter(pk=record_id)
        .first()
    )
    if record is None:
        logger.warning("Export record %s no longer exists", record_id)
        return "Export record no longer exists"

    try:
        deliver_export_record(record)
    except Exception as e:
        logger.error(
            "Failed attempt %d exporting document %s to %s: %s",
            self.requehttp://localhost:4200/trashst.retries + 1,
            record.document_pk,
            record.target,
            e,
        )
        record.last_error = {
            "error": str(e) or e.__class__.__name__,
            "attempt": self.request.retries + 1,
        }
        if self.request.retries >= self.max_retries:
            record.status = ExportRecord.Status.FAILED
            record.finished_at = timezone.now()
            record.save(update_fields=["status", "finished_at", "last_error"])
            raise
        record.save(update_fields=["last_error"])
        # exponential backoff: 1, 2, 4 minutes
        raise self.retry(exc=e, countdown=(2**self.request.retries) * 60)

    return (
        f"Exported document {record.document_pk} to "
        f"{record.target} as {record.object_key}"
    )
