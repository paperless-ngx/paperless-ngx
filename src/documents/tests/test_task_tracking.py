import shutil
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


@pytest.fixture
def pdf_documents(paperless_dirs, tmp_path):
    from documents.models import Document
    from paperless_testing.samples import SIMPLE_DIGITAL_PDF

    documents = DocumentFactory.create_batch(2, mime_type="application/pdf")
    for document in documents:
        source = tmp_path / f"{document.pk}.pdf"
        shutil.copy(SIMPLE_DIGITAL_PDF, source)
        Document.objects.filter(pk=document.pk).update(filename=str(source))
        document.refresh_from_db()
    return documents


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
        assert all(call.args[1]["remote_ocr"] for call in publish.call_args_list)
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

    def publish(*args, task_id, **kwargs):
        # Every child is registered before the first publication.
        assert parent.children.count() == 3
        complete(PaperlessTask.objects.get(task_id=task_id), outcome)
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        assert not parent.dispatched

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


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "name,parameters",
    [
        ("rotate", {"degrees": 90}),
        ("merge", {}),
        ("split", {"pages": [[1]]}),
        ("delete_pages", {"pages": [1]}),
        ("edit_pdf", {"operations": [{"page": 1}], "update_document": True}),
        ("edit_pdf", {"operations": [{"page": 1}]}),
        ("remove_password", {"password": "secret", "update_document": True}),
        ("remove_password", {"password": "secret"}),
    ],
)
def test_file_operations_wait_for_consumption(
    operation,
    pdf_documents,
    name,
    parameters,
):
    from documents.tasks import consume_file

    parent, kwargs = operation
    documents = pdf_documents
    kwargs.update(
        operation=name,
        document_ids=[doc.pk for doc in documents]
        if name == "merge"
        else [documents[0].pk],
        parameters=parameters,
    )
    parent.input_data = {
        "operation": name,
        "document_count": len(kwargs["document_ids"]),
    }
    parent.save()
    with (
        mock.patch("documents.tasks.consume_file.apply_async") as publish,
        mock.patch("documents.bulk_edit.pdf_ops.needs_decrypt", return_value=True),
        mock.patch(
            "documents.bulk_edit.pdf_ops.decrypt_pdf",
            return_value=documents[0].source_path,
        ),
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.STARTED
    child = parent.children.get()
    assert child.task_type == PaperlessTask.TaskType.CONSUME_FILE
    publish.assert_called_once()
    task_postrun_handler(
        task=consume_file,
        task_id=child.task_id,
        state="SUCCESS",
        retval={"document_id": 100},
    )
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.SUCCESS


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "outcome",
    ["success", "failure", "duplicate", "stopped", "revoked"],
)
def test_replacement_waits_for_deletion_or_recovery(operation, pdf_documents, outcome):
    from documents.models import Document
    from documents.task_tracking import finish_file_operation
    from documents.tasks import consume_file

    parent, kwargs = operation
    doc = pdf_documents[0]
    doc.archive_serial_number = 123
    Document.objects.filter(pk=doc.pk).update(archive_serial_number=123)
    kwargs.update(
        operation="edit_pdf",
        document_ids=[doc.pk],
        parameters={"operations": [{"page": 1}], "delete_original": True},
    )
    parent.input_data = {"operation": "edit_pdf", "document_count": 1}
    parent.save()
    with (
        mock.patch("documents.tasks.consume_file.apply_async"),
        mock.patch(
            "documents.task_tracking.finish_file_operation.apply_async",
        ) as finalize,
        mock.patch("documents.signals.handlers._send_bulk_operation_status") as notify,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        consume = parent.children.get(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        finalizer = parent.children.get(task_type=PaperlessTask.TaskType.BULK_DELETE)
        finalize.assert_not_called()
        if outcome == "failure":
            complete(consume, "FAILURE")
        elif outcome == "revoked":
            complete(consume, "REVOKED")
        else:
            retval = (
                {"document_id": 100}
                if outcome == "success"
                else (
                    {"duplicate_of": 100}
                    if outcome == "duplicate"
                    else {"reason": "Stopped"}
                )
            )
            task_postrun_handler(
                task=consume_file,
                task_id=consume.task_id,
                state="SUCCESS",
                retval=retval,
            )
        finalize.assert_called_once()
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        assert Document.objects.filter(pk=doc.pk).exists()
        notify.assert_not_called()
        finish_file_operation.apply(
            kwargs=finalizer.input_data,
            task_id=finalizer.task_id,
            throw=True,
        )
        parent.refresh_from_db()
        assert parent.status == ("success" if outcome == "success" else "failure")
        notify.assert_called_once()
        if outcome == "success":
            assert not Document.objects.filter(pk=doc.pk).exists()
        else:
            doc.refresh_from_db()
            assert not doc.is_deleted
            assert doc.archive_serial_number == 123


@pytest.mark.django_db(transaction=True)
def test_consumption_descendants_keep_operation_active(operation):
    from documents.data_models import ConsumableDocument
    from documents.data_models import DocumentSource
    from documents.signals.handlers import before_task_publish_handler
    from documents.task_tracking import finish_dispatch
    from documents.task_tracking import queue_processing_tasks
    from documents.tasks import consume_file
    from paperless_testing.samples import SIMPLE_DIGITAL_PDF

    parent, _ = operation
    parent.status = PaperlessTask.Status.STARTED
    parent.save()
    input_doc = ConsumableDocument(
        source=DocumentSource.ConsumeFolder,
        original_file=SIMPLE_DIGITAL_PDF,
    )
    with mock.patch("documents.tasks.consume_file.apply_async"):
        queue_processing_tasks(parent.task_id, [consume_file.s(input_doc=input_doc)])
    child = parent.children.get()
    finish_dispatch(parent, {})
    descendant_id = str(uuid.uuid4())
    before_task_publish_handler(
        headers={
            "task": consume_file.name,
            "id": descendant_id,
            "parent_id": child.task_id,
        },
        body=((), {"input_doc": input_doc}, {}),
    )
    descendant = PaperlessTask.objects.get(task_id=descendant_id)
    assert descendant.parent_id == child.pk
    assert descendant.owner_id == parent.owner_id
    task_postrun_handler(
        task=consume_file,
        task_id=child.task_id,
        state="SUCCESS",
        retval={"reason": "Barcode splitting complete"},
    )
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.STARTED
    task_postrun_handler(
        task=consume_file,
        task_id=descendant_id,
        state="SUCCESS",
        retval={"document_id": 100},
    )
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.SUCCESS


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("failure", ["delete", "restore", "publish"])
def test_final_step_failures_reach_parent(operation, pdf_documents, failure):
    from documents.task_tracking import finish_file_operation
    from documents.tasks import consume_file

    parent, kwargs = operation
    doc = pdf_documents[0]
    kwargs.update(
        operation="edit_pdf",
        document_ids=[doc.pk],
        parameters={"operations": [{"page": 1}], "delete_original": True},
    )
    with (
        mock.patch("documents.tasks.consume_file.apply_async"),
        mock.patch(
            "documents.task_tracking.finish_file_operation.apply_async",
            side_effect=RuntimeError("Publish failed")
            if failure == "publish"
            else None,
        ),
        mock.patch("documents.signals.handlers._send_bulk_operation_status") as notify,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        child = parent.children.get(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        if failure == "restore":
            complete(child, "FAILURE")
        else:
            task_postrun_handler(
                task=consume_file,
                task_id=child.task_id,
                state="SUCCESS",
                retval={"document_id": 100},
            )
        finalizer = parent.children.get(task_type=PaperlessTask.TaskType.BULK_DELETE)
        if failure != "publish":
            parent.refresh_from_db()
            assert parent.status == PaperlessTask.Status.STARTED
            notify.assert_not_called()
            target = (
                "documents.bulk_edit.delete"
                if failure == "delete"
                else "documents.bulk_edit.restore_archive_serial_numbers"
            )
            with mock.patch(target, side_effect=RuntimeError("Final step failed")):
                finish_file_operation.apply(
                    kwargs=finalizer.input_data,
                    task_id=finalizer.task_id,
                    throw=False,
                )
        parent.refresh_from_db()
        finalizer.refresh_from_db()
        assert finalizer.status == PaperlessTask.Status.FAILURE
        assert parent.status == PaperlessTask.Status.FAILURE
        notify.assert_called_once()
        doc.refresh_from_db()
        assert not doc.is_deleted


@pytest.mark.django_db(transaction=True)
def test_partial_merge_preserves_skipped_original_and_reports_it(
    operation,
    pdf_documents,
):
    from documents.models import Document
    from documents.task_tracking import finish_file_operation
    from documents.tasks import consume_file

    parent, kwargs = operation
    included, excluded = pdf_documents
    excluded.source_path.unlink()
    kwargs.update(
        operation="merge",
        document_ids=[included.pk, excluded.pk],
        parameters={"delete_originals": True},
    )
    parent.input_data = {"operation": "merge", "document_count": 2}
    parent.save()
    with (
        mock.patch("documents.tasks.consume_file.apply_async") as consume,
        mock.patch("documents.task_tracking.finish_file_operation.apply_async"),
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        consume.assert_called_once()
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        assert parent.result_data["failed_document_ids"] == [excluded.pk]
        child = parent.children.get(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        task_postrun_handler(
            task=consume_file,
            task_id=child.task_id,
            state="SUCCESS",
            retval={"document_id": 100},
        )
        finalizer = parent.children.get(task_type=PaperlessTask.TaskType.BULK_DELETE)
        assert finalizer.input_data["delete_ids"] == [included.pk]
        finish_file_operation.apply(
            kwargs=finalizer.input_data,
            task_id=finalizer.task_id,
            throw=True,
        )
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.FAILURE
    assert parent.result_data["failed_document_ids"] == [excluded.pk]
    assert not Document.objects.filter(pk=included.pk).exists()
    assert Document.objects.filter(pk=excluded.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_merge_with_no_valid_inputs_fails(operation, pdf_documents):
    parent, kwargs = operation
    for doc in pdf_documents:
        doc.source_path.unlink()
    kwargs.update(
        operation="merge",
        document_ids=[doc.pk for doc in pdf_documents],
        parameters={},
    )
    execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=False)
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.FAILURE
    assert not parent.children.exists()


@pytest.mark.django_db(transaction=True)
def test_split_waits_for_every_output_before_recovery(operation, pdf_documents):
    from documents.task_tracking import finish_file_operation
    from documents.tasks import consume_file

    parent, kwargs = operation
    doc = pdf_documents[0]
    kwargs.update(
        operation="split",
        document_ids=[doc.pk],
        parameters={"pages": [[1], [1]], "delete_originals": True},
    )
    with (
        mock.patch("documents.tasks.consume_file.apply_async"),
        mock.patch(
            "documents.task_tracking.finish_file_operation.apply_async",
        ) as finalize,
    ):
        execute_bulk_operation.apply(kwargs=kwargs, task_id=parent.task_id, throw=True)
        children = list(
            parent.children.filter(task_type=PaperlessTask.TaskType.CONSUME_FILE),
        )
        assert len(children) == 2
        complete(children[0], "FAILURE")
        finalize.assert_not_called()
        parent.refresh_from_db()
        assert parent.status == PaperlessTask.Status.STARTED
        task_postrun_handler(
            task=consume_file,
            task_id=children[1].task_id,
            state="SUCCESS",
            retval={"document_id": 100},
        )
        finalize.assert_called_once()
        finalizer = parent.children.get(task_type=PaperlessTask.TaskType.BULK_DELETE)
        finish_file_operation.apply(
            kwargs=finalizer.input_data,
            task_id=finalizer.task_id,
            throw=True,
        )
    parent.refresh_from_db()
    assert parent.status == PaperlessTask.Status.FAILURE
    doc.refresh_from_db()
    assert not doc.is_deleted
