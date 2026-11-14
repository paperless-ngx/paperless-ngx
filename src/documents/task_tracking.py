"""Completion tracking for operations which dispatch document processing tasks."""

import uuid

from django.db import transaction
from django.utils import timezone

from documents.models import PaperlessTask


def queue_reprocessing_tasks(
    parent_task_id: str,
    document_ids: list[int],
    *,
    remote_ocr: bool,
) -> None:
    from documents.tasks import update_document_content_maybe_archive_file

    parent = PaperlessTask.objects.get(task_id=parent_task_id)
    children = [
        PaperlessTask(
            task_id=str(uuid.uuid4()),
            task_type=PaperlessTask.TaskType.REPROCESS_DOCUMENT,
            trigger_source=parent.trigger_source,
            owner_id=parent.owner_id,
            parent=parent,
            input_data={"document_id": document_id},
        )
        for document_id in document_ids
    ]
    # Register the complete set before any can finish
    PaperlessTask.objects.bulk_create(children)
    for index, child in enumerate(children):
        try:
            update_document_content_maybe_archive_file.apply_async(
                task_id=child.task_id,
                kwargs={
                    "document_id": child.input_data["document_id"],
                    "remote_ocr": remote_ocr,
                },
                headers={"trigger_source": parent.trigger_source},
            )
        except Exception:
            PaperlessTask.objects.filter(
                pk__in=[task.pk for task in children[index:]],
            ).update(
                status=PaperlessTask.Status.FAILURE,
                date_done=timezone.now(),
                result_data={"error_message": "Could not publish reprocessing task."},
            )
            raise


def finish_dispatch(task: PaperlessTask, result_data: dict) -> None:
    """Record the scheduling outcome without completing an active parent."""
    with transaction.atomic():
        parent = PaperlessTask.objects.select_for_update().get(pk=task.pk)
        if parent.is_complete:
            return
        parent.dispatched = True
        parent.result_data = result_data
        parent.save(update_fields=["dispatch_complete", "result_data"])
        _finalize_parent(parent)


def update_parent(task: PaperlessTask) -> None:
    if task.parent_id is None:
        return
    with transaction.atomic():
        parent = PaperlessTask.objects.select_for_update().get(pk=task.parent_id)
        _finalize_parent(parent)


def _finalize_parent(parent: PaperlessTask) -> None:
    if parent.is_complete or not parent.dispatched:
        return
    statuses = list(parent.children.values_list("status", flat=True))
    if any(status not in PaperlessTask.COMPLETE_STATUSES for status in statuses):
        return

    succeeded = statuses.count(PaperlessTask.Status.SUCCESS)
    failed = len(statuses) - succeeded
    result_data = parent.result_data or {}
    if failed and not result_data.get("error_message"):
        result_data["error_message"] = (
            f"{succeeded} document(s) reprocessed; {failed} failed or were revoked. "
            "See child tasks for details."
        )
    parent.status = (
        PaperlessTask.Status.FAILURE
        if result_data.get("error_message")
        else PaperlessTask.Status.SUCCESS
    )
    parent.result_data = {
        **parent.input_data,
        **result_data,
        "succeeded_count": succeeded,
        "failed_count": failed,
    }
    parent.date_done = timezone.now()
    if parent.date_started:
        parent.duration_seconds = (
            parent.date_done - parent.date_started
        ).total_seconds()
        parent.wait_time_seconds = (
            parent.date_started - parent.date_created
        ).total_seconds()
    parent.save()
    from documents.signals.handlers import _send_bulk_operation_status

    transaction.on_commit(lambda: _send_bulk_operation_status(parent))
