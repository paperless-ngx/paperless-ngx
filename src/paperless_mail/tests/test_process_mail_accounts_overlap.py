from typing import Final

import pytest
import pytest_mock
from django.core.cache import cache

from paperless_mail import tasks
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.factories import MailRuleFactory

NO_DOCUMENTS_ADDED: Final = "No new documents were added."
SKIPPED: Final = "Skipped: mail account processing already in progress."


@pytest.fixture(autouse=True)
def _clear_mail_fetch_lock():
    cache.delete(tasks.MAIL_FETCH_LOCK_KEY)
    yield
    cache.delete(tasks.MAIL_FETCH_LOCK_KEY)


@pytest.mark.django_db
@pytest.mark.usefixtures("account_with_rule")
class TestProcessMailAccountsOverlap:
    @pytest.fixture
    def account_with_rule(self) -> None:
        """An enabled mail account with a single enabled rule."""
        account = MailAccountFactory.create()
        MailRuleFactory.create(account=account, enabled=True)

    def test_skips_while_lock_is_held(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - The mail fetch lock is already held by another run
        WHEN:
            - Mail accounts are processed
        THEN:
            - Processing is skipped and no account is handled
        """
        cache.add(tasks.MAIL_FETCH_LOCK_KEY, "other-task-id", timeout=60)

        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts()

        assert mocked_handle.call_count == 0
        assert result == SKIPPED

    def test_runs_when_lock_is_free(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - No mail fetch run currently holds the lock
        WHEN:
            - Mail accounts are processed
        THEN:
            - The account is handled and the lock is released afterwards
        """
        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts()

        mocked_handle.assert_called_once()
        assert result == NO_DOCUMENTS_ADDED
        assert cache.get(tasks.MAIL_FETCH_LOCK_KEY) is None

    def test_releases_lock_even_if_handling_raises(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - Handling the account raises an unexpected exception
        WHEN:
            - Mail accounts are processed
        THEN:
            - The lock is still released so the next run is not blocked forever
        """
        mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            side_effect=RuntimeError("boom"),
        )

        with pytest.raises(RuntimeError):
            tasks.process_mail_accounts()

        assert cache.get(tasks.MAIL_FETCH_LOCK_KEY) is None

    def test_recovers_after_lock_ttl_expires(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An enabled mail account with a rule
            - A lock left behind by a run that never released it (e.g. the
              worker was killed mid-run) but whose TTL has since expired
        WHEN:
            - Mail accounts are processed
        THEN:
            - The account is handled instead of being permanently blocked
        """
        cache.add(tasks.MAIL_FETCH_LOCK_KEY, "dead-task-id", timeout=1)
        cache.delete(tasks.MAIL_FETCH_LOCK_KEY)  # simulate TTL expiry

        mocked_handle = mocker.patch.object(
            tasks.MailAccountHandler,
            "handle_mail_account",
            return_value=0,
        )

        result = tasks.process_mail_accounts()

        mocked_handle.assert_called_once()
        assert result == NO_DOCUMENTS_ADDED
