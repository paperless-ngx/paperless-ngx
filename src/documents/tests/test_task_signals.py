import datetime
import sys
import uuid
from pathlib import Path
from unittest import mock

import pytest
import pytest_mock
from django.utils import timezone

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import PaperlessTask
from documents.signals.handlers import before_task_publish_handler
from documents.signals.handlers import task_failure_handler
from documents.signals.handlers import task_postrun_handler
from documents.signals.handlers import task_prerun_handler
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

    task_id = str(uuid.uuid4())
    hdrs = {"task": task_name, "id": task_id, **(headers or {})}
    before_task_publish_handler(sender=task_name, headers=hdrs, body=(args, kwargs, {}))
    return task_id


@pytest.mark.django_db
class TestBeforeTaskPublishHandler:
    def test_creates_task_for_consume_file(self, consume_input_doc, consume_overrides):
        task_id = send_publish(
            "documents.tasks.consume_file",
            (),
            {"input_doc": consume_input_doc, "overrides": consume_overrides},
            headers={"trigger_source": PaperlessTask.TriggerSource.WEB_UI},
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

    def test_overrides_date_serialized_as_iso_string(self, consume_input_doc):
        """A datetime.date in overrides is stored as an ISO string so input_data is JSON-safe."""
        overrides = DocumentMetadataOverrides(created=datetime.date(2024, 1, 15))

        task_id = send_publish(
            "documents.tasks.consume_file",
            (),
            {"input_doc": consume_input_doc, "overrides": overrides},
        )

        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.input_data["overrides"]["created"] == "2024-01-15"

    def test_overrides_path_serialized_as_string(self, consume_input_doc):
        """A Path value in overrides is stored as a plain string so input_data is JSON-safe."""
        overrides = DocumentMetadataOverrides()
        overrides.filename = Path("/uploads/invoice.pdf")  # type: ignore[assignment]

        task_id = send_publish(
            "documents.tasks.consume_file",
            (),
            {"input_doc": consume_input_doc, "overrides": overrides},
        )

        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.input_data["overrides"]["filename"] == "/uploads/invoice.pdf"

    @pytest.mark.parametrize(
        ("header_value", "expected_trigger_source"),
        [
            pytest.param(
                PaperlessTask.TriggerSource.SCHEDULED,
                PaperlessTask.TriggerSource.SCHEDULED,
                id="scheduled",
            ),
            pytest.param(
                PaperlessTask.TriggerSource.SYSTEM,
                PaperlessTask.TriggerSource.SYSTEM,
                id="system",
            ),
            pytest.param(
                "bogus_value",
                PaperlessTask.TriggerSource.MANUAL,
                id="invalid-falls-back-to-manual",
            ),
        ],
    )
    def test_trigger_source_header_resolution(
        self,
        header_value: str,
        expected_trigger_source: PaperlessTask.TriggerSource,
    ) -> None:
        """trigger_source header maps to the expected TriggerSource; invalid values fall back to MANUAL."""
        task_id = send_publish(
            "documents.tasks.train_classifier",
            (),
            {},
            headers={"trigger_source": header_value},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == expected_trigger_source

    def test_ignores_untracked_task(self):
        send_publish("documents.tasks.some_untracked_task", (), {})
        assert PaperlessTask.objects.count() == 0

    def test_ignores_none_headers(self):

        before_task_publish_handler(sender=None, headers=None, body=None)
        assert PaperlessTask.objects.count() == 0

    def test_consume_file_without_trigger_source_header_defaults_to_manual(
        self,
        consume_input_doc,
        consume_overrides,
    ) -> None:
        """Without a trigger_source header the handler defaults to MANUAL."""
        task_id = send_publish(
            "documents.tasks.consume_file",
            (),
            {"input_doc": consume_input_doc, "overrides": consume_overrides},
        )
        task = PaperlessTask.objects.get(task_id=task_id)
        assert task.trigger_source == PaperlessTask.TriggerSource.MANUAL


@pytest.mark.django_db
class TestTaskPrerunHandler:
    def test_marks_task_started(self):
        task = PaperlessTaskFactory(status=PaperlessTask.Status.PENDING)

        task_prerun_handler(task_id=task.task_id)
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.STARTED
        assert task.date_started is not None

    @pytest.mark.parametrize(
        "task_id",
        [
            pytest.param("nonexistent-id", id="unknown"),
            pytest.param(None, id="none"),
        ],
    )
    def test_ignores_invalid_task_id(self, task_id: str | None) -> None:

        task_prerun_handler(task_id=task_id)  # must not raise


@pytest.mark.django_db
class TestTaskPostrunHandler:
    def _started_task(self) -> PaperlessTask:

        return PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )

    def test_records_success_with_dict_result(self):
        task = self._started_task()

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

        task_postrun_handler(task_id=task.task_id, retval="some error", state="FAILURE")
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.STARTED

    def test_records_success_with_consume_result(self):
        """ConsumeFileSuccessResult dict is stored directly as result_data."""
        from documents.data_models import ConsumeFileSuccessResult

        task = self._started_task()
        task_postrun_handler(
            task_id=task.task_id,
            retval=ConsumeFileSuccessResult(document_id=42),
            state="SUCCESS",
        )
        task.refresh_from_db()
        assert task.result_data == {"document_id": 42}

    def test_records_stopped_with_reason(self):
        """ConsumeFileStoppedResult dict is stored directly as result_data."""
        from documents.data_models import ConsumeFileStoppedResult

        task = self._started_task()
        task_postrun_handler(
            task_id=task.task_id,
            retval=ConsumeFileStoppedResult(reason="Barcode splitting complete!"),
            state="SUCCESS",
        )
        task.refresh_from_db()
        assert task.result_data == {"reason": "Barcode splitting complete!"}

    def test_none_retval_stores_no_result_data(self):
        """None return value (non-consume tasks) leaves result_data untouched."""
        task = self._started_task()
        task_postrun_handler(task_id=task.task_id, retval=None, state="SUCCESS")
        task.refresh_from_db()
        assert task.result_data is None

    def test_ignores_unknown_task_id(self):

        task_postrun_handler(
            task_id="nonexistent",
            retval=None,
            state="SUCCESS",
        )  # must not raise

    def test_records_revoked_state(self):
        task = self._started_task()

        task_postrun_handler(task_id=task.task_id, retval=None, state="REVOKED")
        task.refresh_from_db()
        assert task.status == PaperlessTask.Status.REVOKED


@pytest.mark.django_db
class TestTaskFailureHandler:
    def test_records_failure_with_exception(self):

        task = PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )

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

        now = timezone.now()
        task = PaperlessTaskFactory(
            task_type=PaperlessTask.TaskType.CONSUME_FILE,
            status=PaperlessTask.Status.STARTED,
            date_created=now - timezone.timedelta(seconds=10),
            date_started=now - timezone.timedelta(seconds=5),
        )

        task_failure_handler(
            task_id=task.task_id,
            exception=ValueError("boom"),
            traceback=None,
        )
        task.refresh_from_db()
        assert task.duration_seconds == pytest.approx(5.0, abs=1.0)
        assert task.wait_time_seconds == pytest.approx(5.0, abs=1.0)

    def test_ignores_none_task_id(self):

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
