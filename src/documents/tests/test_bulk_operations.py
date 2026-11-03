"""Request acceptance, worker execution, and task tracking."""

import uuid
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import User
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from documents.bulk_operations import execute_bulk_operation
from documents.models import Correspondent
from documents.models import Document
from documents.models import PaperlessTask
from documents.signals.handlers import before_task_publish_handler
from documents.signals.handlers import task_failure_handler
from documents.signals.handlers import task_postrun_handler
from paperless_testing.factories import UserFactory


@pytest.fixture
def bulk_setup(paperless_dirs):
    user = UserFactory(superuser=True)
    client = APIClient()
    client.force_authenticate(user)
    doc = Document.objects.create(title="Example", checksum="bulk-op-example")
    correspondent = Correspondent.objects.create(name="Example correspondent")
    return user, client, doc, correspondent


@pytest.mark.django_db
@pytest.mark.parametrize(
    "endpoint,operation,parameters",
    [
        ("bulk_edit", "set_correspondent", {"correspondent": None}),
        ("delete", "delete", {}),
    ],
)
def test_request_only_queues(bulk_setup, endpoint, operation, parameters):
    user, client, doc, _ = bulk_setup
    task_id = str(uuid.uuid4())
    data = {"documents": [doc.pk], "from_webui": True}
    if endpoint == "bulk_edit":
        data.update(method=operation, parameters=parameters)
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue:
        enqueue.return_value.id = task_id
        response = client.post(f"/api/documents/{endpoint}/", data, format="json")
    assert response.status_code == 200
    assert response.data == {"result": "OK", "task_id": task_id}
    assert Document.objects.filter(pk=doc.pk).exists()
    assert enqueue.call_args.kwargs["kwargs"] == {
        "operation": operation,
        "document_ids": [doc.pk],
        "parameters": parameters,
        "user_id": user.pk,
    }
    assert enqueue.call_args.kwargs["headers"]["trigger_source"] == "web_ui"


@pytest.mark.django_db
def test_metadata_task_includes_audit_and_followup(bulk_setup, settings):
    user, _, doc, correspondent = bulk_setup
    settings.AUDIT_LOG_ENABLED = True
    with (
        mock.patch("documents.bulk_operations.bulk_update_documents") as followup,
        mock.patch(
            "documents.bulk_edit.bulk_update_documents.apply_async",
        ) as extra_task,
    ):

        def check_followup(ids):
            doc.refresh_from_db()
            assert doc.correspondent_id == correspondent.pk
            assert LogEntry.objects.filter(object_pk=str(doc.pk), actor=user).exists()
            assert ids == [doc.pk]

        followup.side_effect = check_followup
        result = execute_bulk_operation(
            "set_correspondent",
            [doc.pk],
            {"correspondent": correspondent.pk},
            user.pk,
        )
    followup.assert_called_once()
    extra_task.assert_not_called()
    assert result["document_count"] == 1


@pytest.mark.django_db
def test_permissions_rechecked_on_worker(bulk_setup):
    user, _, doc, correspondent = bulk_setup
    User.objects.filter(pk=user.pk).update(is_superuser=False)
    with pytest.raises(PermissionDenied):
        execute_bulk_operation(
            "set_correspondent",
            [doc.pk],
            {"correspondent": correspondent.pk},
            user.pk,
        )
    doc.refresh_from_db()
    assert doc.correspondent_id is None


@pytest.mark.django_db
def test_queue_failure_does_not_change_documents(bulk_setup):
    _, client, doc, correspondent = bulk_setup
    with mock.patch(
        "documents.views.execute_bulk_operation.apply_async",
        side_effect=RuntimeError("broker unavailable"),
    ):
        response = client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [doc.pk],
                "method": "set_correspondent",
                "parameters": {"correspondent": correspondent.pk},
            },
            format="json",
        )
    assert response.status_code == 400
    doc.refresh_from_db()
    assert doc.correspondent_id is None


@pytest.mark.django_db
@pytest.mark.parametrize("failed", [False, True])
def test_tracked_outcome_records_initiator_and_result(bulk_setup, failed):
    user, _, doc, _ = bulk_setup
    task_id = str(uuid.uuid4())
    before_task_publish_handler(
        headers={
            "task": "documents.bulk_operations.execute_bulk_operation",
            "id": task_id,
        },
        body=(
            (),
            {"operation": "delete", "document_ids": [doc.pk], "user_id": user.pk},
            {},
        ),
    )
    task = PaperlessTask.objects.get(task_id=task_id)
    assert task.owner_id == user.pk
    assert task.task_type == PaperlessTask.TaskType.BULK_DELETE
    if failed:
        task_failure_handler(task_id=task_id, exception=ValueError("Could not update"))
    else:
        task_postrun_handler(
            task_id=task_id,
            state="SUCCESS",
            retval={"document_count": 1},
        )
    task.refresh_from_db()
    assert task.status == ("failure" if failed else "success")
    if failed:
        assert task.result_data["error_message"] == "Could not update"
    else:
        assert task.result_data == {"document_count": 1}


@pytest.mark.django_db
def test_large_filtered_selection_is_one_task(bulk_setup):
    _, client, _, _ = bulk_setup
    Document.objects.bulk_create(
        [
            Document(title="bulk-large-selection", checksum=f"large-{i}")
            for i in range(10_000)
        ],
    )
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue:
        enqueue.return_value.id = str(uuid.uuid4())
        response = client.post(
            "/api/documents/bulk_edit/",
            {
                "all": True,
                "filters": {"title__icontains": "bulk-large-selection"},
                "method": "set_correspondent",
                "parameters": {"correspondent": None},
            },
            format="json",
        )
    assert response.status_code == 200
    enqueue.assert_called_once()
    assert len(enqueue.call_args.kwargs["kwargs"]["document_ids"]) == 10_000
