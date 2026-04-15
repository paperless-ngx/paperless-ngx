"""Tests for the /api/tasks/ endpoint.

Covers:
- v10 serializer (new field names)
- v9 serializer (backwards-compatible field names)
- Filtering, ordering, acknowledge, acknowledge_all, summary, active, run
"""

import uuid
from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import PaperlessTask
from documents.tests.factories import PaperlessTaskFactory

ENDPOINT = "/api/tasks/"
ACCEPT_V10 = "application/json; version=10"
ACCEPT_V9 = "application/json; version=9"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def superuser(db) -> User:
    return User.objects.create_superuser(username="admin", password="admin")


@pytest.fixture()
def regular_user(db) -> User:
    return User.objects.create_user(username="regular", password="regular")


@pytest.fixture()
def admin_client(superuser: User) -> APIClient:
    """Authenticated admin client sending v10 Accept header."""
    client = APIClient()
    client.force_authenticate(user=superuser)
    client.credentials(HTTP_ACCEPT=ACCEPT_V10)
    return client


@pytest.fixture()
def v9_client(superuser: User) -> APIClient:
    """Authenticated admin client sending v9 Accept header."""
    client = APIClient()
    client.force_authenticate(user=superuser)
    client.credentials(HTTP_ACCEPT=ACCEPT_V9)
    return client


@pytest.fixture()
def user_client(regular_user: User) -> APIClient:
    """Authenticated regular-user client sending v10 Accept header."""
    client = APIClient()
    client.force_authenticate(user=regular_user)
    client.credentials(HTTP_ACCEPT=ACCEPT_V10)
    return client


# ---------------------------------------------------------------------------
# TestGetTasksV10
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestGetTasksV10:
    def test_list_returns_tasks(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory.create_batch(2)

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_response_has_v10_fields(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(
            input_data={"filename": "doc.pdf"},
            result_data={"document_id": 42},
            result_message="Done",
        )

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        task_data = response.data[0]
        assert "task_type" in task_data
        assert "trigger_source" in task_data
        assert "input_data" in task_data
        assert "result_data" in task_data
        assert "result_message" in task_data
        assert "related_document_ids" in task_data

    def test_related_document_ids_populated_from_result_data(
        self,
        admin_client: APIClient,
    ) -> None:
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"document_id": 7},
        )

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document_ids"] == [7]

    def test_filter_by_task_type(self, admin_client: APIClient) -> None:
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
        task = PaperlessTaskFactory()
        PaperlessTaskFactory()  # another task that should not appear

        response = admin_client.get(ENDPOINT, {"task_id": task.task_id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_id"] == task.task_id

    def test_filter_by_acknowledged(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(acknowledged=False)
        PaperlessTaskFactory(acknowledged=True)

        response = admin_client.get(ENDPOINT, {"acknowledged": "false"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["acknowledged"] is False

    def test_filter_is_complete_true(self, admin_client: APIClient) -> None:
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

    def test_default_ordering_is_newest_first(self, admin_client: APIClient) -> None:
        t1 = PaperlessTaskFactory()
        PaperlessTaskFactory()  # middle task -- not checked directly
        t3 = PaperlessTaskFactory()

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        ids = [t["task_id"] for t in response.data]
        assert ids[0] == t3.task_id
        assert ids[-1] == t1.task_id

    def test_no_v9_only_fields_present(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory()

        response = admin_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        task_data = response.data[0]
        assert "task_name" not in task_data
        assert "task_file_name" not in task_data


# ---------------------------------------------------------------------------
# TestGetTasksV9
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestGetTasksV9:
    def test_response_has_v9_fields(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(input_data={"filename": "invoice.pdf"})

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        task_data = response.data[0]
        assert "task_name" in task_data
        assert "task_file_name" in task_data
        assert "type" in task_data
        assert "result" in task_data
        assert "related_document" in task_data
        assert "duplicate_documents" in task_data

    def test_no_v10_only_fields_present(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory()

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        task_data = response.data[0]
        assert "task_type" not in task_data
        assert "trigger_source" not in task_data
        assert "input_data" not in task_data

    def test_task_name_equals_task_type_value(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_name"] == "consume_file"

    def test_task_file_name_from_input_data(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(input_data={"filename": "report.pdf"})

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_file_name"] == "report.pdf"

    def test_task_file_name_none_when_no_filename_key(
        self,
        v9_client: APIClient,
    ) -> None:
        PaperlessTaskFactory(input_data={})

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_file_name"] is None

    def test_type_scheduled_maps_to_scheduled_task(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SCHEDULED)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "SCHEDULED_TASK"

    def test_type_system_maps_to_auto_task(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SYSTEM)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "AUTO_TASK"

    def test_type_web_ui_maps_to_manual_task(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.WEB_UI)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "MANUAL_TASK"

    def test_type_manual_maps_to_manual_task(self, v9_client: APIClient) -> None:
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.MANUAL)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == "MANUAL_TASK"

    def test_related_document_from_result_data_document_id(
        self,
        v9_client: APIClient,
    ) -> None:
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
        PaperlessTaskFactory(result_data=None)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["related_document"] is None

    def test_duplicate_documents_from_result_data(self, v9_client: APIClient) -> None:
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
        PaperlessTaskFactory(result_data=None)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["duplicate_documents"] == []

    def test_filter_by_task_name_maps_to_task_type(self, v9_client: APIClient) -> None:
        """v9 ?task_name=consume_file filter maps to the task_type field."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER)

        response = v9_client.get(ENDPOINT, {"task_name": "consume_file"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_name"] == "consume_file"


# ---------------------------------------------------------------------------
# TestAcknowledge
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestAcknowledge:
    def test_returns_count(self, admin_client: APIClient) -> None:
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
        task = PaperlessTaskFactory()

        response = user_client.post(
            ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_succeeds_with_change_permission(self, regular_user: User) -> None:
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

    def test_list_is_owner_aware(
        self,
        superuser: User,
        regular_user: User,
    ) -> None:
        """The task list only shows tasks the user owns or that are unowned."""
        regular_user.user_permissions.add(
            Permission.objects.get(codename="view_paperlesstask"),
        )

        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V10)

        PaperlessTaskFactory(owner=superuser)
        shared_task = PaperlessTaskFactory()
        own_task = PaperlessTaskFactory(owner=regular_user)

        response = client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        returned_task_ids = {t["task_id"] for t in response.data}
        assert shared_task.task_id in returned_task_ids
        assert own_task.task_id in returned_task_ids


# ---------------------------------------------------------------------------
# TestAcknowledgeAll
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestAcknowledgeAll:
    def test_marks_only_completed_tasks(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=False)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE, acknowledged=False)
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 2}

    def test_skips_already_acknowledged(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=True)
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 1}

    def test_skips_pending_and_started(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.STARTED)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 0}

    def test_includes_revoked(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.REVOKED, acknowledged=False)

        response = admin_client.post(ENDPOINT + "acknowledge_all/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"result": 1}


# ---------------------------------------------------------------------------
# TestSummary
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestSummary:
    def test_returns_per_type_totals(self, admin_client: APIClient) -> None:
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

    def test_contains_expected_fields(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)

        response = admin_client.get(ENDPOINT + "summary/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        item = response.data[0]
        for field in (
            "task_type",
            "total_count",
            "pending_count",
            "success_count",
            "failure_count",
            "avg_duration_seconds",
            "avg_wait_time_seconds",
            "last_run",
            "last_success",
            "last_failure",
        ):
            assert field in item, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# TestActive
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestActive:
    def test_returns_pending_and_started_only(self, admin_client: APIClient) -> None:
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

    def test_excludes_completed_tasks(self, admin_client: APIClient) -> None:
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE)
        PaperlessTaskFactory(status=PaperlessTask.Status.REVOKED)

        response = admin_client.get(ENDPOINT + "active/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------


@pytest.mark.django_db()
class TestRun:
    def test_forbidden_for_regular_user(self, user_client: APIClient) -> None:
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
