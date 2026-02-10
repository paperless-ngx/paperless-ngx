import uuid
from unittest import mock

import celery
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.models import PaperlessTask
from documents.tests.utils import DirectoriesMixin
from documents.views import TasksViewSet


class TestTasks(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/tasks/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_tasks(self) -> None:
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get tasks
        THEN:
            - Attempting and pending tasks are serialized and provided
        """

        task1 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        task2 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        returned_task1 = response.data[1]
        returned_task2 = response.data[0]

        self.assertEqual(returned_task1["task_id"], task1.task_id)
        self.assertEqual(returned_task1["status"], celery.states.PENDING)
        self.assertEqual(returned_task1["task_file_name"], task1.task_file_name)

        self.assertEqual(returned_task2["task_id"], task2.task_id)
        self.assertEqual(returned_task2["status"], celery.states.PENDING)
        self.assertEqual(returned_task2["task_file_name"], task2.task_file_name)

    def test_get_single_task_status(self) -> None:
        """
        GIVEN
            - Query parameter for a valid task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - Single task data is returned
        """

        id1 = str(uuid.uuid4())
        task1 = PaperlessTask.objects.create(
            task_id=id1,
            task_file_name="task_one.pdf",
        )

        _ = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + f"?task_id={id1}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        returned_task1 = response.data[0]

        self.assertEqual(returned_task1["task_id"], task1.task_id)

    def test_get_single_task_status_not_valid(self) -> None:
        """
        GIVEN
            - Query parameter for a non-existent task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - No task data is returned
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        _ = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + "?task_id=bad-task-id")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_acknowledge_tasks(self) -> None:
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get mark task as acknowledged
        THEN:
            - Task is marked as acknowledged
        """
        task = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(len(response.data), 1)

        response = self.client.post(
            self.ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(self.ENDPOINT + "?acknowledged=false")
        self.assertEqual(len(response.data), 0)

    def test_acknowledge_tasks_requires_change_permission(self) -> None:
        """
        GIVEN:
            - A regular user initially without change permissions
            - A regular user with change permissions
        WHEN:
            - API call is made to acknowledge tasks
        THEN:
            - The first user is forbidden from acknowledging tasks
            - The second user is allowed to acknowledge tasks
        """
        regular_user = User.objects.create_user(username="test")
        self.client.force_authenticate(user=regular_user)

        task = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        response = self.client.post(
            self.ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        regular_user2 = User.objects.create_user(username="test2")
        regular_user2.user_permissions.add(
            Permission.objects.get(codename="change_paperlesstask"),
        )
        regular_user2.save()
        self.client.force_authenticate(user=regular_user2)

        response = self.client.post(
            self.ENDPOINT + "acknowledge/",
            {"tasks": [task.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_tasks_owner_aware(self) -> None:
        """
        GIVEN:
            - Existing PaperlessTasks with owner and with no owner
        WHEN:
            - API call is made to get tasks
        THEN:
            - Only tasks with no owner or request user are returned
        """

        regular_user = User.objects.create_user(username="test")
        regular_user.user_permissions.add(*Permission.objects.all())
        self.client.logout()
        self.client.force_authenticate(user=regular_user)

        task1 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            owner=self.user,
        )

        task2 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        task3 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_three.pdf",
            owner=regular_user,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["task_id"], task3.task_id)
        self.assertEqual(response.data[1]["task_id"], task2.task_id)

        acknowledge_response = self.client.post(
            self.ENDPOINT + "acknowledge/",
            {"tasks": [task1.id, task2.id, task3.id]},
        )
        self.assertEqual(acknowledge_response.status_code, status.HTTP_200_OK)
        self.assertEqual(acknowledge_response.data, {"result": 2})

    def test_task_result_no_error(self) -> None:
        """
        GIVEN:
            - A celery task completed without error
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned data includes the task result
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.SUCCESS,
            result="Success. New document id 1 created",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["result"], "Success. New document id 1 created")
        self.assertEqual(returned_data["related_document"], "1")

    def test_task_result_with_error(self) -> None:
        """
        GIVEN:
            - A celery task completed with an exception
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned result is the exception info
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.FAILURE,
            result="test.pdf: Unexpected error during ingestion.",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(
            returned_data["result"],
            "test.pdf: Unexpected error during ingestion.",
        )

    def test_task_name_webui(self) -> None:
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the webui
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="test.pdf",
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "test.pdf")

    def test_task_name_consume_folder(self) -> None:
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the consume folder
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="anothertest.pdf",
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "anothertest.pdf")

    def test_task_result_duplicate_warning_includes_count(self) -> None:
        """
        GIVEN:
            - A celery task succeeds, but a duplicate exists
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned data includes duplicate warning metadata
        """
        checksum = "duplicate-checksum"
        Document.objects.create(
            title="Existing",
            content="",
            mime_type="application/pdf",
            checksum=checksum,
        )
        created_doc = Document.objects.create(
            title="Created",
            content="",
            mime_type="application/pdf",
            checksum=checksum,
            archive_checksum="another-checksum",
        )
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.SUCCESS,
            result=f"Success. New document id {created_doc.pk} created",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["related_document"], str(created_doc.pk))

    def test_run_train_classifier_task(self) -> None:
        """
        GIVEN:
            - A superuser
        WHEN:
            - API call is made to run the train classifier task
        THEN:
            - The task is run
        """
        mock_train_classifier = mock.Mock(return_value="Task started")
        TasksViewSet.TASK_AND_ARGS_BY_NAME = {
            PaperlessTask.TaskName.TRAIN_CLASSIFIER: (
                mock_train_classifier,
                {"scheduled": False},
            ),
        }
        response = self.client.post(
            self.ENDPOINT + "run/",
            {"task_name": PaperlessTask.TaskName.TRAIN_CLASSIFIER},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"result": "Task started"})
        mock_train_classifier.assert_called_once_with(scheduled=False)

        # mock error
        mock_train_classifier.reset_mock()
        mock_train_classifier.side_effect = Exception("Error")
        response = self.client.post(
            self.ENDPOINT + "run/",
            {"task_name": PaperlessTask.TaskName.TRAIN_CLASSIFIER},
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_train_classifier.assert_called_once_with(scheduled=False)

    @mock.patch("documents.tasks.sanity_check")
    def test_run_task_requires_superuser(self, mock_check_sanity) -> None:
        """
        GIVEN:
            - A regular user
        WHEN:
            - API call is made to run a task
        THEN:
            - The task is not run
        """
        regular_user = User.objects.create_user(username="test")
        regular_user.user_permissions.add(*Permission.objects.all())
        self.client.logout()
        self.client.force_authenticate(user=regular_user)

        response = self.client.post(
            self.ENDPOINT + "run/",
            {"task_name": PaperlessTask.TaskName.CHECK_SANITY},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_check_sanity.assert_not_called()
