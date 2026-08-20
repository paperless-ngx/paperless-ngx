"""
Tests that mail rule consumption populates the `mail_context` on
DocumentMetadataOverrides so workflow Jinja templates can reference the
originating mail's subject/sender/recipients/date.
"""

from unittest import mock

import pytest

from documents.tests.utils import remove_dirs
from documents.tests.utils import setup_directories
from paperless_mail.models import MailRule
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.test_mail import MessageBuilder
from paperless_mail.tests.test_mail import _AttachmentDef
from paperless_mail.tests.test_mail import fake_magic_from_buffer


@pytest.fixture()
def directories(settings):
    dirs = setup_directories()
    yield dirs
    remove_dirs(dirs)


@pytest.fixture()
def queue_consumption_tasks_mock():
    with mock.patch("paperless_mail.mail.queue_consumption_tasks") as m:
        yield m


@pytest.fixture()
def mail_account(db):
    return MailAccountFactory()


@pytest.fixture()
def attachment_rule(mail_account):
    rule = MailRule(
        name="attachment rule with templating",
        account=mail_account,
        assign_title_from=MailRule.TitleSource.FROM_SUBJECT,
        consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
    )
    rule.save()
    return rule


@pytest.fixture()
def eml_rule(mail_account):
    rule = MailRule(
        name="eml rule with templating",
        account=mail_account,
        assign_title_from=MailRule.TitleSource.FROM_SUBJECT,
        consumption_scope=MailRule.ConsumptionScope.EML_ONLY,
        attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
    )
    rule.save()
    return rule


@pytest.fixture()
def message_builder():
    return MessageBuilder()


@pytest.mark.django_db
@mock.patch("paperless_mail.mail.magic.from_buffer", fake_magic_from_buffer)
class TestMailContextOverrides:
    """
    GIVEN a mail rule ingests a message
    WHEN attachment or EML overrides are built
    THEN the resulting DocumentMetadataOverrides.mail_context exposes
         subject, sender, recipients and date pulled from the message.
    """

    def test_attachment_overrides_carry_mail_context(
        self,
        directories,
        queue_consumption_tasks_mock,
        attachment_rule,
        mail_account_handler,
        message_builder,
    ):
        message = message_builder.create_message(
            subject="Invoice 42",
            from_="sender@example.com",
            to=["me@example.com", "other@example.com"],
            attachments=[
                _AttachmentDef(filename="invoice.pdf", content=b"%PDF-1.4 test"),
            ],
        )

        result = mail_account_handler._handle_message(message, attachment_rule)
        assert result == 1

        queue_consumption_tasks_mock.assert_called_once()
        consume_tasks = queue_consumption_tasks_mock.call_args.kwargs["consume_tasks"]
        overrides = consume_tasks[0].kwargs["overrides"]

        assert overrides.mail_context is not None
        assert overrides.mail_context["subject"] == "Invoice 42"
        assert "sender@example.com" in overrides.mail_context["sender"]
        assert any(
            "me@example.com" in addr for addr in overrides.mail_context["recipients"]
        )
        # date key must exist even if None (unparsed test messages have no Date)
        assert "date" in overrides.mail_context

    def test_eml_overrides_carry_mail_context(
        self,
        directories,
        queue_consumption_tasks_mock,
        eml_rule,
        mail_account_handler,
        message_builder,
    ):
        message = message_builder.create_message(
            subject="Meeting notes",
            from_="boss@example.com",
            to=["team@example.com"],
            attachments=0,
        )

        mail_account_handler._handle_message(message, eml_rule)

        queue_consumption_tasks_mock.assert_called_once()
        consume_tasks = queue_consumption_tasks_mock.call_args.kwargs["consume_tasks"]
        overrides = consume_tasks[0].kwargs["overrides"]

        assert overrides.mail_context is not None
        assert overrides.mail_context["subject"] == "Meeting notes"
        assert "boss@example.com" in overrides.mail_context["sender"]
        assert any(
            "team@example.com" in addr for addr in overrides.mail_context["recipients"]
        )
