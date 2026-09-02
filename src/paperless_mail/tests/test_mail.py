import dataclasses
import email.contentmanager
import time
import uuid
from collections import namedtuple
from contextlib import AbstractContextManager
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from imap_tools import NOT
from imap_tools import EmailAddress
from imap_tools import FolderInfo
from imap_tools import MailboxFolderSelectError
from imap_tools import MailboxLoginError
from imap_tools import MailMessage
from imap_tools import MailMessageFlags
from imap_tools import errors
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Correspondent
from documents.models import MatchingModel
from documents.tests.factories import CorrespondentFactory
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_mail import tasks
from paperless_mail.mail import MailAccountHandler
from paperless_mail.mail import MailError
from paperless_mail.mail import TagMailAction
from paperless_mail.mail import apply_mail_action
from paperless_mail.mail import error_callback
from paperless_mail.mail import get_mailbox
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.factories import MailRuleFactory


@dataclasses.dataclass
class _AttachmentDef:
    filename: str = "a_file.pdf"
    maintype: str = "application/pdf"
    subtype: str = "pdf"
    disposition: str = "attachment"
    content: bytes = b"a PDF document"


class BogusFolderManager:
    current_folder = "INBOX"
    uidvalidity = "1"

    def set(self, new_folder) -> None:
        if new_folder not in ["INBOX", "spam"]:
            raise MailboxFolderSelectError(None, "uhm")
        self.current_folder = new_folder

    def status(self, folder, options):
        return {"UIDVALIDITY": self.uidvalidity}


class BogusClient:
    def __init__(self, messages) -> None:
        self.messages: list[MailMessage] = messages
        self.capabilities: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def authenticate(self, mechanism, authobject) -> None:
        # authobject must be a callable object
        auth_bytes = authobject(None)
        if auth_bytes != b"\x00admin\x00w57\xc3\xa4\xc3\xb6\xc3\xbcw4b6huwb6nhu":
            raise MailboxLoginError("BAD", "OK")

    def uid(self, command, *args) -> None:
        if command == "STORE":
            for message in self.messages:
                if message.uid == args[0]:
                    flag = args[2]
                    if flag == "processed":
                        message._raw_flag_data.append(b"+FLAGS (processed)")
                        if hasattr(message, "flags"):
                            del message.flags


class BogusMailBox(AbstractContextManager):
    # Common values so tests don't need to remember an accepted login
    USERNAME: str = "admin"
    ASCII_PASSWORD: str = "secret"
    # Note the non-ascii characters here
    UTF_PASSWORD: str = "w57äöüw4b6huwb6nhu"
    # A dummy access token
    ACCESS_TOKEN = "ea7e075cd3acf2c54c48e600398d5d5a"

    def __init__(self) -> None:
        self.messages: list[MailMessage] = []
        self.messages_spam: list[MailMessage] = []
        self.folder = BogusFolderManager()
        self.client = BogusClient(self.messages)
        self._host = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def updateClient(self) -> None:
        self.client = BogusClient(self.messages)

    def login(self, username, password) -> None:
        # This will raise a UnicodeEncodeError if the password is not ASCII only
        password.encode("ascii")
        # Otherwise, check for correct values
        if username != self.USERNAME or password != self.ASCII_PASSWORD:
            raise MailboxLoginError("BAD", "OK")

    def login_utf8(self, username, password) -> None:
        # Expected to only be called with the UTF-8 password
        if username != self.USERNAME or password != self.UTF_PASSWORD:
            raise MailboxLoginError("BAD", "OK")

    def xoauth2(self, username: str, access_token: str) -> None:
        if username != self.USERNAME or access_token != self.ACCESS_TOKEN:
            raise MailboxLoginError("BAD", "OK")

    def fetch(
        self,
        criteria="ALL",
        charset="",
        *,
        mark_seen=True,
        bulk=True,
        uid_list=None,
    ):
        if uid_list is not None:
            return [m for m in self.messages if m.uid in uid_list]
        return self._filter_messages(criteria)

    def uids(self, criteria, charset="") -> list[str]:
        return [m.uid for m in self._filter_messages(criteria)]

    def _filter_messages(self, criteria):
        msg = self.messages

        criteria = str(criteria).strip("()").split(" ")

        if "UNSEEN" in criteria:
            msg = filter(lambda m: not m.seen, msg)

        if "SUBJECT" in criteria:
            subject = criteria[criteria.index("SUBJECT") + 1].strip('"')
            msg = filter(lambda m: subject in m.subject, msg)

        if "BODY" in criteria:
            body = criteria[criteria.index("BODY") + 1].strip('"')
            msg = filter(lambda m: body in m.text, msg)

        if "FROM" in criteria:
            from_ = criteria[criteria.index("FROM") + 1].strip('"')
            msg = filter(lambda m: from_ in m.from_, msg)

        if "TO" in criteria:
            to_ = criteria[criteria.index("TO") + 1].strip('"')
            msg = filter(lambda m: any(to_ in to_addr for to_addr in m.to), msg)

        if "UNFLAGGED" in criteria:
            msg = filter(lambda m: not m.flagged, msg)

        if "UNKEYWORD" in criteria:
            tag = criteria[criteria.index("UNKEYWORD") + 1].strip("'")
            msg = filter(lambda m: tag not in m.flags, msg)

        if "(X-GM-LABELS" in criteria:  # ['NOT', '(X-GM-LABELS', '"processed"']
            msg = filter(lambda m: "processed" not in m.flags, msg)

        if "UID" in criteria:
            uid_list = criteria[criteria.index("UID") + 1].split(",")
            msg = filter(lambda m: m.uid in uid_list, msg)

        return list(msg)

    def delete(self, uid_list) -> None:
        self.messages = list(filter(lambda m: m.uid not in uid_list, self.messages))

    def flag(self, uid_list, flag_set, value) -> None:
        for message in self.messages:
            if message.uid in uid_list:
                for flag in flag_set:
                    if flag == MailMessageFlags.FLAGGED:
                        message.flagged = value
                    if flag == MailMessageFlags.SEEN:
                        message.seen = value
                    if flag == "processed":
                        message._raw_flag_data.append(b"+FLAGS (processed)")
                        if hasattr(message, "flags"):
                            del message.flags

    def move(self, uid_list, folder) -> None:
        if folder == "spam":
            self.messages_spam += list(
                filter(lambda m: m.uid in uid_list, self.messages),
            )
            self.messages = list(filter(lambda m: m.uid not in uid_list, self.messages))
        else:
            raise Exception


def fake_magic_from_buffer(buffer, *, mime=False):
    if mime:
        if "PDF" in str(buffer):
            return "application/pdf"
        else:
            return "unknown/type"
    else:
        return "Some verbose file description"


class MessageBuilder:
    def __init__(self) -> None:
        self._next_uid = 1

    def create_message(
        self,
        *,
        attachments: int | list[_AttachmentDef] = 1,
        body: str = "",
        subject: str = "the subject",
        from_: str = "no_one@mail.com",
        to: list[str] | None = None,
        seen: bool = False,
        flagged: bool = False,
        processed: bool = False,
    ) -> MailMessage:
        if to is None:
            to = ["tosomeone@somewhere.com"]

        email_msg = email.message.EmailMessage()
        # TODO: This does NOT set the UID
        email_msg["Message-ID"] = str(uuid.uuid4())
        email_msg["Subject"] = subject
        email_msg["From"] = from_
        email_msg["To"] = str(" ,".join(to))
        email_msg.set_content(body)

        # Either add some default number of attachments
        # or the provided attachments
        if isinstance(attachments, int):
            for i in range(attachments):
                attachment = _AttachmentDef(filename=f"file_{i}.pdf")
                email_msg.add_attachment(
                    attachment.content,
                    maintype=attachment.maintype,
                    subtype=attachment.subtype,
                    disposition=attachment.disposition,
                    filename=attachment.filename,
                )
        else:
            for attachment in attachments:
                email_msg.add_attachment(
                    attachment.content,
                    maintype=attachment.maintype,
                    subtype=attachment.subtype,
                    disposition=attachment.disposition,
                    filename=attachment.filename,
                )

        # Convert the EmailMessage to an imap_tools MailMessage
        imap_msg = MailMessage.from_bytes(email_msg.as_bytes())

        # TODO: Unsure how to add a uid to the actual EmailMessage. This hacks it in,
        #  based on how imap_tools uses regex to extract it.
        #  This should be a large enough pool
        uid = self._next_uid
        self._next_uid += 1

        imap_msg._raw_uid_data = f"UID {uid}".encode()

        imap_msg.seen = seen
        imap_msg.flagged = flagged
        if processed:
            imap_msg._raw_flag_data.append(b"+FLAGS (processed)")
            if hasattr(imap_msg, "flags"):
                del imap_msg.flags

        return imap_msg


def reset_bogus_mailbox(
    bogus_mailbox: BogusMailBox,
    message_builder: MessageBuilder,
) -> None:
    bogus_mailbox.messages = []
    bogus_mailbox.messages_spam = []
    bogus_mailbox.messages.append(
        message_builder.create_message(
            subject="Invoice 1",
            from_="amazon@amazon.de",
            to=["me@myselfandi.com", "helpdesk@mydomain.com"],
            body="cables",
            seen=True,
            flagged=False,
            processed=False,
        ),
    )
    bogus_mailbox.messages.append(
        message_builder.create_message(
            subject="Invoice 2",
            body="from my favorite electronic store",
            to=["invoices@mycompany.com"],
            seen=False,
            flagged=True,
            processed=True,
        ),
    )
    bogus_mailbox.messages.append(
        message_builder.create_message(
            subject="Claim your $10M price now!",
            from_="amazon@amazon-some-indian-site.org",
            to=["special@me.me"],
            seen=False,
        ),
    )
    bogus_mailbox.updateClient()


class MailMocker(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    def setUp(self) -> None:
        self.bogus_mailbox = BogusMailBox()
        self.messageBuilder = MessageBuilder()

        reset_bogus_mailbox(self.bogus_mailbox, self.messageBuilder)

        patcher = mock.patch("paperless_mail.mail.PinnedMailBox")
        m = patcher.start()
        m.return_value = self.bogus_mailbox
        self.addCleanup(patcher.stop)

        patcher = mock.patch("paperless_mail.mail.queue_consumption_tasks")
        self._queue_consumption_tasks_mock = patcher.start()
        self.addCleanup(patcher.stop)

        super().setUp()

    def assert_queue_consumption_tasks_call_args(
        self,
        expected_call_args: list[list[dict[str, str]]],
    ) -> None:
        """
        Verifies that queue_consumption_tasks has been called with the expected arguments.

        expected_call_args is the following format:

        * List of calls to queue_consumption_tasks, called once per mail, where each element is:
        * List of signatures for the consume_file task, where each element is:
        * dictionary containing arguments that need to be present in the consume_file signature.

        """

        # assert number of calls to queue_consumption_tasks match
        self.assertEqual(
            len(self._queue_consumption_tasks_mock.call_args_list),
            len(expected_call_args),
        )

        for (mock_args, mock_kwargs), expected_signatures in zip(
            self._queue_consumption_tasks_mock.call_args_list,
            expected_call_args,
        ):
            consume_tasks = mock_kwargs["consume_tasks"]

            # assert number of consume_file tasks match
            self.assertEqual(len(consume_tasks), len(expected_signatures))

            for consume_task, expected_signature in zip(
                consume_tasks,
                expected_signatures,
            ):
                input_doc = consume_task.kwargs["input_doc"]
                overrides = consume_task.kwargs["overrides"]

                # assert the file exists
                self.assertIsFile(input_doc.original_file)

                # assert all expected arguments are present in the signature
                for key, value in expected_signature.items():
                    if key == "override_correspondent_id":
                        self.assertEqual(overrides.correspondent_id, value)
                    elif key == "override_filename":
                        self.assertEqual(overrides.filename, value)
                    elif key == "override_title":
                        self.assertEqual(overrides.title, value)
                    else:
                        self.fail("No match for expected arg")

    def apply_mail_actions(self) -> None:
        """
        Applies pending actions to mails by inspecting calls to the queue_consumption_tasks method.
        """
        for args, kwargs in self._queue_consumption_tasks_mock.call_args_list:
            message = kwargs["message"]
            rule = kwargs["rule"]
            apply_mail_action([], rule.pk, message.uid, message.subject, message.date)


def assert_eventually_equals(
    getter_fn,
    expected_value,
    timeout=1.0,
    interval=0.05,
) -> None:
    """
    Repeatedly calls `getter_fn()` until the result equals `expected_value`,
    or times out after `timeout` seconds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getter_fn() == expected_value:
            return
        time.sleep(interval)
    actual = getter_fn()
    raise AssertionError(f"Expected {expected_value}, but got {actual}")


@mock.patch("paperless_mail.mail.magic.from_buffer", fake_magic_from_buffer)
class TestMail(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    TestCase,
):
    def setUp(self) -> None:
        self.mailMocker = MailMocker()
        self.mailMocker.setUp()
        self.addCleanup(self.mailMocker.doCleanups)
        self.mail_account_handler = MailAccountHandler()

        super().setUp()

    @mock.patch("paperless_mail.mail.MAIL_FETCH_BATCH_SIZE", 5)
    def test_handle_mail_account_batches_body_fetch_for_large_backlog(self) -> None:
        """
        GIVEN:
            - More new/unprocessed mail than MAIL_FETCH_BATCH_SIZE
        WHEN:
            - The mail account is processed
        THEN:
            - The body fetch is issued once, with all UIDs and the configured batch size
              handed to imap_tools so it can bulk-fetch in batches server-side
            - Every message is still processed (none dropped at a batch boundary)
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        message_count = 12  # more than the patched batch size of 5
        self.mailMocker.bogus_mailbox.messages = [
            self.mailMocker.messageBuilder.create_message(
                subject=f"No attachment {i}",
                attachments=[],
            )
            for i in range(message_count)
        ]
        self.mailMocker.bogus_mailbox.updateClient()

        with mock.patch.object(
            self.mailMocker.bogus_mailbox,
            "fetch",
            wraps=self.mailMocker.bogus_mailbox.fetch,
        ) as fetch_spy:
            self.mail_account_handler.handle_mail_account(account)

        # A single fetch() call hands the full UID list and batch size to imap_tools,
        # which does its own bulk-fetching in batches of MAIL_FETCH_BATCH_SIZE.
        fetch_spy.assert_called_once()
        self.assertEqual(fetch_spy.call_args.kwargs["bulk"], 5)
        self.assertEqual(len(fetch_spy.call_args.kwargs["uid_list"]), message_count)
        self.assertEqual(
            ProcessedMail.objects.filter(rule=rule).count(),
            message_count,
        )

    def test_get_correspondent(self) -> None:
        message = namedtuple("MailMessage", [])
        message.from_ = "someone@somewhere.com"
        message.from_values = EmailAddress(
            "Someone!",
            "someone@somewhere.com",
        )

        message2 = namedtuple("MailMessage", [])
        message2.from_ = "me@localhost.com"
        message2.from_values = EmailAddress(
            "",
            "fake@localhost.com",
        )

        me_localhost = CorrespondentFactory(name=message2.from_)
        someone_else = CorrespondentFactory(name="someone else")

        handler = MailAccountHandler()

        rule = MailRule(
            name="a",
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_NOTHING,
        )
        self.assertIsNone(handler._get_correspondent(message, rule))

        rule = MailRule(
            name="b",
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_EMAIL,
        )
        c = handler._get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "someone@somewhere.com")
        self.assertEqual(c.matching_algorithm, MatchingModel.MATCH_LITERAL)
        self.assertEqual(c.match, "someone@somewhere.com")
        c = handler._get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "me@localhost.com")
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(
            name="c",
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_NAME,
        )
        c = handler._get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "Someone!")
        c = handler._get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(
            name="d",
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_CUSTOM,
            assign_correspondent=someone_else,
        )
        c = handler._get_correspondent(message, rule)
        self.assertEqual(c, someone_else)

    def test_get_title(self) -> None:
        message = namedtuple("MailMessage", [])
        message.subject = "the message title"
        att = namedtuple("Attachment", [])
        att.filename = "this_is_the_file.pdf"

        handler = MailAccountHandler()

        rule = MailRule(
            name="a",
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
        )
        self.assertEqual(handler._get_title(message, att, rule), "this_is_the_file")
        rule = MailRule(
            name="b",
            assign_title_from=MailRule.TitleSource.FROM_SUBJECT,
        )
        self.assertEqual(handler._get_title(message, att, rule), "the message title")
        rule = MailRule(
            name="b",
            assign_title_from=MailRule.TitleSource.NONE,
        )
        self.assertEqual(handler._get_title(message, att, rule), None)

    def test_handle_message(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            subject="the message title",
            from_="Myself",
            attachments=2,
        )

        account = MailAccount.objects.create()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            account=account,
        )
        rule.save()

        result = self.mail_account_handler._handle_message(message, rule)

        self.assertEqual(result, 2)

        self.mailMocker._queue_consumption_tasks_mock.assert_called()

        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_title": "file_0", "override_filename": "file_0.pdf"},
                    {"override_title": "file_1", "override_filename": "file_1.pdf"},
                ],
            ],
        )

    def test_bogus_mailbox_uids_and_uid_criteria(self) -> None:
        mailbox = self.mailMocker.bogus_mailbox
        all_messages = list(mailbox.messages)

        # uids() returns the UIDs of unseen messages, no bodies needed to call it
        unseen_uids = mailbox.uids("(UNSEEN)")
        self.assertEqual(
            set(unseen_uids),
            {m.uid for m in all_messages if not m.seen},
        )

        # fetch() with an explicit UID criteria returns only the matching messages
        target_uid = all_messages[0].uid
        from imap_tools import AND

        fetched = mailbox.fetch(AND(uid=[target_uid]), mark_seen=False)
        self.assertEqual([m.uid for m in fetched], [target_uid])

    def test_handle_empty_message(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            subject="No attachments here",
            attachments=[],
        )

        account = MailAccount.objects.create()
        rule = MailRule.objects.create(
            account=account,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        result = self.mail_account_handler._handle_message(message, rule)

        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()
        self.assertEqual(result, 0)

        processed = ProcessedMail.objects.get(
            rule=rule,
            uid=message.uid,
            folder=rule.folder,
        )
        self.assertEqual(processed.status, "PROCESSED_WO_CONSUMPTION")

        # Calling it again must not create a second row
        self.mail_account_handler._handle_message(message, rule)
        self.assertEqual(
            ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).count(),
            1,
        )

    def test_handle_unknown_mime_type(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            attachments=[
                _AttachmentDef(filename="f1.pdf"),
                _AttachmentDef(
                    filename="f2.json",
                    content=b"{'much': 'payload.', 'so': 'json', 'wow': true}",
                ),
            ],
        )

        account = MailAccount.objects.create()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            account=account,
        )
        rule.save()

        result = self.mail_account_handler._handle_message(message, rule)

        self.assertEqual(result, 1)
        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_filename": "f1.pdf"},
                ],
            ],
        )

    def test_handle_disposition(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            attachments=[
                _AttachmentDef(
                    filename="f1.pdf",
                    disposition="inline",
                ),
                _AttachmentDef(filename="f2.pdf"),
            ],
        )

        account = MailAccount.objects.create()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            account=account,
        )
        rule.save()

        result = self.mail_account_handler._handle_message(message, rule)
        self.assertEqual(result, 1)
        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_filename": "f2.pdf"},
                ],
            ],
        )

    def test_handle_inline_files(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            attachments=[
                _AttachmentDef(
                    filename="f1.pdf",
                    disposition="inline",
                ),
                _AttachmentDef(filename="f2.pdf"),
            ],
        )

        account = MailAccount.objects.create()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            account=account,
            attachment_type=MailRule.AttachmentProcessing.EVERYTHING,
        )
        rule.save()

        result = self.mail_account_handler._handle_message(message, rule)
        self.assertEqual(result, 2)
        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_filename": "f1.pdf"},
                    {"override_filename": "f2.pdf"},
                ],
            ],
        )

    def test_filename_filter(self) -> None:
        """
        GIVEN:
            - Email with multiple similar named attachments
            - Rule with inclusive and exclusive filters
        WHEN:
            - Mail action filtering is checked
        THEN:
            - Mail action should not be performed for files excluded
            - Mail action should be performed for files included
        """
        message = self.mailMocker.messageBuilder.create_message(
            attachments=[
                _AttachmentDef(filename="f1.pdf"),
                _AttachmentDef(filename="f2.pdf"),
                _AttachmentDef(filename="f3.pdf"),
                _AttachmentDef(filename="f2.png"),
                _AttachmentDef(filename="file.PDf"),
                _AttachmentDef(filename="f1.Pdf"),
            ],
        )

        @dataclasses.dataclass(frozen=True)
        class FilterTestCase:
            name: str
            include_pattern: str | None
            exclude_pattern: str | None
            expected_matches: list[str]

        tests = [
            FilterTestCase(
                "PDF Wildcard",
                include_pattern="*.pdf",
                exclude_pattern=None,
                expected_matches=["f1.pdf", "f2.pdf", "f3.pdf", "file.PDf", "f1.Pdf"],
            ),
            FilterTestCase(
                "F1 PDF Only",
                include_pattern="f1.pdf",
                exclude_pattern=None,
                expected_matches=["f1.pdf", "f1.Pdf"],
            ),
            FilterTestCase(
                "All Files",
                include_pattern="*",
                exclude_pattern=None,
                expected_matches=[
                    "f1.pdf",
                    "f2.pdf",
                    "f3.pdf",
                    "f2.png",
                    "file.PDf",
                    "f1.Pdf",
                ],
            ),
            FilterTestCase(
                "PNG Only",
                include_pattern="*.png",
                exclude_pattern=None,
                expected_matches=["f2.png"],
            ),
            FilterTestCase(
                "PDF Files with f2 and f3",
                include_pattern="f2.pdf,f3*",
                exclude_pattern=None,
                expected_matches=["f2.pdf", "f3.pdf"],
            ),
            FilterTestCase(
                "PDF Files without f1",
                include_pattern="*.pdf",
                exclude_pattern="f1*",
                expected_matches=["f2.pdf", "f3.pdf", "file.PDf"],
            ),
            FilterTestCase(
                "PDF Files without f1 and f2",
                include_pattern="*.pdf",
                exclude_pattern="f1*,f2*",
                expected_matches=["f3.pdf", "file.PDf"],
            ),
            FilterTestCase(
                "PDF Files without f1 and f2 and f3",
                include_pattern="*.pdf",
                exclude_pattern="f1*,f2*,f3*",
                expected_matches=["file.PDf"],
            ),
            FilterTestCase(
                "All Files, no PNG",
                include_pattern="*",
                exclude_pattern="*.png",
                expected_matches=[
                    "f1.pdf",
                    "f2.pdf",
                    "f3.pdf",
                    "file.PDf",
                    "f1.Pdf",
                ],
            ),
        ]

        for test_case in tests:
            with self.subTest(msg=test_case.name):
                self.mailMocker._queue_consumption_tasks_mock.reset_mock()
                account = MailAccount(name=str(uuid.uuid4()))
                account.save()
                rule = MailRule(
                    name=str(uuid.uuid4()),
                    assign_title_from=MailRule.TitleSource.FROM_FILENAME,
                    account=account,
                    filter_attachment_filename_include=test_case.include_pattern,
                    filter_attachment_filename_exclude=test_case.exclude_pattern,
                )
                rule.save()

                self.mail_account_handler._handle_message(message, rule)
                self.mailMocker.assert_queue_consumption_tasks_call_args(
                    [
                        [{"override_filename": m} for m in test_case.expected_matches],
                    ],
                )

    @pytest.mark.flaky(reruns=4)
    def test_filename_filter_inline_no_consumption(self) -> None:
        """
        GIVEN:
            - Rule that processes all attachments but filters by filename
        WHEN:
            - Given email with inline attachment that does not meet filename filter
        THEN:
            - Mail action should not be performed
        """
        message = self.mailMocker.messageBuilder.create_message(
            attachments=[
                _AttachmentDef(
                    filename="test.png",
                    disposition="inline",
                ),
            ],
        )
        self.mailMocker.bogus_mailbox.messages.append(message)
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        account.save()
        rule = MailRule(
            name=str(uuid.uuid4()),
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            account=account,
            filter_attachment_filename_include="*.pdf",
            attachment_type=MailRule.AttachmentProcessing.EVERYTHING,
            action=MailRule.MailAction.DELETE,
        )
        rule.save()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 4)

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 1)

    def test_handle_mail_account_mark_read(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            0,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    @pytest.mark.flaky(reruns=4)
    def test_handle_mail_account_delete(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
            filter_subject="Invoice",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        assert_eventually_equals(lambda: len(self.mailMocker.bogus_mailbox.messages), 1)

    def test_handle_mail_account_delete_no_filters(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
            maximum_age=0,
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 0)

    def test_handle_mail_account_overlapping_rules_only_first_consumes(self) -> None:
        """
        GIVEN:
            - Multiple rules that match the same mail
        WHEN:
            - Mail account is processed
        THEN:
            - Only the first rule should be applied
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        first_rule = MailRule.objects.create(
            name="testrule-first",
            account=account,
            action=MailRule.MailAction.DELETE,
            filter_subject="Claim",
            order=1,
        )
        _ = MailRule.objects.create(
            name="testrule-second",
            account=account,
            action=MailRule.MailAction.DELETE,
            filter_subject="Claim",
            order=2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 1)
        queued_rule = self.mailMocker._queue_consumption_tasks_mock.call_args.kwargs[
            "rule"
        ]
        self.assertEqual(queued_rule.id, first_rule.id)

    def test_handle_mail_account_skips_body_fetch_for_already_processed_mail(
        self,
    ) -> None:
        """
        GIVEN:
            - An attachment-less mail under an attachments-only mark-read rule,
              already recorded as PROCESSED_WO_CONSUMPTION
        WHEN:
            - The mail account is processed again and the mail still matches the
              search criteria (it was never marked read, since no mail action is
              applied for the no-consumption case)
        THEN:
            - No IMAP body fetch happens for that mail; only the cheap UID search runs.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        message = self.mailMocker.messageBuilder.create_message(
            subject="No attachment",
            attachments=[],
        )
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        # First run: records ProcessedMail without consuming anything.
        self.mail_account_handler.handle_mail_account(account)
        self.assertTrue(
            ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).exists(),
        )
        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()

        # Second run: message still matches UNSEEN (mark-read action never ran),
        # but its body must not be downloaded again.
        with mock.patch.object(
            self.mailMocker.bogus_mailbox,
            "fetch",
            wraps=self.mailMocker.bogus_mailbox.fetch,
        ) as fetch_spy:
            self.mail_account_handler.handle_mail_account(account)

        fetch_spy.assert_not_called()

    def test_handle_mail_account_skip_duplicate_uids_from_fetch(self) -> None:
        """
        GIVEN:
            - Multiple mails with the same UID returned from the mailbox fetch method
        WHEN:
            - Mail account is processed
        THEN:
            - Only one of the mails should be processed, to avoid duplicate processing due to fetch issues
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
            filter_subject="Duplicated mail",
        )

        duplicated_message = self.mailMocker.messageBuilder.create_message(
            subject="Duplicated mail",
        )
        self.mailMocker.bogus_mailbox.messages = [
            duplicated_message,
            duplicated_message,
        ]
        self.mailMocker.bogus_mailbox.updateClient()

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 1)

    def test_handle_mail_account_skips_mail_already_processed_in_same_uidvalidity(
        self,
    ) -> None:
        """
        GIVEN:
            - A ProcessedMail row recorded under the mailbox's current UIDVALIDITY
        WHEN:
            - A mail with the same UID is fetched from the same UIDVALIDITY epoch
        THEN:
            - The mail is skipped as a duplicate.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
        )

        message = self.mailMocker.messageBuilder.create_message()
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        self.mailMocker.bogus_mailbox.folder.uidvalidity = "SAME"
        ProcessedMail.objects.create(
            rule=rule,
            folder=rule.folder,
            uid=message.uid,
            uid_validity="SAME",
            subject="Previously processed mail",
            status="SUCCESS",
            received=timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0)),
        )

        self.mail_account_handler.handle_mail_account(account)

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 0)

    def test_handle_mail_account_processes_mail_after_uidvalidity_change(
        self,
    ) -> None:
        """
        GIVEN:
            - A ProcessedMail row recorded under a previous UIDVALIDITY epoch
        WHEN:
            - A mail with the same UID is fetched after UIDVALIDITY has changed
        THEN:
            - The mail is processed, not skipped as a duplicate.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
        )

        message = self.mailMocker.messageBuilder.create_message()
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        self.mailMocker.bogus_mailbox.folder.uidvalidity = "NEW"
        ProcessedMail.objects.create(
            rule=rule,
            folder=rule.folder,
            uid=message.uid,
            uid_validity="OLD",
            subject="Previously processed mail",
            status="SUCCESS",
            received=timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0)),
        )

        self.mail_account_handler.handle_mail_account(account)

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 1)

    def test_handle_mail_account_skips_mail_processed_before_uidvalidity_tracking(
        self,
    ) -> None:
        """
        GIVEN:
            - A ProcessedMail row recorded before UIDVALIDITY tracking existed
              (uid_validity is NULL)
        WHEN:
            - A mail with the same UID is fetched
        THEN:
            - The mail is skipped as a duplicate, to avoid re-ingesting all
              previously processed mail after upgrading.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
        )

        message = self.mailMocker.messageBuilder.create_message()
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        ProcessedMail.objects.create(
            rule=rule,
            folder=rule.folder,
            uid=message.uid,
            uid_validity=None,
            subject="Previously processed mail",
            status="SUCCESS",
            received=timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0)),
        )

        self.mail_account_handler.handle_mail_account(account)

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 0)

    def test_handle_mail_account_processes_mail_when_uidvalidity_unavailable(
        self,
    ) -> None:
        """
        GIVEN:
            - The mail server fails to report a UIDVALIDITY for the folder
        WHEN:
            - A mail account is processed
        THEN:
            - The failure is logged and the rule still processes the mail,
              instead of the whole rule being disabled.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
        )

        message = self.mailMocker.messageBuilder.create_message()
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        self.mailMocker.bogus_mailbox.folder.status = mock.MagicMock(
            side_effect=errors.MailboxFolderStatusError(("NO", [b"unsupported"]), "OK"),
        )

        with self.assertLogs("paperless_mail", level="WARNING") as cm:
            self.mail_account_handler.handle_mail_account(account)

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 1)
        self.assertEqual(len(cm.output), 1)
        self.assertIn(
            "Server does not support retrieving UIDVALIDITY",
            cm.output[0],
        )

    def test_handle_mail_account_skips_mail_when_uidvalidity_unavailable_but_prior_record_exists(
        self,
    ) -> None:
        """
        GIVEN:
            - A ProcessedMail row recorded with a real uid_validity value
            - The mail server fails to report UIDVALIDITY (MailboxFolderStatusError),
              so _get_uid_validity returns None
        WHEN:
            - A mail with the same UID is fetched
        THEN:
            - The mail is skipped as already-processed rather than re-ingested,
              falling back to (rule, uid, folder) matching.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.DELETE,
        )

        message = self.mailMocker.messageBuilder.create_message()
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        ProcessedMail.objects.create(
            rule=rule,
            folder=rule.folder,
            uid=message.uid,
            uid_validity="REAL_VALIDITY",
            subject="Previously processed mail",
            status="SUCCESS",
            received=timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0)),
        )

        self.mailMocker.bogus_mailbox.folder.status = mock.MagicMock(
            side_effect=errors.MailboxFolderStatusError(("NO", [b"unsupported"]), "OK"),
        )

        self.mail_account_handler.handle_mail_account(account)

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 0)

    @pytest.mark.flaky(reruns=4)
    def test_handle_mail_account_flag(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.FLAG,
            filter_subject="Invoice",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNFLAGGED", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNFLAGGED", mark_seen=False)),
            1,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    @pytest.mark.flaky(reruns=4)
    def test_handle_mail_account_move(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 0)

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 1)

    def test_handle_mail_account_move_no_filters(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            maximum_age=0,
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 0)

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 0)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 3)

    def test_handle_mail_account_tag(self) -> None:
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.TAG,
            action_parameter="processed",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(
                self.mailMocker.bogus_mailbox.fetch(
                    "UNKEYWORD processed",
                    mark_seen=False,
                ),
            ),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(
                self.mailMocker.bogus_mailbox.fetch(
                    "UNKEYWORD processed",
                    mark_seen=False,
                ),
            ),
            0,
        )

    def test_handle_mail_account_tag_gmail(self) -> None:
        self.mailMocker.bogus_mailbox._host = "imap.gmail.com"
        self.mailMocker.bogus_mailbox.client.capabilities = ["X-GM-EXT-1"]

        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.TAG,
            action_parameter="processed",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        criteria = NOT(gmail_label="processed")
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch(criteria, mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch(criteria, mark_seen=False)),
            0,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    def test_tag_mail_action_applemail_wrong_input(self) -> None:
        self.assertRaises(
            MailError,
            TagMailAction,
            "apple:black",
            supports_gmail_labels=False,
        )

    def test_handle_mail_account_tag_applemail(self) -> None:
        # all mails will be FLAGGED afterwards

        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.TAG,
            action_parameter="apple:green",
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNFLAGGED", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNFLAGGED", mark_seen=False)),
            0,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    def test_error_login(self) -> None:
        """
        GIVEN:
            - Account configured with incorrect password
        WHEN:
            - Account tried to login
        THEN:
            - MailError with correct message raised
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="wrong",
        )

        with self.assertRaisesRegex(
            MailError,
            "Error while authenticating account",
        ):
            self.mail_account_handler.handle_mail_account(account)

    @pytest.mark.flaky(reruns=4)
    def test_error_skip_account(self) -> None:
        _ = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="wroasdng",
        )

        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
        )

        tasks.process_mail_accounts()
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 1)

    @pytest.mark.flaky(reruns=4)
    def test_error_skip_rule(self) -> None:
        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
            order=1,
            folder="uuuhhhh",
        )
        _ = MailRule.objects.create(
            name="testrule2",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
            order=2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages_spam), 1)

    def test_error_folder_set(self) -> None:
        """
        GIVEN:
            - Mail rule with non-existent folder
        THEN:
            - Should call list to output all folders in the account
            - Should not process any messages
        """
        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
            order=1,
            folder="uuuhhhh",  # Invalid folder name
        )

        self.mailMocker.bogus_mailbox.folder.list = mock.Mock(
            return_value=[FolderInfo("SomeFoldername", "|", ())],
        )

        self.mail_account_handler.handle_mail_account(account)

        self.mailMocker.bogus_mailbox.folder.list.assert_called_once()
        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()

    def test_error_folder_set_error_listing(self) -> None:
        """
        GIVEN:
            - Mail rule with non-existent folder
            - Mail account folder listing raises exception
        THEN:
            - Should not process any messages
        """
        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            filter_subject="Claim",
            order=1,
            folder="uuuhhhh",  # Invalid folder name
        )

        self.mailMocker.bogus_mailbox.folder.list = mock.Mock(
            side_effect=MailboxFolderSelectError(None, "uhm"),
        )

        self.mail_account_handler.handle_mail_account(account)

        self.mailMocker.bogus_mailbox.folder.list.assert_called_once()
        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()

    @pytest.mark.flaky(reruns=4)
    @mock.patch("paperless_mail.mail.MailAccountHandler._get_correspondent")
    def test_error_skip_mail(self, m) -> None:
        def get_correspondent_fake(message, rule) -> None:
            if message.from_ == "amazon@amazon.de":
                raise ValueError("Does not compute.")
            else:
                return

        m.side_effect = get_correspondent_fake

        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        # test that we still consume mail even if some mails throw errors.
        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 2)

        # faulty mail still in inbox, untouched
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 1)
        self.assertEqual(
            self.mailMocker.bogus_mailbox.messages[0].from_,
            "amazon@amazon.de",
        )

    def test_error_create_correspondent(self) -> None:
        account = MailAccount.objects.create(
            name="test2",
            imap_server="",
            username="admin",
            password="secret",
        )
        _ = MailRule.objects.create(
            name="testrule",
            filter_from="amazon@amazon.de",
            account=account,
            action=MailRule.MailAction.MOVE,
            action_parameter="spam",
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_EMAIL,
        )

        self.mail_account_handler.handle_mail_account(account)

        self.mailMocker._queue_consumption_tasks_mock.assert_called_once()

        c = Correspondent.objects.get(name="amazon@amazon.de")
        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_correspondent_id": c.id},
                ],
            ],
        )

        self.mailMocker._queue_consumption_tasks_mock.reset_mock()
        reset_bogus_mailbox(
            self.mailMocker.bogus_mailbox,
            self.mailMocker.messageBuilder,
        )

        with mock.patch("paperless_mail.mail.Correspondent.objects.get_or_create") as m:
            m.side_effect = DatabaseError()

            self.mail_account_handler.handle_mail_account(account)

        self.mailMocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {"override_correspondent_id": None},
                ],
            ],
        )

    @pytest.mark.flaky(reruns=4)
    def test_filters(self) -> None:
        account = MailAccount.objects.create(
            name="test3",
            imap_server="",
            username="admin",
            password="secret",
        )

        for f_body, f_from, f_to, f_subject, expected_mail_count in [
            (None, None, None, "Claim", 1),
            ("electronic", None, None, None, 1),
            (None, "amazon", None, None, 2),
            ("cables", "amazon", None, "Invoice", 1),
            (None, None, "test@email.com", None, 0),
            (None, None, "invoices@mycompany.com", None, 1),
            ("electronic", None, "invoices@mycompany.com", None, 1),
            (None, "amazon", "me@myselfandi.com", None, 1),
        ]:
            with self.subTest(f_body=f_body, f_from=f_from, f_subject=f_subject):
                MailRule.objects.all().delete()
                _ = MailRule.objects.create(
                    name="testrule3",
                    account=account,
                    action=MailRule.MailAction.DELETE,
                    filter_subject=f_subject,
                    filter_body=f_body,
                    filter_from=f_from,
                    filter_to=f_to,
                )
                reset_bogus_mailbox(
                    self.mailMocker.bogus_mailbox,
                    self.mailMocker.messageBuilder,
                )
                self.mailMocker._queue_consumption_tasks_mock.reset_mock()

                self.mailMocker._queue_consumption_tasks_mock.assert_not_called()
                self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

                self.mail_account_handler.handle_mail_account(account)
                self.mailMocker.apply_mail_actions()

                self.assertEqual(
                    len(self.mailMocker.bogus_mailbox.messages),
                    3 - expected_mail_count,
                )
                self.assertEqual(
                    self.mailMocker._queue_consumption_tasks_mock.call_count,
                    expected_mail_count,
                )

    def test_auth_plain_fallback(self) -> None:
        """
        GIVEN:
            - Mail account with password containing non-ASCII characters
        WHEN:
            - Mail account is handled
        THEN:
            - Should still authenticate to the mail account
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username=BogusMailBox.USERNAME,
            # Note the non-ascii characters here
            password=BogusMailBox.UTF_PASSWORD,
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 2)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            0,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    def test_auth_plain_fallback_fails_still(self) -> None:
        """
        GIVEN:
            - Mail account with password containing non-ASCII characters
            - Incorrect password value
        WHEN:
            - Mail account is handled
        THEN:
            - Should raise a MailError for the account
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username=BogusMailBox.USERNAME,
            # Note the non-ascii characters here
            # Passes the check in login, not in authenticate
            password="réception",
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
        )

        self.assertRaises(
            MailError,
            self.mail_account_handler.handle_mail_account,
            account,
        )

    def test_auth_with_valid_token(self) -> None:
        """
        GIVEN:
            - Mail account configured with access token
        WHEN:
            - Mail account is handled
        THEN:
            - Should still authenticate to the mail account
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username=BogusMailBox.USERNAME,
            # Note the non-ascii characters here
            password=BogusMailBox.ACCESS_TOKEN,
            is_token=True,
        )

        _ = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
        )

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 0)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(self.mailMocker._queue_consumption_tasks_mock.call_count, 2)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            0,
        )
        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)

    def test_disabled_rule(self) -> None:
        """
        GIVEN:
            - Mail rule is disabled
        WHEN:
            - Mail account is handled
        THEN:
            - Should not process any messages
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
            enabled=False,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()

        self.assertEqual(len(self.mailMocker.bogus_mailbox.messages), 3)
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            2,
        )

        self.mail_account_handler.handle_mail_account(account)
        self.mailMocker.apply_mail_actions()
        self.assertEqual(
            len(self.mailMocker.bogus_mailbox.fetch("UNSEEN", mark_seen=False)),
            2,
        )  # still 2


class TestPostConsumeAction(TestCase):
    def setUp(self) -> None:
        self.account = MailAccountFactory()
        self.rule = MailRuleFactory(account=self.account)
        self.message_uid = "12345"
        self.message_subject = "Test Subject"
        self.message_date = timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0))

    @mock.patch("paperless_mail.mail.get_mailbox")
    @mock.patch("paperless_mail.mail.mailbox_login")
    @mock.patch("paperless_mail.mail.get_rule_action")
    def test_post_consume_success(
        self,
        mock_get_rule_action,
        mock_mailbox_login,
        mock_get_mailbox,
    ) -> None:
        mock_mailbox = mock.MagicMock()
        mock_get_mailbox.return_value.__enter__.return_value = mock_mailbox
        mock_action = mock.MagicMock()
        mock_get_rule_action.return_value = mock_action

        apply_mail_action(
            result=[],
            rule_id=self.rule.pk,
            message_uid=self.message_uid,
            message_subject=self.message_subject,
            message_date=self.message_date,
        )

        mock_mailbox_login.assert_called_once_with(mock_mailbox, self.account)
        mock_mailbox.folder.set.assert_called_once_with(self.rule.folder)
        mock_action.post_consume.assert_called_once_with(
            mock_mailbox,
            self.message_uid,
            self.rule.action_parameter,
        )

        processed_mail = ProcessedMail.objects.get(uid=self.message_uid)
        self.assertEqual(processed_mail.status, "SUCCESS")

    @mock.patch("paperless_mail.mail.get_mailbox")
    @mock.patch("paperless_mail.mail.mailbox_login")
    @mock.patch("paperless_mail.mail.get_rule_action")
    def test_post_consume_failure(
        self,
        mock_get_rule_action,
        mock_mailbox_login,
        mock_get_mailbox,
    ) -> None:
        mock_mailbox = mock.MagicMock()
        mock_get_mailbox.return_value.__enter__.return_value = mock_mailbox
        mock_action = mock.MagicMock()
        mock_get_rule_action.return_value = mock_action
        mock_action.post_consume.side_effect = errors.ImapToolsError("Test Exception")

        with (
            self.assertRaises(errors.ImapToolsError),
            self.assertLogs("paperless.mail", level="ERROR") as cm,
        ):
            apply_mail_action(
                result=[],
                rule_id=self.rule.pk,
                message_uid=self.message_uid,
                message_subject=self.message_subject,
                message_date=self.message_date,
            )
            error_str = cm.output[0]
            expected_str = "Error while processing mail action during post_consume"
            self.assertIn(expected_str, error_str)

        processed_mail = ProcessedMail.objects.get(uid=self.message_uid)
        self.assertEqual(processed_mail.status, "FAILED")
        self.assertIn("Test Exception", processed_mail.error)


class TestErrorCallback:
    @pytest.mark.django_db
    def test_error_callback_is_idempotent_for_same_mail(self) -> None:
        """
        GIVEN:
            - A mail rule and a mail that failed to be consumed
        WHEN:
            - error_callback is invoked more than once for the same mail, as
              happens when task_allow_error_cb_on_chord_header fires the
              errback once per failed header task in a chord
        THEN:
            - Only one ProcessedMail row is created for that mail
        """
        account = MailAccountFactory()
        rule = MailRuleFactory(account=account)
        message_uid = "12345"
        message_subject = "Test Subject"
        message_date = timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0))

        for exc_message in ("boom 1", "boom 2"):
            error_callback(
                None,
                Exception(exc_message),
                None,
                rule_id=rule.pk,
                message_uid=message_uid,
                message_subject=message_subject,
                message_date=message_date,
            )

        processed_mails = ProcessedMail.objects.filter(
            rule=rule,
            uid=message_uid,
            folder=rule.folder,
        )
        assert processed_mails.count() == 1
        assert processed_mails.get().status == "FAILED"


class TestManagementCommand(TestCase):
    @mock.patch(
        "paperless_mail.management.commands.mail_fetcher.tasks.process_mail_accounts",
    )
    def test_mail_fetcher(self, m) -> None:
        call_command("mail_fetcher", skip_checks=True)

        m.assert_called_once()


class TestTasks(TestCase):
    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_all_accounts(self, m) -> None:
        m.side_effect = lambda account: 6

        MailAccount.objects.create(
            name="A",
            imap_server="A",
            username="A",
            password="A",
        )
        MailAccount.objects.create(
            name="B",
            imap_server="A",
            username="A",
            password="A",
        )
        MailRule.objects.create(
            name="A",
            account=MailAccount.objects.get(name="A"),
        )
        MailRule.objects.create(
            name="B",
            account=MailAccount.objects.get(name="B"),
        )

        result = tasks.process_mail_accounts()

        self.assertEqual(m.call_count, 2)
        self.assertIn("Added 12", result)

        m.side_effect = lambda account: 0
        result = tasks.process_mail_accounts()
        self.assertIn("No new", result)

    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_accounts_no_enabled_rules(self, m) -> None:
        m.side_effect = lambda account: 6

        MailAccount.objects.create(
            name="A",
            imap_server="A",
            username="A",
            password="A",
        )
        MailAccount.objects.create(
            name="B",
            imap_server="A",
            username="A",
            password="A",
        )
        MailRule.objects.create(
            name="A",
            account=MailAccount.objects.get(name="A"),
            enabled=False,
        )
        MailRule.objects.create(
            name="B",
            account=MailAccount.objects.get(name="B"),
            enabled=False,
        )

        tasks.process_mail_accounts()
        self.assertEqual(m.call_count, 0)

    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_process_with_account_ids(self, m) -> None:
        m.side_effect = lambda account: 6

        account_a = MailAccount.objects.create(
            name="A",
            imap_server="A",
            username="A",
            password="A",
        )
        account_b = MailAccount.objects.create(
            name="B",
            imap_server="A",
            username="A",
            password="A",
        )
        MailRule.objects.create(
            name="A",
            account=account_a,
        )
        MailRule.objects.create(
            name="B",
            account=account_b,
        )

        result = tasks.process_mail_accounts(account_ids=[account_a.id])

        self.assertEqual(m.call_count, 1)
        self.assertIn("Added 6", result)

        m.side_effect = lambda account: 0
        result = tasks.process_mail_accounts(account_ids=[account_b.id])
        self.assertIn("No new", result)

    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_rule_with_stop_processing(self, m) -> None:
        """
        GIVEN:
            - Mail account with a rule with stop_processing=True
        WHEN:
            - Mail account is processed
        THEN:
            - Should only process the first rule
        """
        m.side_effect = lambda account: 6

        account = MailAccount.objects.create(
            name="A",
            imap_server="A",
            username="A",
            password="A",
        )
        MailRule.objects.create(
            name="A",
            account=account,
            stop_processing=True,
        )
        MailRule.objects.create(
            name="B",
            account=account,
        )

        result = tasks.process_mail_accounts()

        self.assertEqual(m.call_count, 1)
        self.assertIn("Added 6", result)


class TestMailAccountTestView(APITestCase):
    def setUp(self) -> None:
        self.mailMocker = MailMocker()
        self.mailMocker.setUp()
        self.addCleanup(self.mailMocker.doCleanups)
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword",
        )
        self.user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["add_mailaccount", "change_mailaccount"],
            ),
        )
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/mail_accounts/test/"

    def test_mail_account_test_view_success(self) -> None:
        data = {
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "secret",
            "account_type": MailAccount.MailAccountType.IMAP,
            "is_token": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True})

    def test_mail_account_test_view_mail_error(self) -> None:
        data = {
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "wrong",
            "account_type": MailAccount.MailAccountType.IMAP,
            "is_token": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.content.decode(), "Unable to connect to server")

    @override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
    @mock.patch("paperless_mail.mail.resolve_hostname_ips", return_value=["127.0.0.1"])
    def test_mail_account_test_view_blocks_internal_host_when_disabled(
        self,
        _mock_resolve_hostname_ips,
    ) -> None:
        data = {
            "imap_server": "internal.example",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "secret",
            "account_type": MailAccount.MailAccountType.IMAP,
            "is_token": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.content.decode(), "Unable to connect to server")

    @mock.patch(
        "paperless_mail.oauth.PaperlessMailOAuth2Manager.refresh_account_oauth_token",
    )
    def test_mail_account_test_view_refresh_token(
        self,
        mock_refresh_account_oauth_token,
    ) -> None:
        """
        GIVEN:
            - Mail account with expired token
        WHEN:
            - Mail account is tested
        THEN:
            - Should refresh the token
        """
        existing_account = MailAccount.objects.create(
            imap_server="imap.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            username="admin",
            password="secret",
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            refresh_token="oldtoken",
            expiration=timezone.now() - timedelta(days=1),
            is_token=True,
        )

        mock_refresh_account_oauth_token.return_value = True
        data = {
            "id": existing_account.id,
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "****",
            "is_token": True,
        }
        self.client.post(self.url, data, format="json")
        self.assertEqual(mock_refresh_account_oauth_token.call_count, 1)

    @mock.patch(
        "paperless_mail.oauth.PaperlessMailOAuth2Manager.refresh_account_oauth_token",
    )
    def test_mail_account_test_view_refresh_token_fails(
        self,
        mock_mock_refresh_account_oauth_token: mock.MagicMock,
    ) -> None:
        """
        GIVEN:
            - Mail account with expired token
        WHEN:
            - Mail account is tested
            - Token refresh fails
        THEN:
            - Should log an error
        """
        existing_account = MailAccount.objects.create(
            imap_server="imap.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            username="admin",
            password="secret",
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            refresh_token="oldtoken",
            expiration=timezone.now() - timedelta(days=1),
            is_token=True,
        )

        mock_mock_refresh_account_oauth_token.return_value = False
        data = {
            "id": existing_account.id,
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "****",
            "is_token": True,
        }
        with self.assertLogs("paperless_mail", level="ERROR") as cm:
            response = self.client.post(self.url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error_str = cm.output[0]
            expected_str = "Unable to refresh oauth token"
            self.assertIn(expected_str, error_str)

    def test_mail_account_test_view_existing_forbidden_for_other_owner(self) -> None:
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpassword",
        )
        existing_account = MailAccount.objects.create(
            name="Owned account",
            imap_server="imap.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            username="admin",
            password="secret",
            owner=other_user,
        )
        data = {
            "id": existing_account.id,
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "****",
            "is_token": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content.decode(), "Insufficient permissions")

    def test_mail_account_test_view_requires_add_permission_without_account_id(
        self,
    ) -> None:
        self.user.user_permissions.remove(
            *Permission.objects.filter(codename__in=["add_mailaccount"]),
        )
        self.user.save()
        data = {
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "username": "admin",
            "password": "secret",
            "is_token": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content.decode(), "Insufficient permissions")


class TestGetMailboxHostPinning(TestCase):
    """
    get_mailbox() must connect to the address it validated, so that a DNS answer
    which changes between the check and the connection (DNS rebinding) cannot
    redirect the connection to an internal host.
    """

    @override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
    @mock.patch(
        "paperless_mail.mail.resolve_hostname_ips",
        return_value=["93.184.216.34"],
    )
    def test_connects_to_validated_ip(self, _mock_resolve) -> None:
        with mock.patch(
            "paperless_mail.mail.socket.create_connection",
            side_effect=OSError("no connection in tests"),
        ) as mock_connection:
            with self.assertRaises(OSError):
                get_mailbox(
                    "mail.example.com",
                    143,
                    MailAccount.ImapSecurity.NONE,
                )

        # the hostname is never handed to the socket layer for a second lookup
        mock_connection.assert_called_once_with(("93.184.216.34", 143))

    @override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
    @mock.patch(
        "paperless_mail.mail.resolve_hostname_ips",
        return_value=["93.184.216.34"],
    )
    def test_ssl_pins_ip_but_keeps_hostname_for_sni(self, _mock_resolve) -> None:
        ssl_context = mock.MagicMock()
        ssl_context.wrap_socket.return_value.makefile.side_effect = OSError(
            "no connection in tests",
        )

        with (
            mock.patch(
                "paperless_mail.mail.ssl.create_default_context",
                return_value=ssl_context,
            ),
            mock.patch(
                "paperless_mail.mail.socket.create_connection",
            ) as mock_connection,
        ):
            with self.assertRaises(OSError):
                get_mailbox(
                    "mail.example.com",
                    993,
                    MailAccount.ImapSecurity.SSL,
                )

        mock_connection.assert_called_once_with(("93.184.216.34", 993))
        # certificate verification still happens against the hostname
        ssl_context.wrap_socket.assert_called_once_with(
            mock_connection.return_value,
            server_hostname="mail.example.com",
        )

    @override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
    @mock.patch(
        "paperless_mail.mail.resolve_hostname_ips",
        return_value=["93.184.216.34", "127.0.0.1"],
    )
    def test_blocks_when_any_resolved_address_is_internal(self, _mock_resolve) -> None:
        with self.assertRaises(MailError):
            get_mailbox("mail.example.com", 993, MailAccount.ImapSecurity.SSL)


class TestMailAccountProcess(APITestCase):
    def setUp(self) -> None:
        self.mailMocker = MailMocker()
        self.mailMocker.setUp()
        self.addCleanup(self.mailMocker.doCleanups)
        self.user = User.objects.create_superuser(
            username="testuser",
            password="testpassword",
        )
        self.client.force_authenticate(user=self.user)
        self.account = MailAccount.objects.create(
            imap_server="imap.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            username="admin",
            password="secret",
            account_type=MailAccount.MailAccountType.IMAP,
            owner=self.user,
        )
        self.url = f"/api/mail_accounts/{self.account.pk}/process/"

    @mock.patch("paperless_mail.tasks.process_mail_accounts.apply_async")
    def test_mail_account_process_view(self, m) -> None:
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()


class TestMailRuleAPI(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(
            username="testuser",
            password="testpassword",
        )
        self.client.force_authenticate(user=self.user)
        self.account = MailAccountFactory(owner=self.user)
        self.url = "/api/mail_rules/"

    def test_create_mail_rule(self) -> None:
        """
        GIVEN:
            - Valid data for creating a mail rule
        WHEN:
            - A POST request is made to the mail rules endpoint
        THEN:
            - The rule should be created successfully
            - The response should contain the created rule's details
        """
        data = {
            "name": "Test Rule",
            "account": self.account.pk,
            "action": MailRule.MailAction.MOVE,
            "action_parameter": "inbox",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MailRule.objects.count(), 1)
        rule = MailRule.objects.first()
        assert rule is not None
        self.assertEqual(rule.name, "Test Rule")

    def test_mail_rule_action_parameter_required_for_tag_or_move(self) -> None:
        """
        GIVEN:
            - Valid data for creating a mail rule without action_parameter
        WHEN:
            - A POST request is made to the mail rules endpoint
        THEN:
            - The request should fail with a 400 Bad Request status
            - The response should indicate that action_parameter is required
        """
        data = {
            "name": "Test Rule",
            "account": self.account.pk,
            "action": MailRule.MailAction.MOVE,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "action parameter is required",
            str(response.data["non_field_errors"]),
        )
