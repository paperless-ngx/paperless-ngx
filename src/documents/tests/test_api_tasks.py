"""Tests for the /api/tasks/ endpoint.

Covers:
- v10 serializer (new field names)
- v9 serializer (backwards-compatible field names)
- Filtering, ordering, acknowledge, summary, active, run
"""

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import PaperlessTask
from documents.tests.factories import DocumentFactory
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

    def test_list_scoped_to_own_and_unowned_tasks_for_regular_user(
        self,
        admin_user: User,
        regular_user: User,
    ) -> None:
        """Regular users see their own tasks and unowned (system) tasks; other users' tasks are hidden."""
        regular_user.user_permissions.add(
            Permission.objects.get(codename="view_paperlesstask"),
        )

        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V10)

        PaperlessTaskFactory(owner=admin_user)  # other user — not visible
        unowned_task = PaperlessTaskFactory()  # unowned (system task) — visible
        own_task = PaperlessTaskFactory(owner=regular_user)

        response = client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        visible_ids = {t["task_id"] for t in response.data}
        assert visible_ids == {own_task.task_id, unowned_task.task_id}

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
    @pytest.mark.parametrize(
        ("task_type", "expected_task_name"),
        [
            pytest.param(
                PaperlessTask.TaskType.CONSUME_FILE,
                "consume_file",
                id="consume_file-passthrough",
            ),
            pytest.param(
                PaperlessTask.TaskType.SANITY_CHECK,
                "check_sanity",
                id="sanity_check-remapped",
            ),
            pytest.param(
                PaperlessTask.TaskType.LLM_INDEX,
                "llmindex_update",
                id="llm_index-remapped",
            ),
        ],
    )
    def test_task_name_mapping(
        self,
        v9_client: APIClient,
        task_type: PaperlessTask.TaskType,
        expected_task_name: str,
    ) -> None:
        """v9 task_name is either a direct pass-through or a legacy remap of task_type."""
        PaperlessTaskFactory(task_type=task_type)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["task_name"] == expected_task_name

    @pytest.mark.parametrize(
        ("trigger_source", "expected_type"),
        [
            pytest.param(
                PaperlessTask.TriggerSource.SCHEDULED,
                "scheduled_task",
                id="scheduled",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.SYSTEM,
                "auto_task",
                id="system",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.EMAIL_CONSUME,
                "auto_task",
                id="email_consume",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.FOLDER_CONSUME,
                "auto_task",
                id="folder_consume",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.WEB_UI,
                "manual_task",
                id="web_ui",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.MANUAL,
                "manual_task",
                id="manual",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.API_UPLOAD,
                "manual_task",
                id="api_upload",
            ),
        ],
    )
    def test_trigger_source_maps_to_v9_type(
        self,
        v9_client: APIClient,
        trigger_source: PaperlessTask.TriggerSource,
        expected_type: str,
    ) -> None:
        """Every TriggerSource value maps to the correct v9 type string."""
        PaperlessTaskFactory(trigger_source=trigger_source)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["type"] == expected_type

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
        doc = DocumentFactory.create(title="Duplicate Target")
        PaperlessTaskFactory(
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": doc.pk},
        )

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        dupes = response.data[0]["duplicate_documents"]
        assert len(dupes) == 1
        assert dupes[0]["id"] == doc.pk
        assert dupes[0]["title"] == doc.title
        assert "deleted_at" in dupes[0]

    def test_duplicate_documents_empty_when_no_result_data(
        self,
        v9_client: APIClient,
    ) -> None:
        """duplicate_documents is an empty list when result_data is absent in v9."""
        PaperlessTaskFactory(result_data=None)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["duplicate_documents"] == []

    def test_status_remapped_to_uppercase(self, v9_client: APIClient) -> None:
        """v9 status values are uppercase Celery state strings."""
        PaperlessTaskFactory(status=PaperlessTask.Status.SUCCESS)
        PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        PaperlessTaskFactory(status=PaperlessTask.Status.FAILURE)

        response = v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        statuses = {t["status"] for t in response.data}
        assert statuses == {"SUCCESS", "PENDING", "FAILURE"}

    def test_filter_by_task_name_maps_old_value(self, v9_client: APIClient) -> None:
        """?task_name=check_sanity maps to task_type=sanity_check in v9."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.SANITY_CHECK)
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)

        response = v9_client.get(ENDPOINT, {"task_name": "check_sanity"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_name"] == "check_sanity"

    def test_v9_non_staff_sees_own_and_unowned_tasks(
        self,
        admin_user: User,
        regular_user: User,
    ) -> None:
        """Non-staff users see their own tasks plus unowned tasks via v9 API."""
        regular_user.user_permissions.add(
            Permission.objects.get(codename="view_paperlesstask"),
        )

        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V9)

        PaperlessTaskFactory(owner=admin_user)  # other user, not visible
        PaperlessTaskFactory(owner=None)  # unowned, visible in v9
        PaperlessTaskFactory(owner=regular_user)  # own task, visible

        response = client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_filter_by_task_name_maps_to_task_type(self, v9_client: APIClient) -> None:
        """?task_name=consume_file filter maps to the task_type field for v9 compatibility."""
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.CONSUME_FILE)
        PaperlessTaskFactory(task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER)

        response = v9_client.get(ENDPOINT, {"task_name": "consume_file"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["task_name"] == "consume_file"

    def test_filter_by_type_scheduled_task(self, v9_client: APIClient) -> None:
        """?type=scheduled_task matches trigger_source=scheduled only."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SCHEDULED)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.WEB_UI)

        response = v9_client.get(ENDPOINT, {"type": "scheduled_task"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["type"] == "scheduled_task"

    def test_filter_by_type_auto_task_includes_all_auto_sources(
        self,
        v9_client: APIClient,
    ) -> None:
        """?type=auto_task matches system, email_consume, and folder_consume tasks."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.SYSTEM)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.EMAIL_CONSUME)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.FOLDER_CONSUME)
        PaperlessTaskFactory(
            trigger_source=PaperlessTask.TriggerSource.MANUAL,
        )  # excluded

        response = v9_client.get(ENDPOINT, {"type": "auto_task"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        assert all(t["type"] == "auto_task" for t in response.data)

    def test_filter_by_type_manual_task_includes_all_manual_sources(
        self,
        v9_client: APIClient,
    ) -> None:
        """?type=manual_task matches manual, web_ui, and api_upload tasks."""
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.MANUAL)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.WEB_UI)
        PaperlessTaskFactory(trigger_source=PaperlessTask.TriggerSource.API_UPLOAD)
        PaperlessTaskFactory(
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
        )  # excluded

        response = v9_client.get(ENDPOINT, {"type": "manual_task"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        assert all(t["type"] == "manual_task" for t in response.data)


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
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )

    @pytest.mark.parametrize(
        "task_type",
        [
            pytest.param(
                PaperlessTask.TaskType.CONSUME_FILE,
                id="consume_file-not-runnable",
            ),
            pytest.param(
                "not_a_real_type",
                id="invalid-task-type",
            ),
        ],
    )
    def test_returns_400_for_non_runnable_task_type(
        self,
        admin_client: APIClient,
        task_type: str,
    ) -> None:
        """run/ returns 400 for task types that cannot be manually triggered."""
        response = admin_client.post(
            ENDPOINT + "run/",
            {"task_type": task_type},
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
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )


@pytest.mark.django_db()
class TestDuplicateDocumentsPermissions:
    """duplicate_documents in the v9 response must respect document-level permissions."""

    @pytest.fixture()
    def user_v9_client(self, regular_user: User) -> APIClient:
        regular_user.user_permissions.add(
            Permission.objects.get(codename="view_paperlesstask"),
        )
        client = APIClient()
        client.force_authenticate(user=regular_user)
        client.credentials(HTTP_ACCEPT=ACCEPT_V9)
        return client

    def test_owner_sees_duplicate_document(
        self,
        user_v9_client: APIClient,
        regular_user: User,
    ) -> None:
        """A non-staff user sees a duplicate_of document they own."""
        doc = DocumentFactory(owner=regular_user, title="My Doc")
        PaperlessTaskFactory(
            owner=regular_user,
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": doc.pk},
        )

        response = user_v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        dupes = response.data[0]["duplicate_documents"]
        assert len(dupes) == 1
        assert dupes[0]["id"] == doc.pk

    def test_unowned_duplicate_document_is_visible(
        self,
        user_v9_client: APIClient,
        regular_user: User,
    ) -> None:
        """An unowned duplicate_of document is visible to any authenticated user."""
        doc = DocumentFactory(owner=None, title="Shared Doc")
        PaperlessTaskFactory(
            owner=regular_user,
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": doc.pk},
        )

        response = user_v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data[0]["duplicate_documents"]) == 1

    def test_other_users_duplicate_document_is_hidden(
        self,
        user_v9_client: APIClient,
        regular_user: User,
        admin_user: User,
    ) -> None:
        """A non-staff user cannot see a duplicate_of document owned by another user."""
        doc = DocumentFactory(owner=admin_user, title="Admin Doc")
        PaperlessTaskFactory(
            owner=regular_user,
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": doc.pk},
        )

        response = user_v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["duplicate_documents"] == []

    def test_explicit_permission_grants_visibility(
        self,
        user_v9_client: APIClient,
        regular_user: User,
        admin_user: User,
    ) -> None:
        """A user with explicit guardian view_document permission sees the duplicate_of document."""
        doc = DocumentFactory(owner=admin_user, title="Granted Doc")
        assign_perm("view_document", regular_user, doc)
        PaperlessTaskFactory(
            owner=regular_user,
            status=PaperlessTask.Status.SUCCESS,
            result_data={"duplicate_of": doc.pk},
        )

        response = user_v9_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        dupes = response.data[0]["duplicate_documents"]
        assert len(dupes) == 1
        assert dupes[0]["id"] == doc.pk
