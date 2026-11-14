import uuid
from unittest import mock

import pytest

from documents.bulk_operations import execute_bulk_operation
from documents.models import PaperlessTask
from documents.signals.handlers import task_failure_handler
from documents.signals.handlers import task_postrun_handler
from documents.signals.handlers import task_revoked_handler
from documents.tasks import update_document_content_maybe_archive_file
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory


@pytest.fixture
def operation(paperless_dirs):
    user = UserFactory(superuser=True)
    documents = DocumentFactory.create_batch(3)
    parent = PaperlessTask.objects.create(
        task_id=str(uuid.uuid4()),
        task_type=PaperlessTask.TaskType.BULK_UPDATE,
        owner=user,
        trigger_source=PaperlessTask.TriggerSource.WEB_UI,
        input_data={"operation": "reprocess", "document_count": 3},
    )
    kwargs = {
        "operation": "reprocess",
        "document_ids": [document.pk for document in documents],
        "parameters": {"remote_ocr": True},
        "user_id": user.pk,
    }
    return parent, kwargs


def complete(child, status="SUCCESS"):
    if status == "FAILURE":
        task_failure_handler(
            sender=update_document_content_maybe_archive_file,
            task_id=child.task_id,
            exception=RuntimeError("Parser failed"),
        )
    elif status == "REVOKED":
        task_revoked_handler(
            sender=update_document_content_maybe_archive_file,
            request=mock.Mock(id=child.task_id),
        )
    else:
        task_postrun_handler(
            task=update_document_content_maybe_archive_file,
            task_id=child.task_id,
            state=status,
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("outcome", ["SUCCESS", "FAILURE", "REVOKED"])
def test_parent_waits_for_all_children(operation, outcome):
    parent, kwargs = operation
    with (
        mock.patch(
            "documents.tasks.update_document_content_maybe_archive_file.apply_async",
        ) as publish,
        mock.patch("documents.signals.handlers._send_bulk_operation_status") as notify,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        assert parent.date_done is None
        children = list(parent.children.order_by("pk"))
        assert len(children) == 3
        assert publish.call_count == 3
        assert all(child.owner_id == parent.owner_id for child in children)
        assert all(child.trigger_source == parent.trigger_source for child in children)
        assert all(
            call.kwargs["kwargs"]["remote_ocr"] for call in publish.call_args_list
        )
        complete(children[0], outcome)
        complete(children[1])
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        notify.assert_not_called()
        complete(children[2])
        parent.refresh_from_db()
        assert parent.status == ("success" if outcome == "SUCCESS" else "failure")
        assert parent.result_data["succeeded_count"] == (
            3 if outcome == "SUCCESS" else 2
        )
        assert parent.result_data["failed_count"] == (0 if outcome == "SUCCESS" else 1)
        assert parent.date_done is not None
        assert parent.duration_seconds >= 0
        notify.assert_called_once()
        complete(children[2])
        notify.assert_called_once()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("outcome", ["SUCCESS", "FAILURE"])
def test_fast_children_wait_for_dispatch_to_finish(operation, outcome):
    parent, kwargs = operation

    def publish(*, task_id, **kwargs):
        # Every child is registered before the first publication.
        assert parent.children.count() == 3
        complete(PaperlessTask.objects.get(task_id=task_id), outcome)
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        assert not parent.dispatch_complete

    with (
        mock.patch(
            "documents.tasks.update_document_content_maybe_archive_file.apply_async",
            side_effect=publish,
        ),
        mock.patch("documents.signals.handlers._send_bulk_operation_status") as notify,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        parent.refresh_from_db()
        assert parent.status == ("success" if outcome == "SUCCESS" else "failure")
        notify.assert_called_once()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("published_count", [0, 1])
def test_publish_failure_waits_for_published_children(operation, published_count):
    parent, kwargs = operation
    with (
        mock.patch(
            "documents.tasks.update_document_content_maybe_archive_file.apply_async",
            side_effect=[None] * published_count + [RuntimeError("Broker unavailable")],
        ),
        mock.patch("documents.signals.handlers._send_bulk_operation_status") as notify,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=False)
        parent.refresh_from_db()
        if published_count:
            assert parent.status == PaperlessTask.Status.STARTED
            notify.assert_not_called()
            complete(parent.children.get(status=PaperlessTask.Status.PENDING))
            parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.FAILURE
        assert parent.result_data["error_message"] == "Broker unavailable"
        assert parent.result_data["succeeded_count"] == published_count
        assert parent.result_data["failed_count"] == 3 - published_count
        notify.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_empty_selection_completes_without_children(operation):
    parent, kwargs = operation
    kwargs["document_ids"] = []
    execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.SUCCESS
    assert not parent.children.exists()


@pytest.mark.django_db
def test_client_cannot_supply_parent_task_id(operation):
    from rest_framework.test import APIClient

    parent, kwargs = operation
    client = APIClient()
    client.force_authenticate(parent.owner)
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as publish:
        response = client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": kwargs["document_ids"],
                "method": "set_correspondent",
                "parameters": {"correspondent": None, "parent_task_id": parent.task_id},
            },
            format="json",
        )
    assert response.status_code == 400
    publish.assert_not_called()
