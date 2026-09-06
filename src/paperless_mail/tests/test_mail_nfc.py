"""
Tests that mail attachment filenames and EML subject filenames are
normalized to NFC Unicode before being stored as document overrides.

Filenames from MIME headers can arrive in NFD form (e.g. from macOS Mail),
and must be normalized to NFC so filenames are consistent regardless of the
sending client.
"""

import unicodedata
from pathlib import Path
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
        name="attachment rule",
        account=mail_account,
        assign_title_from=MailRule.TitleSource.FROM_FILENAME,
        consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
    )
    rule.save()
    return rule


@pytest.fixture()
def eml_rule(mail_account):
    rule = MailRule(
        name="eml rule",
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
class TestMailNFCNormalization:
    """Attachment filenames and EML subject filenames must be NFC-normalized."""

    def test_attachment_nfd_filename_normalized_to_nfc(
        self,
        directories,
        queue_consumption_tasks_mock,
        attachment_rule,
        mail_account_handler,
        message_builder,
    ):
        """Attachment filename arriving as NFD must be stored as NFC in both
        the overrides and the temp file written to disk.
        """
        nfd_filename = unicodedata.normalize("NFD", "Rechnung März.pdf")
        nfc_filename = unicodedata.normalize("NFC", "Rechnung März.pdf")

        # Confirm the fixture is actually NFD (not already NFC)
        assert unicodedata.is_normalized("NFD", nfd_filename)
        assert not unicodedata.is_normalized("NFC", nfd_filename)

        message = message_builder.create_message(
            subject="Test invoice",
            from_="sender@example.com",
            attachments=[
                _AttachmentDef(filename=nfd_filename, content=b"%PDF-1.4 test"),
            ],
        )

        result = mail_account_handler._handle_message(message, attachment_rule)

        assert result == 1
        queue_consumption_tasks_mock.assert_called_once()

        call_kwargs = queue_consumption_tasks_mock.call_args.kwargs
        consume_tasks = call_kwargs["consume_tasks"]
        assert len(consume_tasks) == 1

        overrides = consume_tasks[0].kwargs["overrides"]
        assert overrides.filename == nfc_filename
        assert unicodedata.is_normalized("NFC", overrides.filename)
        assert unicodedata.is_normalized("NFC", overrides.title)

        input_doc = consume_tasks[0].kwargs["input_doc"]
        original_file = Path(input_doc.original_file)
        assert original_file.exists()
        assert original_file.name == nfc_filename

    def test_eml_subject_filename_nfc(
        self,
        directories,
        queue_consumption_tasks_mock,
        eml_rule,
        mail_account_handler,
        message_builder,
    ):
        """EML filename derived from subject arriving as NFD must be stored as NFC."""
        nfd_subject = unicodedata.normalize("NFD", "Rechnung März 2024")
        nfc_expected_filename = unicodedata.normalize("NFC", "Rechnung März 2024.eml")

        # Confirm the fixture is actually NFD
        assert unicodedata.is_normalized("NFD", nfd_subject)

        message = message_builder.create_message(
            subject=nfd_subject,
            from_="sender@example.com",
            attachments=0,
        )

        mail_account_handler._handle_message(message, eml_rule)

        queue_consumption_tasks_mock.assert_called_once()

        call_kwargs = queue_consumption_tasks_mock.call_args.kwargs
        consume_tasks = call_kwargs["consume_tasks"]
        assert len(consume_tasks) == 1

        overrides = consume_tasks[0].kwargs["overrides"]
        assert overrides.filename == nfc_expected_filename
        assert unicodedata.is_normalized("NFC", overrides.filename)

    def test_already_nfc_attachment_filename_unchanged(
        self,
        directories,
        queue_consumption_tasks_mock,
        attachment_rule,
        mail_account_handler,
        message_builder,
    ):
        """An attachment filename already in NFC must pass through unchanged."""
        nfc_filename = "Invoice_2024.pdf"
        assert unicodedata.is_normalized("NFC", nfc_filename)

        message = message_builder.create_message(
            subject="Invoice",
            from_="sender@example.com",
            attachments=[
                _AttachmentDef(filename=nfc_filename, content=b"%PDF-1.4 test"),
            ],
        )

        mail_account_handler._handle_message(message, attachment_rule)

        call_kwargs = queue_consumption_tasks_mock.call_args.kwargs
        consume_tasks = call_kwargs["consume_tasks"]
        overrides = consume_tasks[0].kwargs["overrides"]
        assert overrides.filename == nfc_filename
