"""Request acceptance, worker execution, and task tracking."""

import json
import uuid
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import User
from pytest_mock import MockerFixture
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from documents.bulk_operations import execute_bulk_operation
from documents.models import Correspondent
from documents.models import Document
from documents.models import OcrTemplate
from documents.models import PaperlessTask
from documents.signals.handlers import before_task_publish_handler
from documents.signals.handlers import task_failure_handler
from documents.signals.handlers import task_postrun_handler
from documents.signals.handlers import task_revoked_handler
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import OcrTemplateFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global


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
        ("run_zone_ocr", "run_zone_ocr", {}),
    ],
)
def test_request_only_queues(bulk_setup, endpoint, operation, parameters):
    user, client, doc, _ = bulk_setup
    task_id = str(uuid.uuid4())
    data = {"documents": [doc.pk], "from_webui": True}
    if endpoint == "bulk_edit":
        data.update(method=operation, parameters=parameters)
    else:
        data.update(parameters)
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
        "trigger_source": "web_ui",
    }
    assert enqueue.call_args.kwargs["headers"]["trigger_source"] == "web_ui"


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRunZoneOcrBulkOperation:
    """Zone OCR runs as a tracked bulk operation."""

    @pytest.fixture
    def document(self) -> Document:
        return DocumentFactory()

    def test_queues_only_template_id_and_returns_tracked_task(
        self,
        mocker: MockerFixture,
        admin_client: APIClient,
        admin_user: User,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A zone OCR run request naming a template
        WHEN:
            - The request is posted to the API
        THEN:
            - Only the template id is queued, with a tracked task id returned
            - Extraction does not run in the request
        """
        template = OcrTemplateFactory()
        enqueue = mocker.patch("documents.views.execute_bulk_operation.apply_async")
        extract = mocker.patch("documents.bulk_edit.extract_zones")
        enqueue.return_value.id = "zone-ocr-task"
        response = admin_client.post(
            "/api/documents/run_zone_ocr/",
            {
                "documents": [document.pk],
                "template": template.pk,
                "from_webui": True,
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data == {"result": "OK", "task_id": "zone-ocr-task"}
        kwargs = enqueue.call_args.kwargs["kwargs"]
        assert json.loads(json.dumps(kwargs)) == {
            "operation": "run_zone_ocr",
            "document_ids": [document.pk],
            "parameters": {"template": template.pk},
            "user_id": admin_user.pk,
            "trigger_source": "web_ui",
        }
        extract.assert_not_called()

    def test_finishes_extraction_within_the_tracked_task(
        self,
        mocker: MockerFixture,
        admin_user: User,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A queued zone OCR run naming a template
        WHEN:
            - The tracked task executes it
        THEN:
            - Extraction is called synchronously with the requester
            - No further extraction task is enqueued
            - The result reports the operation and document count
        """
        template = OcrTemplateFactory()
        extract = mocker.patch("documents.bulk_edit.extract_zones")
        result = execute_bulk_operation(
            "run_zone_ocr",
            [document.pk],
            {"template": template.pk},
            admin_user.pk,
        )
        extract.assert_called_once_with(
            document_id=document.pk,
            template_id=template.pk,
            requester=admin_user,
        )
        extract.apply_async.assert_not_called()
        assert result == {"operation": "run_zone_ocr", "document_count": 1}

    def test_without_template_selects_for_the_requester(
        self,
        mocker: MockerFixture,
        admin_user: User,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A queued zone OCR run without a chosen template
        WHEN:
            - The tracked task executes it
        THEN:
            - Extraction receives the requesting user so templates are limited to
              those they can view
        """
        extract = mocker.patch("documents.bulk_edit.extract_zones")
        execute_bulk_operation("run_zone_ocr", [document.pk], {}, admin_user.pk)
        extract.assert_called_once_with(
            document_id=document.pk,
            template_id=None,
            requester=admin_user,
        )

    @pytest.mark.parametrize(
        "revoked",
        [
            pytest.param("document", id="document"),
            pytest.param("template", id="template"),
            pytest.param("user", id="user"),
        ],
    )
    def test_rechecks_access_before_extraction(
        self,
        mocker: MockerFixture,
        user_client: APIClient,
        regular_user: User,
        document: Document,
        revoked: str,
    ) -> None:
        """
        GIVEN:
            - A zone OCR run accepted for a user with access to the document
              and template
        WHEN:
            - Access to the document, the template, or the user is revoked before
              the tracked task executes
        THEN:
            - Execution raises PermissionDenied
            - Extraction never runs
        """
        grant_global(regular_user, "change_document")
        template = OcrTemplateFactory(owner=regular_user)
        enqueue = mocker.patch("documents.views.execute_bulk_operation.apply_async")
        enqueue.return_value.id = "zone-ocr-task"
        response = user_client.post(
            "/api/documents/run_zone_ocr/",
            {
                "documents": [document.pk],
                "template": template.pk,
            },
            format="json",
        )
        assert response.status_code == 200
        if revoked == "document":
            document.owner = UserFactory()
            document.save(update_fields=["owner"])
        elif revoked == "template":
            template.owner = UserFactory()
            template.save(update_fields=["owner"])
        else:
            User.objects.filter(pk=regular_user.pk).update(is_active=False)
        extract = mocker.patch("documents.bulk_edit.extract_zones")
        with pytest.raises(PermissionDenied):
            execute_bulk_operation(**enqueue.call_args.kwargs["kwargs"])
        extract.assert_not_called()

    def test_cannot_fall_back_to_matching_if_chosen_template_is_deleted(
        self,
        mocker: MockerFixture,
        admin_user: User,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A queued zone OCR run naming a template that no longer exists
        WHEN:
            - The tracked task executes it
        THEN:
            - OcrTemplate.DoesNotExist is raised instead of falling back to
              template matching
            - Extraction never runs
        """
        extract = mocker.patch("documents.bulk_edit.extract_zones")
        with pytest.raises(OcrTemplate.DoesNotExist):
            execute_bulk_operation(
                "run_zone_ocr",
                [document.pk],
                {"template": 999},
                admin_user.pk,
            )
        extract.assert_not_called()


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
def test_document_action_runs_with_user_in_worker(bulk_setup):
    user, _, doc, _ = bulk_setup
    with mock.patch("documents.bulk_edit.rotate") as rotate:
        result = execute_bulk_operation(
            "rotate",
            [doc.pk],
            {"degrees": 90},
            user.pk,
            trigger_source="web_ui",
        )
    rotate.assert_called_once_with(
        [doc.pk],
        degrees=90,
        user=user,
        trigger_source="web_ui",
    )
    assert result == {"operation": "rotate", "document_count": 1}


@pytest.mark.django_db
def test_delete_task_without_audit_log(bulk_setup, settings):
    user, _, doc, _ = bulk_setup
    settings.AUDIT_LOG_ENABLED = False
    with mock.patch(
        "documents.bulk_operations.set_actor",
        side_effect=AssertionError("audit context must not be entered"),
    ):
        result = execute_bulk_operation("delete", [doc.pk], {}, user.pk)
    assert result == {"operation": "delete", "document_count": 1}
    assert not Document.objects.filter(pk=doc.pk).exists()


@pytest.mark.django_db
def test_metadata_task_without_audit_log(bulk_setup, settings):
    user, _, doc, correspondent = bulk_setup
    settings.AUDIT_LOG_ENABLED = False
    with (
        mock.patch(
            "documents.bulk_operations.set_actor",
            side_effect=AssertionError("audit context must not be entered"),
        ),
        mock.patch("documents.bulk_operations.bulk_update_documents"),
    ):
        result = execute_bulk_operation(
            "set_correspondent",
            [doc.pk],
            {"correspondent": correspondent.pk},
            user.pk,
        )
    doc.refresh_from_db()
    assert doc.correspondent_id == correspondent.pk
    assert result == {"operation": "set_correspondent", "document_count": 1}


@pytest.mark.django_db
def test_document_action_queue_contains_only_serializable_parameters(bulk_setup):
    user, client, doc, _ = bulk_setup
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue:
        enqueue.return_value.id = "rotate-task"
        response = client.post(
            "/api/documents/rotate/",
            {"documents": [doc.pk], "degrees": 90, "from_webui": True},
            format="json",
        )
    assert response.data == {"result": "OK", "task_id": "rotate-task"}
    assert enqueue.call_args.kwargs["kwargs"] == {
        "operation": "rotate",
        "document_ids": [doc.pk],
        "parameters": {"degrees": 90, "source_mode": "latest_version"},
        "user_id": user.pk,
        "trigger_source": "web_ui",
    }


@pytest.mark.django_db
def test_reprocess_keeps_bulk_audit_entry(bulk_setup, settings):
    user, _, doc, _ = bulk_setup
    settings.AUDIT_LOG_ENABLED = True
    LogEntry.objects.all().delete()
    with mock.patch("documents.bulk_edit.reprocess"):
        execute_bulk_operation("reprocess", [doc.pk], {}, user.pk)
    entry = LogEntry.objects.get_for_object(doc).get()
    assert entry.changes_dict["checksum"] == [doc.checksum, doc.checksum]
    assert entry.actor_id == user.pk


@pytest.mark.django_db
def test_workflow_runs_in_tracked_task_instead_of_dispatching_another(bulk_setup):
    user, _, doc, _ = bulk_setup
    with mock.patch("documents.bulk_edit.run_workflows_for_documents") as run:
        execute_bulk_operation(
            "run_workflow",
            [doc.pk],
            {"workflow": 7, "filter_documents": False},
            user.pk,
        )
    run.assert_called_once_with(
        document_ids=[doc.pk],
        workflow_id=7,
        filter_documents=False,
    )


@pytest.mark.django_db
def test_delete_failure_propagates_from_worker(bulk_setup):
    user, _, doc, _ = bulk_setup
    with mock.patch(
        "documents.models.Document.delete",
        side_effect=RuntimeError("delete failed"),
    ):
        with pytest.raises(RuntimeError, match="delete failed"):
            execute_bulk_operation("delete", [doc.pk], {}, user.pk)
    assert Document.objects.filter(pk=doc.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operation,parameters,preparation",
    [
        ("rotate", {"degrees": 90}, "rotate_pdf"),
        ("split", {"pages": [[1]]}, "build_pdfs"),
        ("delete_pages", {"pages": [1]}, "remove_pages"),
    ],
)
def test_preparation_failure_propagates_from_worker(
    bulk_setup,
    operation,
    parameters,
    preparation,
):
    user, _, doc, _ = bulk_setup
    doc.mime_type = "application/pdf"
    doc.save()
    with (
        mock.patch(
            f"documents.bulk_edit.pdf_ops.{preparation}",
            side_effect=RuntimeError("preparation failed"),
        ),
        mock.patch("documents.bulk_edit.consume_file.apply_async") as consume,
        mock.patch("documents.bulk_edit.consume_file.s") as consume_signature,
        pytest.raises(
            RuntimeError,
            match="Rotation failed" if operation == "rotate" else "preparation failed",
        ),
    ):
        execute_bulk_operation(operation, [doc.pk], parameters, user.pk)
    consume.assert_not_called()
    consume_signature.assert_not_called()


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
def test_queued_delete_is_tracked_as_bulk_delete(bulk_setup):
    user, _, doc, _ = bulk_setup
    before_task_publish_handler(
        headers={"task": execute_bulk_operation.name, "id": "delete-task"},
        body=(
            (),
            {"operation": "delete", "document_ids": [doc.pk], "user_id": user.pk},
            {},
        ),
    )
    task = PaperlessTask.objects.get(task_id="delete-task")
    assert task.task_type == PaperlessTask.TaskType.BULK_DELETE
    assert task.owner_id == user.pk


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
            "task": execute_bulk_operation.name,
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
            task_revoked_handler(
                sender=execute_bulk_operation,
                request=mock.Mock(id=task_id),
                expired=True,
            )
        elif outcome == "failure":
            task_failure_handler(
                sender=execute_bulk_operation,
                task_id=task_id,
                exception=ValueError("Could not update"),
            )
        else:
            task_postrun_handler(
                task=execute_bulk_operation,
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
def test_legacy_trash_queues_without_deleting_in_request(bulk_setup):
    user, client, doc, _ = bulk_setup
    data = {"documents": [doc.pk], "method": "delete", "parameters": {}}
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue:
        enqueue.return_value.id = "delete-task"
        response = client.post(
            "/api/documents/bulk_edit/",
            data,
            format="json",
            HTTP_ACCEPT="application/json; version=9",
        )
    assert response.status_code == 200
    assert response.data == {"result": "OK", "task_id": "delete-task"}
    assert Document.objects.filter(pk=doc.pk).exists()
    assert enqueue.call_args.kwargs["kwargs"] == {
        "operation": "delete",
        "document_ids": [doc.pk],
        "parameters": {},
        "user_id": user.pk,
        "trigger_source": "api_upload",
    }


@pytest.mark.django_db
def test_dedicated_trash_queues_without_deleting_in_request(bulk_setup):
    user, client, doc, _ = bulk_setup
    with mock.patch("documents.views.execute_bulk_operation.apply_async") as enqueue:
        enqueue.return_value.id = "delete-task"
        response = client.post(
            "/api/documents/delete/",
            {"documents": [doc.pk]},
            format="json",
        )
    assert response.status_code == 200
    assert response.data == {"result": "OK", "task_id": "delete-task"}
    assert Document.objects.filter(pk=doc.pk).exists()
    assert enqueue.call_args.kwargs["kwargs"] == {
        "operation": "delete",
        "document_ids": [doc.pk],
        "parameters": {},
        "user_id": user.pk,
        "trigger_source": "api_upload",
    }
