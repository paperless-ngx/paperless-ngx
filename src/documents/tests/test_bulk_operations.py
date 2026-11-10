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
from documents.signals.handlers import task_revoked_handler
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
            {
                "operation": "set_permissions",
                "document_ids": [doc.pk],
                "user_id": user.pk,
            },
            {},
        ),
    )
    task = PaperlessTask.objects.get(task_id=task_id)
    assert task.owner_id == user.pk
    assert task.task_type == PaperlessTask.TaskType.BULK_UPDATE
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_error"),
    [
        ("success", "success", ""),
        ("failure", "failure", "Could not update"),
        (
            "expired",
            "revoked",
            "Task expired before execution. Check worker logs for details.",
        ),
    ],
)
def test_tracked_outcome_notifies_only_initiator(
    bulk_setup,
    outcome,
    expected_status,
    expected_error,
):
    user, _, doc, _ = bulk_setup
    task_id = str(uuid.uuid4())
    before_task_publish_handler(
        headers={
            "task": "documents.bulk_operations.execute_bulk_operation",
            "id": task_id,
        },
        body=(
            (),
            {
                "operation": "set_permissions",
                "document_ids": [doc.pk],
                "user_id": user.pk,
            },
            {},
        ),
    )
    task = PaperlessTask.objects.get(task_id=task_id)
    assert task.owner_id == user.pk
    assert task.task_type == PaperlessTask.TaskType.BULK_UPDATE
    with mock.patch("documents.signals.handlers.async_to_sync") as send:
        if outcome == "expired":
            task_revoked_handler(request=mock.Mock(id=task_id), expired=True)
        elif outcome == "failure":
            task_failure_handler(
                task_id=task_id,
                exception=ValueError("Could not update"),
            )
        else:
            task_postrun_handler(
                task_id=task_id,
                state="SUCCESS",
                retval={"document_count": 1},
            )
    group, event = send.return_value.call_args.args
    assert group == f"bulk_operations_{user.pk}"
    assert event["data"]["status"] == expected_status
    assert event["data"]["error"] == expected_error
    assert event["data"]["task_id"] == task_id


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_completion_socket_is_private(anyio_backend):
    from types import SimpleNamespace

    from channels.layers import get_channel_layer
    from channels.testing import WebsocketCommunicator

    from paperless.consumers import StatusConsumer

    own = WebsocketCommunicator(StatusConsumer.as_asgi(), "/ws/status/")
    other = WebsocketCommunicator(StatusConsumer.as_asgi(), "/ws/status/")
    own.scope["user"] = SimpleNamespace(id=1, is_authenticated=True)
    other.scope["user"] = SimpleNamespace(id=2, is_authenticated=True)
    assert (await own.connect())[0]
    assert (await other.connect())[0]
    try:
        event = {
            "type": "bulk_operation_status",
            "data": {"task_id": "example", "status": "success"},
        }
        await get_channel_layer().group_send("bulk_operations_1", event)
        assert await own.receive_json_from() == event
        assert await other.receive_nothing(timeout=0.02)
    finally:
        await own.disconnect()
        await other.disconnect()


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["delete", "bulk_edit"])
def test_trash_remains_synchronous(bulk_setup, endpoint):
    _, client, doc, _ = bulk_setup
    data = {"documents": [doc.pk]}
    if endpoint == "bulk_edit":
        data.update(method="delete", parameters={})
    with (
        mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue,
        mock.patch("documents.search.get_backend"),
    ):
        response = client.post(
            f"/api/documents/{endpoint}/",
            data,
            format="json",
            HTTP_ACCEPT="application/json; version=9",
        )
    assert response.status_code == 200
    assert response.data == {"result": "OK"}
    assert not Document.objects.filter(pk=doc.pk).exists()
    assert Document.deleted_objects.filter(pk=doc.pk).exists()
    enqueue.assert_not_called()
