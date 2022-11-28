import celery
from django.test import TestCase
from documents.models import PaperlessTask
from documents.signals.handlers import before_task_publish_handler
from documents.signals.handlers import task_postrun_handler
from documents.signals.handlers import task_prerun_handler
from documents.tests.utils import DirectoriesMixin


class TestTaskSignalHandler(DirectoriesMixin, TestCase):

    HEADERS_CONSUME = {
        "lang": "py",
        "task": "documents.tasks.consume_file",
        "id": "52d31e24-9dcc-4c32-9e16-76007e9add5e",
        "shadow": None,
        "eta": None,
        "expires": None,
        "group": None,
        "group_index": None,
        "retries": 0,
        "timelimit": [None, None],
        "root_id": "52d31e24-9dcc-4c32-9e16-76007e9add5e",
        "parent_id": None,
        "argsrepr": "('/consume/hello-999.pdf',)",
        "kwargsrepr": "{'override_tag_ids': None}",
        "origin": "gen260@paperless-ngx-dev-webserver",
        "ignore_result": False,
    }

    HEADERS_WEB_UI = {
        "lang": "py",
        "task": "documents.tasks.consume_file",
        "id": "6e88a41c-e5f8-4631-9972-68c314512498",
        "shadow": None,
        "eta": None,
        "expires": None,
        "group": None,
        "group_index": None,
        "retries": 0,
        "timelimit": [None, None],
        "root_id": "6e88a41c-e5f8-4631-9972-68c314512498",
        "parent_id": None,
        "argsrepr": "('/tmp/paperless/paperless-upload-st9lmbvx',)",
        "kwargsrepr": "{'override_filename': 'statement.pdf', 'override_title': None, 'override_correspondent_id': None, 'override_document_type_id': None, 'override_tag_ids': None, 'task_id': 'f5622ca9-3707-4ed0-b418-9680b912572f', 'override_created': None}",
        "origin": "gen342@paperless-ngx-dev-webserver",
        "ignore_result": False,
    }

    def util_call_before_task_publish_handler(self, headers_to_use):
        self.assertEqual(PaperlessTask.objects.all().count(), 0)

        before_task_publish_handler(headers=headers_to_use)

        self.assertEqual(PaperlessTask.objects.all().count(), 1)

    def test_before_task_publish_handler_consume(self):
        """
        GIVEN:
            - A celery task completed with an exception
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned result is the exception info
        """
        self.util_call_before_task_publish_handler(headers_to_use=self.HEADERS_CONSUME)

        task = PaperlessTask.objects.get()
        self.assertIsNotNone(task)
        self.assertEqual(self.HEADERS_CONSUME["id"], task.task_id)
        self.assertListEqual(["/consume/hello-999.pdf"], task.task_args)
        self.assertDictEqual({"override_tag_ids": None}, task.task_kwargs)
        self.assertEqual("hello-999.pdf", task.task_file_name)
        self.assertEqual("documents.tasks.consume_file", task.task_name)
        self.assertEqual(celery.states.PENDING, task.status)

    def test_before_task_publish_handler_webui(self):

        self.util_call_before_task_publish_handler(headers_to_use=self.HEADERS_WEB_UI)

        task = PaperlessTask.objects.get()

        self.assertIsNotNone(task)

        self.assertEqual(self.HEADERS_WEB_UI["id"], task.task_id)
        self.assertListEqual(
            ["/tmp/paperless/paperless-upload-st9lmbvx"],
            task.task_args,
        )
        self.assertDictEqual(
            {
                "override_filename": "statement.pdf",
                "override_title": None,
                "override_correspondent_id": None,
                "override_document_type_id": None,
                "override_tag_ids": None,
                "task_id": "f5622ca9-3707-4ed0-b418-9680b912572f",
                "override_created": None,
            },
            task.task_kwargs,
        )
        self.assertEqual("statement.pdf", task.task_file_name)
        self.assertEqual("documents.tasks.consume_file", task.task_name)
        self.assertEqual(celery.states.PENDING, task.status)

    def test_task_prerun_handler(self):
        self.util_call_before_task_publish_handler(headers_to_use=self.HEADERS_CONSUME)

        task_prerun_handler(task_id=self.HEADERS_CONSUME["id"])

        task = PaperlessTask.objects.get()

        self.assertEqual(celery.states.STARTED, task.status)

    def test_task_postrun_handler(self):
        self.util_call_before_task_publish_handler(headers_to_use=self.HEADERS_CONSUME)

        task_postrun_handler(
            task_id=self.HEADERS_CONSUME["id"],
            retval="Success. New document id 1 created",
            state=celery.states.SUCCESS,
        )

        task = PaperlessTask.objects.get()

        self.assertEqual(celery.states.SUCCESS, task.status)
