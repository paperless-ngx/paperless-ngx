"""Tests for the /api/tasks/ endpoint.

Covers:
- v10 serializer (new field names)
- v9 serializer (backwards-compatible field names)
- Filtering, ordering, acknowledge, acknowledge_all, summary, active, run
"""

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import PaperlessTask
from documents.tests.factories import PaperlessTaskFactory

pytestmark = pytest.mark.api

ENDPOINT = "/api/tasks/"
ACCEPT_V10 = "application/json; version=10"
ACCEPT_V9 = "application/json; version=9"


@pytest.mark.django_db()
class TestGetTasksV10:
    def test_list_returns_tasks(self, admin_client: APIClient) -> None:
        """GET /api/tasks/ returns all tasks visible to the admin."""
        PaperlessTaskFactory.create_batch(2)

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_related_document_ids_populated_from_result_data(
        self,
        admin_client: APIClient,
    ) -> None:
        """related_document_ids includes the consumed document_id from result_data."""
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"document_id": 7},
        )

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document_ids"] == [7]

    def test_related_document_ids_includes_duplicate_of(
        self,
        admin_client: APIClient,
    ) -> None:
        """related_document_ids includes duplicate_of when the file was already archived."""
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": 12},
        )

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document_ids"] == [12]

    def test_filter_by_task_type(self, admin_client: APIClient) -> None:
        """?task_type= filters results to tasks of that type only."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER)

        response = admin_client.get(
            ENDPOINT,
            {"task_type": PaperlessTask.TaskType.TRAIN_CLASSIFIER},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_type"] == PaperlessTask.TaskType.TRAIN_CLASSIFIER

    def test_filter_by_status(self, admin_client: APIClient) -> None:
        """?status= filters results to tasks with that status only."""
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)

        response = admin_client.get(
            ENDPOINT,
            {"status": PaperlessTask.Status.SUCCESS},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["status"] == PaperlessTask.Status.SUCCESS

    def test_filter_by_task_id(self, admin_client: APIClient) -> None:
        """?task_id= returns only the task with that UUID."""
        task = PaperlessTaskFactory()
        PaperlessTaskFactory()  # unrelated task that should not appear

        response = admin_client.get(ENDPOINT, {"task_id": task.task_id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_id"] == task.task_id

    def test_filter_by_acknowledged(self, admin_client: APIClient) -> None:
        """?acknowledged=false returns only tasks that have not been acknowledged."""
        PaperlessTaskFactory(acknowledged=False)
        PaperlessTaskFactory(acknowledged=True)

        response = admin_client.get(ENDPOINT, {"acknowledged": "false"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["acknowledged"] is False

    def test_filter_is_complete_true(self, admin_client: APIClient) -> None:
        """?is_complete=true returns only SUCCESS and FAILURE tasks."""
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE)

        response = admin_client.get(ENDPOINT, {"is_complete": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        returned_statuses = {t["status"] for t in response.data}
        assert returned_statuses == {
            PaperlessTask.Status.SUCCESS,
            PaperlessTask.Status.FAILURE,
        }

    def test_filter_is_complete_false(self, admin_client: APIClient) -> None:
        """?is_complete=false returns only PENDING and STARTED tasks."""
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.STARTED)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)

        response = admin_client.get(ENDPOINT, {"is_complete": "false"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        returned_statuses = {t["status"] for t in response.data}
        assert returned_statuses == {
            PaperlessTask.Status.PENDING,
            PaperlessTask.Status.STARTED,
        }

    def test_default_ordering_is_newest_first(self, admin_client: APIClient) -> None:
        """Tasks are returned in descending date_created order (newest first)."""
        base = timezone.now()
        t1 = PaperlessTaskFactory(date_created=base)
        t2 = PaperlessTaskFactory(date_created=base + timedelta(seconds=1))
        t3 = PaperlessTaskFactory(date_created=base + timedelta(seconds=2))

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        ids = [t["task_id"] for t in response.data]
        assert ids == [t3.task_id, t2.task_id, t1.task_id]

    def test_list_scoped_to_own_tasks_for_regular_user(
        self,
        admin_user: User,
        regular_user: User,
    ) -> None:
        """Regular users see only tasks they own; tasks owned by others or unowned are hidden."""
        regular_user.user_permissions.add(
            Permission.objects.get(codename="view_paperlesstask"),
        )

        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V10)

        PaperlessTaskFactory(owner=admin_user)  # other user — not visible
        PaperlessTaskFactory()  # unowned (system task) — not visible
        own_task = PaperlessTaskFactory(owner=regular_user)

        response = client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_id"] == own_task.task_id

    def test_list_admin_sees_all_tasks(
        self,
        admin_client: APIClient,
        admin_user: User,
        regular_user: User,
    ) -> None:
        """Admin users see all tasks regardless of owner."""
        PaperlessTaskFactory(owner=admin_user)
        PaperlessTaskFactory()  # unowned system task
        PaperlessTaskFactory(owner=regular_user)

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3


@pytest.mark.django_db()
class TestGetTasksV9:
    def test_task_name_equals_task_type_value(self, v9_client: APIClient) -> None:
        """task_name mirrors the task_type value for v9 backwards compatibility."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_name"] == "consume_file"

    def test_task_file_name_from_input_data(self, v9_client: APIClient) -> None:
        """task_file_name is read from input_data['filename']."""
        PaperlessTaskFactory(input_data={"filename": "report.pdf"})

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_file_name"] == "report.pdf"

    def test_task_file_name_none_when_no_filename_key(
        self,
        v9_client: APIClient,
    ) -> None:
        """task_file_name is None when filename is absent from input_data."""
        PaperlessTaskFactory(input_data={})

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_file_name"] is None

    def test_type_scheduled_maps_to_scheduled_task(self, v9_client: APIClient) -> None:
        """trigger_source=scheduled maps to type='SCHEDULED_TASK' in v9."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SCHEDULED)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "SCHEDULED_TASK"

    def test_type_system_maps_to_auto_task(self, v9_client: APIClient) -> None:
        """trigger_source=system maps to type='AUTO_TASK' in v9."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SYSTEM)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "AUTO_TASK"

    def test_type_web_ui_maps_to_manual_task(self, v9_client: APIClient) -> None:
        """trigger_source=web_ui maps to type='MANUAL_TASK' in v9."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.WEB_UI)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "MANUAL_TASK"

    def test_type_manual_maps_to_manual_task(self, v9_client: APIClient) -> None:
        """trigger_source=manual maps to type='MANUAL_TASK' in v9."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.MANUAL)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "MANUAL_TASK"

    def test_related_document_from_result_data_document_id(
        self,
        v9_client: APIClient,
    ) -> None:
        """related_document is taken from result_data['document_id'] in v9."""
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"document_id": 99},
        )

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document"] == 99

    def test_related_document_none_when_no_result_data(
        self,
        v9_client: APIClient,
    ) -> None:
        """related_document is None when result_data is absent in v9."""
        PaperlessTaskFactory(result_data=None)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document"] is None

    def test_duplicate_documents_from_result_data(self, v9_client: APIClient) -> None:
        """duplicate_documents includes duplicate_of from result_data in v9."""
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": 55},
        )

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["duplicate_documents"] == [55]

    def test_duplicate_documents_empty_when_no_result_data(
        self,
        v9_client: APIClient,
    ) -> None:
        """duplicate_documents is an empty list when result_data is absent in v9."""
        PaperlessTaskFactory(result_data=None)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["duplicate_documents"] == []

    def test_filter_by_task_name_maps_to_task_type(self, v9_client: APIClient) -> None:
        """?task_name=consume_file filter maps to the task_type field for v9 compatibility."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER)

        response = v9_client.get(ENDPOINT, {"task_name": "consume_file"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_name"] == "consume_file"

    def test_filter_by_type_maps_to_trigger_source(self, v9_client: APIClient) -> None:
        """?type=SCHEDULED_TASK filter maps to trigger_source=scheduled for v9 compatibility."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SCHEDULED)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.WEB_UI)

        response = v9_client.get(ENDPOINT, {"type": "SCHEDULED_TASK"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["type"] == "SCHEDULED_TASK"


@pytest.mark.django_db()
class TestAcknowledge:
    def test_returns_count(self, admin_client: APIClient) -> None:
        """POST acknowledge/ returns the count of tasks that were acknowledged."""
        task1 = PaperlessTaskFactory()
        task2 = PaperlessTaskFactory()

        response = admin_client.post(
            ENDPOINT + "acknowledge/",
            {"tasks": [task1.id, task2.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 2}

    def test_acknowledged_tasks_excluded_from_unacked_filter(
        self,
        admin_client: APIClient,
    ) -> None:
        """Acknowledged tasks no longer appear when filtering with ?acknowledged=false."""
        task = PaperlessTaskFactory()
        admin_client.post(
            ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
            format="json",
        )

        response = admin_client.get(ENDPOINT, {"acknowledged": "false"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_requires_change_permission(self, user_client: APIClient) -> None:
        """Regular users without change_paperlesstask permission receive 403."""
        task = PaperlessTaskFactory()

        response = user_client.post(
            ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_succeeds_with_change_permission(self, regular_user: User) -> None:
        """Users granted change_paperlesstask permission can acknowledge tasks."""
        regular_user.user_permissions.add(
            Permission.objects.get(codename="change_paperlesstask"),
        )
        regular_user.save()

        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V10)

        task = PaperlessTaskFactory()
        response = client.post(
            ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
class TestAcknowledgeAll:
    def test_marks_only_completed_tasks(self, admin_client: APIClient) -> None:
        """acknowledge_all/ marks only SUCCESS and FAILURE tasks as acknowledged."""
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=False)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE, acknowledged=False)
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 2}

    def test_skips_already_acknowledged(self, admin_client: APIClient) -> None:
        """acknowledge_all/ does not re-acknowledge tasks that are already acknowledged."""
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=True)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 1}

    def test_skips_pending_and_started(self, admin_client: APIClient) -> None:
        """acknowledge_all/ does not touch PENDING or STARTED tasks."""
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.STARTED)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 0}

    def test_includes_revoked(self, admin_client: APIClient) -> None:
        """acknowledge_all/ marks REVOKED tasks as acknowledged."""
        PaperlessTaskFactory(status=PaperlessTask.Status.REVOKED, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 1}


@pytest.mark.django_db()
class TestSummary:
    def test_returns_per_type_totals(self, admin_client: APIClient) -> None:
        """summary/ returns per-type counts of total, success, and failure tasks."""
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.SUCCESS,
        )
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.FAILURE,
        )
        PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
            status=PaperlessTask.Status.SUCCESS,
        )

        response = admin_client.get(ENDPOINT + "summary/")

        assert response.status_code == status.HTTP_200_OK
        by_type = {item["task_type"]: item for item in response.data}
        assert by_type["consume_file"]["total_count"] == 2
        assert by_type["consume_file"]["success_count"] == 1
        assert by_type["consume_file"]["failure_count"] == 1
        assert by_type["train_classifier"]["total_count"] == 1

    def test_rejects_invalid_days_param(self, admin_client: APIClient) -> None:
        """?days=invalid returns 400 with an error message."""
        response = admin_client.get(ENDPOINT + "summary/", {"days": "invalid"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "days" in response.data


@pytest.mark.django_db()
class TestActive:
    def test_returns_pending_and_started_only(self, admin_client: APIClient) -> None:
        """active/ returns only tasks in PENDING or STARTED status."""
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.STARTED)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE)

        response = admin_client.get(ENDPOINT + "active/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        active_statuses = {t["status"] for t in response.data}
        assert active_statuses == {
            PaperlessTask.Status.PENDING,
            PaperlessTask.Status.STARTED,
        }

    def test_excludes_revoked_tasks_from_active(self, admin_client: APIClient) -> None:
        """active/ excludes REVOKED tasks."""
        PaperlessTaskFactory(status=PaperlessTask.Status.REVOKED)

        response = admin_client.get(ENDPOINT + "active/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@pytest.mark.django_db()
class TestRun:
    def test_forbidden_for_regular_user(self, user_client: APIClient) -> None:
        """Regular users without add_paperlesstask permission receive 403 from run/."""
        response = user_client.post(
            ENDPOINT + "run/",
            {"task_type": PaperlessTask.TaskType.TRAIN_CLASSIFIER},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dispatches_via_apply_async_with_manual_trigger_header(
        self,
        admin_client: APIClient,
    ) -> None:
        """run/ dispatches the task via apply_async with trigger_source=manual in headers."""
        fake_task_id = str(uuid.uuid4())
        mock_async_result = mock.Mock()
        mock_async_result.id = fake_task_id

        mock_apply_async = mock.Mock(return_value=mock_async_result)

        with mock.patch(
            "documents.views.train_classifier.apply_async",
            mock_apply_async,
        ):
            response = admin_client.post(
                ENDPOINT + "run/",
                {"task_type": PaperlessTask.TaskType.TRAIN_CLASSIFIER},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"task_id": fake_task_id}
        mock_apply_async.assert_called_once_with(
            kwargs={},
            headers={"trigger_source": "manual"},
        )

    def test_returns_400_for_consume_file(self, admin_client: APIClient) -> None:
        """consume_file cannot be manually triggered via the run endpoint."""
        response = admin_client.post(
            ENDPOINT + "run/",
            {"task_type": PaperlessTask.TaskType.CONSUME_FILE},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_400_for_invalid_task_type(self, admin_client: APIClient) -> None:
        """run/ returns 400 for an unrecognized task_type value."""
        response = admin_client.post(
            ENDPOINT + "run/",
            {"task_type": "not_a_real_type"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sanity_check_dispatched_with_correct_kwargs(
        self,
        admin_client: APIClient,
    ) -> None:
        """run/ dispatches sanity_check with raise_on_error=False and manual trigger header."""
        fake_task_id = str(uuid.uuid4())
        mock_async_result = mock.Mock()
        mock_async_result.id = fake_task_id

        mock_apply_async = mock.Mock(return_value=mock_async_result)

        with mock.patch(
            "documents.views.sanity_check.apply_async",
            mock_apply_async,
        ):
            response = admin_client.post(
                ENDPOINT + "run/",
                {"task_type": PaperlessTask.TaskType.SANITY_CHECK},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"task_id": fake_task_id}
        mock_apply_async.assert_called_once_with(
            kwargs={"raise_on_error": False},
            headers={"trigger_source": "manual"},
        )
