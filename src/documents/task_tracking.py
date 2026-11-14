"""Completion tracking for operations which dispatch document processing tasks."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from documents.models import PaperlessTask

if TYPE_CHECKING:
    from celery.canvas import Signature

    from documents.data_models import ConsumableDocument
    from documents.data_models import DocumentMetadataOverrides


def queue_consumption(
    *,
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides,
    trigger_source: str,
    parent_task_id: str | None,
) -> None:
    from documents.tasks import consume_file

    kwargs = {"input_doc": input_doc, "overrides": overrides}
    if parent_task_id is None:
        consume_file.apply_async(
            kwargs=kwargs,
            headers={"trigger_source": trigger_source},
        )
    else:
        queue_processing_tasks(parent_task_id, [consume_file.s(**kwargs)])


def queue_reprocessing_tasks(
    parent_task_id: str,
    document_ids: list[int],
    *,
    remote_ocr: bool,
) -> None:
    from documents.tasks import update_document_content_maybe_archive_file

    queue_processing_tasks(
        parent_task_id,
        [
            update_document_content_maybe_archive_file.s(
                document_id=document_id,
                remote_ocr=remote_ocr,
            )
            for document_id in document_ids
        ],
    )


def queue_processing_tasks(
    parent_task_id: str,
    signatures: list[Signature],
    *,
    delete_ids: list[int] | None = None,
    asn_backup: dict | None = None,
) -> None:
    from documents.signals.handlers import TRACKED_TASKS
    from documents.signals.handlers import _extract_input_data

    parent = PaperlessTask.objects.get(task_id=parent_task_id)
    children = [
        PaperlessTask(
            task_id=str(uuid.uuid4()),
            task_type=TRACKED_TASKS[signature.task],
            trigger_source=parent.trigger_source,
            owner_id=parent.owner_id,
            parent=parent,
            input_data=_extract_input_data(
                TRACKED_TASKS[signature.task],
                signature.kwargs,
            ),
        )
        for signature in signatures
    ]
    # Dependencies and their final step must be registered together.
    with transaction.atomic():
        PaperlessTask.objects.bulk_create(children)
        if delete_ids:
            PaperlessTask.objects.create(
                task_id=str(uuid.uuid4()),
                task_type=PaperlessTask.TaskType.BULK_DELETE,
                owner_id=parent.owner_id,
                trigger_source=parent.trigger_source,
                parent=parent,
                input_data={
                    "dependencies": [child.pk for child in children],
                    "delete_ids": delete_ids,
                    "asn_backup": asn_backup or {},
                },
            )
    for index, (signature, child) in enumerate(zip(signatures, children, strict=True)):
        try:
            signature.apply_async(
                task_id=child.task_id,
                headers={"trigger_source": parent.trigger_source},
            )
        except Exception:
            PaperlessTask.objects.filter(
                pk__in=[task.pk for task in children[index:]],
            ).update(
                status=PaperlessTask.Status.FAILURE,
                date_done=timezone.now(),
                result_data={"error_message": "Could not publish processing task."},
            )
            raise


@shared_task
def finish_file_operation(
    dependencies: list[int],
    delete_ids: list[int],
    asn_backup: dict,
) -> dict[str, str]:
    from documents.bulk_edit import delete
    from documents.bulk_edit import restore_archive_serial_numbers

    statuses = list(
        PaperlessTask.objects.filter(pk__in=dependencies).values_list(
            "status",
            flat=True,
        ),
    )
    if len(statuses) != len(dependencies):
        raise ValueError(
            "Processing task records are missing; originals were preserved.",
        )
    if any(status != PaperlessTask.Status.SUCCESS for status in statuses):
        restore_archive_serial_numbers(asn_backup)
        return {"reason": "Originals preserved; archive serial numbers restored."}
    delete(delete_ids)
    return {"reason": "Originals moved to trash."}


def _publish_finalizer(task: PaperlessTask) -> None:
    try:
        finish_file_operation.apply_async(
            task_id=task.task_id,
            kwargs=task.input_data,
            headers={"trigger_source": task.trigger_source},
        )
    except Exception as error:
        from documents.signals.handlers import task_failure_handler

        task_failure_handler(
            sender=finish_file_operation,
            task_id=task.task_id,
            exception=error,
        )


def _schedule_finalizers(parent: PaperlessTask) -> None:
    for task in parent.children.filter(
        task_type=PaperlessTask.TaskType.BULK_DELETE,
        status=PaperlessTask.Status.PENDING,
    ):
        dependencies = task.input_data.get("dependencies")
        if dependencies is None or task.result_data:
            continue
        if (
            PaperlessTask.objects.filter(pk__in=dependencies)
            .exclude(
                status__in=PaperlessTask.COMPLETE_STATUSES,
            )
            .exists()
        ):
            continue
        task.result_data = {"scheduled": True}
        task.save(update_fields=["result_data"])
        transaction.on_commit(lambda task=task: _publish_finalizer(task))


def finish_dispatch(task: PaperlessTask, result_data: dict) -> None:
    """Record the scheduling outcome without completing an active parent."""
    with transaction.atomic():
        parent = PaperlessTask.objects.select_for_update().get(pk=task.pk)
        if parent.is_complete:
            return
        parent.dispatched = True
        parent.result_data = result_data
        parent.save(update_fields=["dispatched", "result_data"])
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
    _schedule_finalizers(parent)
    statuses = list(parent.children.values_list("status", flat=True))
    if any(status not in PaperlessTask.COMPLETE_STATUSES for status in statuses):
        return

    succeeded = statuses.count(PaperlessTask.Status.SUCCESS)
    failed = len(statuses) - succeeded
    result_data = parent.result_data or {}
    if failed and not result_data.get("error_message"):
        result_data["error_message"] = (
            f"{succeeded} child task(s) succeeded; {failed} failed or were revoked. "
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

    if "operation" in parent.input_data:
        transaction.on_commit(lambda: _send_bulk_operation_status(parent))
    update_parent(parent)
