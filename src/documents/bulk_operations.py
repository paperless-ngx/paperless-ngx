"""Queued document bulk operations."""

from typing import Any

from auditlog.context import set_actor
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from documents import bulk_edit
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import PaperlessTask
from documents.permissions import has_document_operation_permissions
from documents.tasks import bulk_update_documents

MODIFIED_FIELDS = {
    "set_correspondent": "correspondent",
    "set_document_type": "document_type",
    "set_storage_path": "storage_path",
    "add_tag": "tags",
    "remove_tag": "tags",
    "modify_tags": "tags",
    "modify_custom_fields": "custom_fields",
    "set_permissions": None,
}
LEGACY_MODIFIED_FIELDS = {"delete": "deleted_at", "reprocess": "checksum"}
QUEUED_OPERATIONS = frozenset(
    (
        *MODIFIED_FIELDS,
        "delete",
        "reprocess",
        "run_workflow",
        "rotate",
        "merge",
        "merge_as_versions",
        "split",
        "delete_pages",
        "edit_pdf",
        "remove_password",
    ),
)
USER_OPERATIONS = frozenset(
    {
        "split",
        "merge",
        "rotate",
        "delete_pages",
        "edit_pdf",
        "remove_password",
        "merge_as_versions",
    },
)
# merge_as_versions doesn't queue any consume tasks
TRIGGER_SOURCE_OPERATIONS = USER_OPERATIONS - {"merge_as_versions"}


def snapshot_field(doc_ids: list[int], field: str) -> dict[int, Any]:
    """
    Returns each document's current value of field, for the audit log.

    Tags and custom fields are one row per value, so they are gathered
    into a sorted list of pks per document (empty when there are none).
    Reading them through Document.values() instead would join those rows
    and return one arbitrary value per document.
    """
    if field == "tags":
        rows = (
            Document.tags.through.objects.filter(document_id__in=doc_ids)
            .order_by("tag_id")
            .values_list("document_id", "tag_id")
        )
    elif field == "custom_fields":
        rows = (
            CustomFieldInstance.objects.filter(document_id__in=doc_ids)
            .order_by("pk")
            .values_list("document_id", "pk")
        )
    else:
        return dict(
            Document.objects.filter(pk__in=doc_ids).values_list("pk", field),
        )

    values: dict[int, list[int]] = {doc_id: [] for doc_id in doc_ids}
    for doc_id, pk in rows:
        values[doc_id].append(pk)
    return values


@shared_task
def execute_bulk_operation(
    operation: str,
    document_ids: list[int],
    parameters: dict,
    user_id: int,
    trigger_source: str = PaperlessTask.TriggerSource.API_UPLOAD,
) -> dict:
    if operation not in QUEUED_OPERATIONS:
        raise ValueError(f"Unsupported bulk operation: {operation}")
    method = getattr(bulk_edit, operation)
    user = User.objects.get(pk=user_id)
    if not has_document_operation_permissions(
        user=user,
        documents=document_ids,
        method=method,
        parameters=parameters,
    ):
        raise PermissionDenied("Insufficient permissions to execute bulk operation")

    if operation == "run_workflow" and not user.has_perm("documents.view_workflow"):
        raise PermissionDenied("Insufficient permissions to run this workflow")

    if operation not in MODIFIED_FIELDS:
        execution_parameters = parameters.copy()
        if operation in USER_OPERATIONS:
            execution_parameters["user"] = user
        if operation in TRIGGER_SOURCE_OPERATIONS:
            execution_parameters["trigger_source"] = trigger_source
        modified_field = LEGACY_MODIFIED_FIELDS.get(operation)
        with set_actor(user):
            old_values = (
                snapshot_field(document_ids, modified_field)
                if settings.AUDIT_LOG_ENABLED and modified_field
                else {}
            )
            method(document_ids, **execution_parameters)
            if settings.AUDIT_LOG_ENABLED and modified_field:
                from auditlog.models import LogEntry

                new_values = snapshot_field(document_ids, modified_field)
                for doc in Document.objects.filter(pk__in=document_ids):
                    LogEntry.objects.log_create(
                        instance=doc,
                        changes={
                            modified_field: [old_values[doc.pk], new_values[doc.pk]],
                        },
                        action=LogEntry.Action.UPDATE,
                        actor=user,
                        additional_data={"reason": f"Bulk edit: {operation}"},
                    )
        return {"operation": operation, "document_count": len(document_ids)}

    affected_ids: list[int] = []
    modified_field = MODIFIED_FIELDS[operation]
    # Keep metadata writes and their audit entries together. Follow-up processing
    # runs after commit, within this same tracked task.
    with set_actor(user), transaction.atomic():
        old_values = (
            snapshot_field(document_ids, modified_field)
            if settings.AUDIT_LOG_ENABLED and modified_field
            else {}
        )
        method(document_ids, **parameters, update_callback=affected_ids.extend)
        if settings.AUDIT_LOG_ENABLED and modified_field:
            from auditlog.models import LogEntry

            new_values = snapshot_field(document_ids, modified_field)
            for doc in Document.objects.filter(pk__in=document_ids):
                LogEntry.objects.log_create(
                    instance=doc,
                    changes={modified_field: [old_values[doc.pk], new_values[doc.pk]]},
                    action=LogEntry.Action.UPDATE,
                    actor=user,
                    additional_data={"reason": f"Bulk edit: {operation}"},
                )
    if affected_ids:
        bulk_update_documents(list(dict.fromkeys(affected_ids)))
    return {"operation": operation, "document_count": len(document_ids)}
