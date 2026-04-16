import uuid
from unittest import mock

import pytest
import pytest_mock

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import PaperlessTask
from documents.signals.handlers import task_revoked_handler
from documents.tests.factories import PaperlessTaskFactory


@pytest.fixture
def consume_input_doc():
    doc = mock.MagicMock(spec=ConsumableDocument)
    # original_file is a Path; configure the nested mock so .name works
    doc.original_file = mock.MagicMock()
    doc.original_file.name = "invoice.pdf"
    doc.original_path = None
    doc.mime_type = "application/pdf"
    doc.mailrule_id = None
    doc.source = DocumentSource.WebUI
    return doc


@pytest.fixture
def consume_overrides(django_user_model):
    user = django_user_model.objects.create_user(username="testuser")
    overrides = mock.MagicMock(spec=DocumentMetadataOverrides)
    overrides.owner_id = user.id
    return overrides


def send_publish(
    task_name: str,
    args: tuple,
    kwargs: dict,
    headers: dict | None = None,
) -> str:
    from documents.signals.handlers import before_task_publish_handler

    task_id = str(uuid.uuid4())
    hdrs = {"task": task_name, "id": task_id, **(headers or {})}
    before_task_publish_handler(sender=task_name, headers=hdrs, body=(args, kwargs, {}))
    return task_id


@pytest.mark.django_db
class TestBeforeTaskPublishHandler:
    def test_creates_task_for_consume_file(self, consume_input_doc, consume_overrides):
        task_id = send_publish(
            "documents.tasks.consume_file",
            (consume_input_doc, consume_overrides),
            {},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.task_type == PaperlessTask.TaskType.CONSUME_FILE
        assert task.status == PaperlessTask.Status.PENDING
        assert task.trigger_source == PaperlessTask.TriggerSource.WEB_UI
        assert task.input_data["filename"] == "invoice.pdf"
        assert task.owner_id == consume_overrides.owner_id

    def test_creates_task_for_train_classifier(self):
        task_id = send_publish("documents.tasks.train_classifier", (), {})
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.task_type == PaperlessTask.TaskType.TRAIN_CLASSIFIER
        assert task.trigger_source == PaperlessTask.TriggerSource.MANUAL

    def test_creates_task_for_sanity_check(self):
        task_id = send_publish("documents.tasks.sanity_check", (), {})
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.task_type == PaperlessTask.TaskType.SANITY_CHECK

    def test_creates_task_for_process_mail_accounts(self):
        task_id = send_publish(
            "paperless_mail.tasks.process_mail_accounts",
            (),
            {"account_ids": [1, 2]},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.task_type == PaperlessTask.TaskType.MAIL_FETCH
        assert task.input_data["account_ids"] == [1, 2]

    def test_mail_fetch_no_account_ids_stores_empty_input(self):
        """Beat-scheduled mail checks pass no account_ids; input_data should be {} not {"account_ids": None}."""
        task_id = send_publish("paperless_mail.tasks.process_mail_accounts", (), {})
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.input_data == {}

    def test_scheduled_header_sets_trigger_source(self):
        task_id = send_publish(
            "documents.tasks.train_classifier",
            (),
            {},
            headers={"trigger_source": "scheduled"},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == PaperlessTask.TriggerSource.SCHEDULED

    def test_system_header_sets_trigger_source(self):
        task_id = send_publish(
            "documents.tasks.llmindex_index",
            (),
            {"rebuild": True},
            headers={"trigger_source": "system"},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == PaperlessTask.TriggerSource.SYSTEM

    def test_ignores_untracked_task(self):
        send_publish("documents.tasks.some_untracked_task", (), {})
        assert PaperlessTask.objects.count() == 0

    def test_ignores_none_headers(self):
        from documents.signals.handlers import before_task_publish_handler

        before_task_publish_handler(sender=None, headers=None, body=None)
        assert PaperlessTask.objects.count() == 0

    def test_consume_folder_source_maps_correctly(
        self,
        consume_input_doc,
        consume_overrides,
    ):
        consume_input_doc.source = DocumentSource.ConsumeFolder
        task_id = send_publish(
            "documents.tasks.consume_file",
            (consume_input_doc, consume_overrides),
            {},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == PaperlessTask.TriggerSource.FOLDER_CONSUME

    def test_email_source_maps_correctly(self, consume_input_doc, consume_overrides):
        consume_input_doc.source = DocumentSource.MailFetch
        task_id = send_publish(
            "documents.tasks.consume_file",
            (consume_input_doc, consume_overrides),
            {},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == PaperlessTask.TriggerSource.EMAIL_CONSUME


@pytest.mark.django_db
class TestTaskPrerunHandler:
    def test_marks_task_started(self):
        task = PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        from documents.signals.handlers import task_prerun_handler

        task_prerun_handler(task_id=task.task_id)
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.STARTED
        assert task.date_started is not None

    def test_ignores_unknown_task_id(self):
        from documents.signals.handlers import task_prerun_handler

        task_prerun_handler(task_id="nonexistent-id")  # must not raise

    def test_ignores_none_task_id(self):
        from documents.signals.handlers import task_prerun_handler

        task_prerun_handler(task_id=None)  # must not raise


@pytest.mark.django_db
class TestTaskPostrunHandler:
    def _started_task(self) -> PaperlessTask:
        from django.utils import timezone

        return PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )

    def test_records_success_with_dict_result(self):
        task = self._started_task()
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(
            task_id=task.task_id,
            retval={"document_id": 42},
            state="SUCCESS",
        )
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.SUCCESS
        assert task.result_data == {"document_id": 42}
        assert task.date_done is not None
        assert task.duration_seconds is not None
        assert task.wait_time_seconds is not None

    def test_skips_failure_state(self):
        """postrun skips FAILURE; task_failure_handler owns that path."""
        task = self._started_task()
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(task_id=task.task_id, retval="some error", state="FAILURE")
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.STARTED

    def test_parses_legacy_new_document_string(self):
        task = self._started_task()
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(
            task_id=task.task_id,
            retval="New document id 42 created",
            state="SUCCESS",
        )
        task.refresh_from_db()
        assert task.result_data["document_id"] == 42
        assert task.result_message == "New document id 42 created"

    def test_parses_duplicate_string(self):
        """Duplicate detection returns a string with SUCCESS state (StopConsumeTaskError is caught and returned, not raised)."""
        task = self._started_task()
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(
            task_id=task.task_id,
            retval="It is a duplicate of some document (#99).",
            state="SUCCESS",
        )
        task.refresh_from_db()
        assert task.result_data["duplicate_of"] == 99
        assert task.result_data["duplicate_in_trash"] is False

    def test_ignores_unknown_task_id(self):
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(
            task_id="nonexistent",
            retval=None,
            state="SUCCESS",
        )  # must not raise

    def test_records_revoked_state(self):
        task = self._started_task()
        from documents.signals.handlers import task_postrun_handler

        task_postrun_handler(task_id=task.task_id, retval=None, state="REVOKED")
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.REVOKED


@pytest.mark.django_db
class TestTaskFailureHandler:
    def test_records_failure_with_exception(self):
        from django.utils import timezone

        task = PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )
        from documents.signals.handlers import task_failure_handler

        task_failure_handler(
            task_id=task.task_id,
            exception=ValueError("PDF parse failed"),
            traceback=None,
        )
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.FAILURE
        assert task.result_data["error_type"] == "ValueError"
        assert task.result_data["error_message"] == "PDF parse failed"
        assert task.date_done is not None

    def test_records_traceback_when_provided(self):
        import sys

        from django.utils import timezone

        task = PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )
        try:
            raise ValueError("test error")
        except ValueError:
            tb = sys.exc_info()[2]

        from documents.signals.handlers import task_failure_handler

        task_failure_handler(
            task_id=task.task_id,
            exception=ValueError("test error"),
            traceback=tb,
        )
        task.refresh_from_db()
        assert "traceback" in task.result_data
        assert len(task.result_data["traceback"]) <= 5000

    def test_computes_duration_and_wait_time(self):
        from django.utils import timezone

        now = timezone.now()
        task = PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.STARTED,
            date_created=now - timezone.timedelta(seconds=10),
            date_started=now - timezone.timedelta(seconds=5),
        )
        from documents.signals.handlers import task_failure_handler

        task_failure_handler(
            task_id=task.task_id,
            exception=ValueError("boom"),
            traceback=None,
        )
        task.refresh_from_db()
        assert task.duration_seconds == pytest.approx(5.0, abs=1.0)
        assert task.wait_time_seconds == pytest.approx(5.0, abs=1.0)

    def test_ignores_none_task_id(self):
        from documents.signals.handlers import task_failure_handler

        task_failure_handler(task_id=None, exception=ValueError("x"), traceback=None)


@pytest.mark.django_db
class TestTaskRevokedHandler:
    def test_marks_task_revoked(self, mocker: pytest_mock.MockerFixture):
        """task_revoked_handler moves a queued task to REVOKED and stamps date_done."""
        task = PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)
        request = mocker.MagicMock()
        request.id = task.task_id

        task_revoked_handler(request=request)
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.REVOKED
        assert task.date_done is not None

    def test_ignores_none_request(self):
        """task_revoked_handler must not raise when request is None."""

        task_revoked_handler(request=None)  # must not raise

    def test_ignores_unknown_task_id(self, mocker: pytest_mock.MockerFixture):
        """task_revoked_handler must not raise for a task_id not in the database."""
        request = mocker.MagicMock()
        request.id = "nonexistent-id"

        task_revoked_handler(request=request)  # must not raise
