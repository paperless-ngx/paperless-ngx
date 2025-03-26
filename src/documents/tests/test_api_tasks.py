import uuid

import celery
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import EdocTask
from documents.tests.utils import DirectoriesMixin


class TestTasks(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/tasks/"
    ENDPOINT_ACKNOWLEDGE = "/api/acknowledge_tasks/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_tasks(self):
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get tasks
        THEN:
            - Attempting and pending tasks are serialized and provided
        """

        task1 = EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        task2 = EdocTask.objects.create(
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

    def test_get_single_task_status(self):
        """
        GIVEN
            - Query parameter for a valid task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - Single task data is returned
        """

        id1 = str(uuid.uuid4())
        task1 = EdocTask.objects.create(
            task_id=id1,
            task_file_name="task_one.pdf",
        )

        _ = EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + f"?task_id={id1}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        returned_task1 = response.data[0]

        self.assertEqual(returned_task1["task_id"], task1.task_id)

    def test_get_single_task_status_not_valid(self):
        """
        GIVEN
            - Query parameter for a non-existent task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - No task data is returned
        """
        EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        _ = EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + "?task_id=bad-task-id")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_acknowledge_tasks(self):
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get mark task as acknowledged
        THEN:
            - Task is marked as acknowledged
        """
        task = EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(len(response.data), 1)

        response = self.client.post(
            self.ENDPOINT_ACKNOWLEDGE,
            {"tasks": [task.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(len(response.data), 0)

    def test_task_result_no_error(self):
        """
        GIVEN:
            - A celery task completed without error
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned data includes the task result
        """
        EdocTask.objects.create(
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

    def test_task_result_with_error(self):
        """
        GIVEN:
            - A celery task completed with an exception
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned result is the exception info
        """
        EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.FAILURE,
            result="test.pdf: Not consuming test.pdf: It is a duplicate.",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(
            returned_data["result"],
            "test.pdf: Not consuming test.pdf: It is a duplicate.",
        )

    def test_task_name_webui(self):
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the webui
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="test.pdf",
            task_name="documents.tasks.some_task",
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "test.pdf")

    def test_task_name_consume_folder(self):
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the consume folder
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        EdocTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="anothertest.pdf",
            task_name="documents.tasks.some_task",
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "anothertest.pdf")
