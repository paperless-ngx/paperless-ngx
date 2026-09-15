from typing import Final

import pytest
import pytest_mock

from documents.models import PaperlessTask
from documents.tests.factories import PaperlessTaskFactory
from paperless_mail import tasks
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.factories import MailRuleFactory

NO_DOCUMENTS_ADDED: Final = "No new documents were added."
SKIPPED: Final = "Skipped: mail account processing already in progress."


@pytest.mark.django_db
@pytest.mark.usefixtures("account_with_rule")
class TestProcessMailAccountsOverlap:
    @pytest.fixture
    def account_with_rule(self) -> None:
        """An enabled mail account with a single enabled rule."""
        account = MailAccountFactory.create()
        MailRuleFactory.create(account=account, enabled=True)

    @pytest.mark.parametrize(
        ("status", "expected_result", "expected_call_count"),
        [
            pytest.param(
                PaperlessTask.Status.PENDING,
                SKIPPED,
                0,
                id="pending-task-blocks",
            ),
            pytest.param(
                PaperlessTask.Status.STARTED,
                SKIPPED,
                0,
                id="started-task-blocks",
            ),
            pytest.param(
                PaperlessTask.Status.SUCCESS,
                NO_DOCUMENTS_ADDED,
                1,
                id="finished-task-does-not-block",
            ),
        ],
    )
    def test_skips_only_while_another_mail_fetch_task_runs(
        self,
        mocker: pytest_mock.MockerFixture,
        status: PaperlessTask.Status,
        expected_result: str,
        expected_call_count: int,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - Another mail fetch task row in the given status
        WHEN:
            - Mail accounts are processed
        THEN:
            - Processing is skipped only if that other task is pending or running
        """
        PaperlessTaskFactory.create(
            task_type=PaperlessTask.TaskType.MAIL_FETCH,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=status,
        )

        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts()

        assert mocked_handle.call_count == expected_call_count
        assert result == expected_result

    def test_runs_when_no_other_mail_fetch_task_exists(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - No other mail fetch task rows
        WHEN:
            - Mail accounts are processed
        THEN:
            - The account is handled
        """
        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts()

        mocked_handle.assert_called_once()
        assert result == NO_DOCUMENTS_ADDED

    def test_does_not_skip_due_to_its_own_task_row(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - A running mail fetch task row belonging to this very task
        WHEN:
            - Mail accounts are processed under that task id
        THEN:
            - The task does not skip itself and handles the account
        """
        PaperlessTaskFactory.create(
            task_id="self-task-id",
            task_type=PaperlessTask.TaskType.MAIL_FETCH,
            trigger_source=PaperlessTask.TriggerSource.SCHEDULED,
            status=PaperlessTask.Status.STARTED,
        )

        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts.apply(task_id="self-task-id").result

        mocked_handle.assert_called_once()
        assert result == NO_DOCUMENTS_ADDED
