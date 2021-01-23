import os
import uuid
from collections import namedtuple
from typing import ContextManager
from unittest import mock

from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from imap_tools import MailMessageFlags, MailboxFolderSelectError

from documents.models import Correspondent
from documents.tests.utils import DirectoriesMixin
from paperless_mail import tasks
from paperless_mail.mail import MailError, MailAccountHandler
from paperless_mail.models import MailRule, MailAccount


class BogusFolderManager:

    current_folder = "INBOX"

    def set(self, new_folder):
        if new_folder not in ["INBOX", "spam"]:
            raise MailboxFolderSelectError(None, "uhm")
        self.current_folder = new_folder


class BogusMailBox(ContextManager):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self):
        self.messages = []
        self.messages_spam = []

    def login(self, username, password):
        if not (username == 'admin' and password == 'secret'):
            raise Exception()

    folder = BogusFolderManager()

    def fetch(self, criteria, mark_seen, charset=""):
        msg = self.messages

        criteria = str(criteria).strip('()').split(" ")

        if 'UNSEEN' in criteria:
            msg = filter(lambda m: not m.seen, msg)

        if 'SUBJECT' in criteria:
            subject = criteria[criteria.index('SUBJECT') + 1].strip('"')
            msg = filter(lambda m: subject in m.subject, msg)

        if 'BODY' in criteria:
            body = criteria[criteria.index('BODY') + 1].strip('"')
            msg = filter(lambda m: body in m.body, msg)

        if 'FROM' in criteria:
            from_ = criteria[criteria.index('FROM') + 1].strip('"')
            msg = filter(lambda m: from_ in m.from_, msg)

        if 'UNFLAGGED' in criteria:
            msg = filter(lambda m: not m.flagged, msg)

        return list(msg)

    def seen(self, uid_list, seen_val):
        for message in self.messages:
            if message.uid in uid_list:
                message.seen = seen_val

    def delete(self, uid_list):
        self.messages = list(filter(lambda m: m.uid not in uid_list, self.messages))

    def flag(self, uid_list, flag_set, value):
        for message in self.messages:
            if message.uid in uid_list:
                for flag in flag_set:
                    if flag == MailMessageFlags.FLAGGED:
                        message.flagged = value

    def move(self, uid_list, folder):
        if folder == "spam":
            self.messages_spam.append(
                filter(lambda m: m.uid in uid_list, self.messages)
            )
            self.messages = list(
                filter(lambda m: m.uid not in uid_list, self.messages)
            )
        else:
            raise Exception()


def create_message(num_attachments=1, body="", subject="the suject", from_="noone@mail.com", seen=False, flagged=False):
    message = namedtuple('MailMessage', [])

    message.uid = uuid.uuid4()
    message.subject = subject
    message.attachments = []
    message.from_ = from_
    message.body = body
    for i in range(num_attachments):
        message.attachments.append(create_attachment(filename=f"file_{i}.pdf"))

    message.seen = seen
    message.flagged = flagged

    return message


def create_attachment(filename="the_file.pdf", content_disposition="attachment", payload=b"a PDF document"):
    attachment = namedtuple('Attachment', [])
    attachment.filename = filename
    attachment.content_disposition = content_disposition
    attachment.payload = payload
    return attachment


def fake_magic_from_buffer(buffer, mime=False):

    if mime:
        if 'PDF' in str(buffer):
            return 'application/pdf'
        else:
            return 'unknown/type'
    else:
        return 'Some verbose file description'


@mock.patch('paperless_mail.mail.magic.from_buffer', fake_magic_from_buffer)
class TestMail(DirectoriesMixin, TestCase):

    def setUp(self):
        patcher = mock.patch('paperless_mail.mail.MailBox')
        m = patcher.start()
        self.bogus_mailbox = BogusMailBox()
        m.return_value = self.bogus_mailbox
        self.addCleanup(patcher.stop)

        patcher = mock.patch('paperless_mail.mail.async_task')
        self.async_task = patcher.start()
        self.addCleanup(patcher.stop)

        self.reset_bogus_mailbox()

        self.mail_account_handler = MailAccountHandler()
        super(TestMail, self).setUp()

    def reset_bogus_mailbox(self):
        self.bogus_mailbox.messages = []
        self.bogus_mailbox.messages_spam = []
        self.bogus_mailbox.messages.append(create_message(subject="Invoice 1", from_="amazon@amazon.de", body="cables", seen=True, flagged=False))
        self.bogus_mailbox.messages.append(create_message(subject="Invoice 2", body="from my favorite electronic store", seen=False, flagged=True))
        self.bogus_mailbox.messages.append(create_message(subject="Claim your $10M price now!", from_="amazon@amazon-some-indian-site.org", seen=False))

    def test_get_correspondent(self):
        message = namedtuple('MailMessage', [])
        message.from_ = "someone@somewhere.com"
        message.from_values = {'name': "Someone!", 'email': "someone@somewhere.com"}

        message2 = namedtuple('MailMessage', [])
        message2.from_ = "me@localhost.com"
        message2.from_values = {'name': "", 'email': "fake@localhost.com"}

        me_localhost = Correspondent.objects.create(name=message2.from_)
        someone_else = Correspondent.objects.create(name="someone else")

        handler = MailAccountHandler()

        rule = MailRule(name="a", assign_correspondent_from=MailRule.CORRESPONDENT_FROM_NOTHING)
        self.assertIsNone(handler.get_correspondent(message, rule))

        rule = MailRule(name="b", assign_correspondent_from=MailRule.CORRESPONDENT_FROM_EMAIL)
        c = handler.get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "someone@somewhere.com")
        c = handler.get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "me@localhost.com")
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(name="c", assign_correspondent_from=MailRule.CORRESPONDENT_FROM_NAME)
        c = handler.get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "Someone!")
        c = handler.get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(name="d", assign_correspondent_from=MailRule.CORRESPONDENT_FROM_CUSTOM, assign_correspondent=someone_else)
        c = handler.get_correspondent(message, rule)
        self.assertEqual(c, someone_else)

    def test_get_title(self):
        message = namedtuple('MailMessage', [])
        message.subject = "the message title"
        att = namedtuple('Attachment', [])
        att.filename = "this_is_the_file.pdf"

        handler = MailAccountHandler()

        rule = MailRule(name="a", assign_title_from=MailRule.TITLE_FROM_FILENAME)
        self.assertEqual(handler.get_title(message, att, rule), "this_is_the_file")
        rule = MailRule(name="b", assign_title_from=MailRule.TITLE_FROM_SUBJECT)
        self.assertEqual(handler.get_title(message, att, rule), "the message title")

    def test_handle_message(self):
        message = create_message(subject="the message title", from_="Myself", num_attachments=2)

        account = MailAccount()
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME, account=account)

        result = self.mail_account_handler.handle_message(message, rule)

        self.assertEqual(result, 2)

        self.assertEqual(len(self.async_task.call_args_list), 2)

        args1, kwargs1 = self.async_task.call_args_list[0]
        args2, kwargs2 = self.async_task.call_args_list[1]

        self.assertTrue(os.path.isfile(kwargs1['path']), kwargs1['path'])

        self.assertEqual(kwargs1['override_title'], "file_0")
        self.assertEqual(kwargs1['override_filename'], "file_0.pdf")

        self.assertTrue(os.path.isfile(kwargs2['path']), kwargs1['path'])

        self.assertEqual(kwargs2['override_title'], "file_1")
        self.assertEqual(kwargs2['override_filename'], "file_1.pdf")

    def test_handle_empty_message(self):
        message = namedtuple('MailMessage', [])

        message.attachments = []
        rule = MailRule()

        result = self.mail_account_handler.handle_message(message, rule)

        self.assertFalse(self.async_task.called)
        self.assertEqual(result, 0)

    def test_handle_unknown_mime_type(self):
        message = create_message()
        message.attachments = [
            create_attachment(filename="f1.pdf"),
            create_attachment(filename="f2.json", payload=b"{'much': 'payload.', 'so': 'json', 'wow': true}")
        ]

        account = MailAccount()
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME, account=account)

        result = self.mail_account_handler.handle_message(message, rule)

        self.assertEqual(result, 1)
        self.assertEqual(self.async_task.call_count, 1)

        args, kwargs = self.async_task.call_args
        self.assertTrue(os.path.isfile(kwargs['path']), kwargs['path'])
        self.assertEqual(kwargs['override_filename'], "f1.pdf")

    def test_handle_disposition(self):
        message = create_message()
        message.attachments = [
            create_attachment(filename="f1.pdf", content_disposition='inline'),
            create_attachment(filename="f2.pdf", content_disposition='attachment')
        ]

        account = MailAccount()
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME, account=account)

        result = self.mail_account_handler.handle_message(message, rule)

        self.assertEqual(result, 1)
        self.assertEqual(self.async_task.call_count, 1)

        args, kwargs = self.async_task.call_args
        self.assertEqual(kwargs['override_filename'], "f2.pdf")

    def test_handle_inline_files(self):
        message = create_message()
        message.attachments = [
            create_attachment(filename="f1.pdf", content_disposition='inline'),
            create_attachment(filename="f2.pdf", content_disposition='attachment')
        ]

        account = MailAccount()
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME, account=account, attachment_type=MailRule.ATTACHMENT_TYPE_EVERYTHING)

        result = self.mail_account_handler.handle_message(message, rule)

        self.assertEqual(result, 2)
        self.assertEqual(self.async_task.call_count, 2)

    def test_filename_filter(self):
        message = create_message()
        message.attachments = [
            create_attachment(filename="f1.pdf"),
            create_attachment(filename="f2.pdf"),
            create_attachment(filename="f3.pdf"),
            create_attachment(filename="f2.png"),
        ]

        tests = [
            ("*.pdf", ["f1.pdf", "f2.pdf", "f3.pdf"]),
            ("f1.pdf", ["f1.pdf"]),
            ("f1", []),
            ("*", ["f1.pdf", "f2.pdf", "f3.pdf", "f2.png"]),
            ("*.png", ["f2.png"]),
        ]

        for (pattern, matches) in tests:
            self.async_task.reset_mock()
            account = MailAccount()
            rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME, account=account, filter_attachment_filename=pattern)

            result = self.mail_account_handler.handle_message(message, rule)

            self.assertEqual(result, len(matches))
            filenames = [a[1]['override_filename'] for a in self.async_task.call_args_list]
            self.assertCountEqual(filenames, matches)

    def test_handle_mail_account_mark_read(self):

        account = MailAccount.objects.create(name="test", imap_server="", username="admin", password="secret")

        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_MARK_READ)

        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.assertEqual(self.async_task.call_count, 0)
        self.assertEqual(len(self.bogus_mailbox.fetch("UNSEEN", False)), 2)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(self.async_task.call_count, 2)
        self.assertEqual(len(self.bogus_mailbox.fetch("UNSEEN", False)), 0)
        self.assertEqual(len(self.bogus_mailbox.messages), 3)

    def test_handle_mail_account_delete(self):

        account = MailAccount.objects.create(name="test", imap_server="", username="admin", password="secret")

        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_DELETE, filter_subject="Invoice")

        self.assertEqual(self.async_task.call_count, 0)
        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(self.async_task.call_count, 2)
        self.assertEqual(len(self.bogus_mailbox.messages), 1)

    def test_handle_mail_account_flag(self):
        account = MailAccount.objects.create(name="test", imap_server="", username="admin", password="secret")

        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_FLAG, filter_subject="Invoice")

        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.assertEqual(self.async_task.call_count, 0)
        self.assertEqual(len(self.bogus_mailbox.fetch("UNFLAGGED", False)), 2)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(self.async_task.call_count, 1)
        self.assertEqual(len(self.bogus_mailbox.fetch("UNFLAGGED", False)), 1)
        self.assertEqual(len(self.bogus_mailbox.messages), 3)

    def test_handle_mail_account_move(self):
        account = MailAccount.objects.create(name="test", imap_server="", username="admin", password="secret")

        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_MOVE, action_parameter="spam", filter_subject="Claim")

        self.assertEqual(self.async_task.call_count, 0)
        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.assertEqual(len(self.bogus_mailbox.messages_spam), 0)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(self.async_task.call_count, 1)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.bogus_mailbox.messages_spam), 1)

    def test_error_login(self):
        account = MailAccount.objects.create(name="test", imap_server="", username="admin", password="wrong")

        try:
            self.mail_account_handler.handle_mail_account(account)
        except MailError as e:
            self.assertTrue(str(e).startswith("Error while authenticating account"))
        else:
            self.fail("Should raise exception")

    def test_error_skip_account(self):
        account_faulty = MailAccount.objects.create(name="test", imap_server="", username="admin", password="wroasdng")

        account = MailAccount.objects.create(name="test2", imap_server="", username="admin", password="secret")
        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_MOVE,
                                       action_parameter="spam", filter_subject="Claim")

        tasks.process_mail_accounts()
        self.assertEqual(self.async_task.call_count, 1)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.bogus_mailbox.messages_spam), 1)

    def test_error_skip_rule(self):

        account = MailAccount.objects.create(name="test2", imap_server="", username="admin", password="secret")
        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_MOVE,
                                       action_parameter="spam", filter_subject="Claim", order=1, folder="uuuhhhh")
        rule2 = MailRule.objects.create(name="testrule2", account=account, action=MailRule.ACTION_MOVE,
                                       action_parameter="spam", filter_subject="Claim", order=2)

        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(self.async_task.call_count, 1)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(len(self.bogus_mailbox.messages_spam), 1)


    @mock.patch("paperless_mail.mail.MailAccountHandler.get_correspondent")
    def test_error_skip_mail(self, m):

        def get_correspondent_fake(message, rule):
            if message.from_ == 'amazon@amazon.de':
                raise ValueError("Does not compute.")
            else:
                return None

        m.side_effect = get_correspondent_fake

        account = MailAccount.objects.create(name="test2", imap_server="", username="admin", password="secret")
        rule = MailRule.objects.create(name="testrule", account=account, action=MailRule.ACTION_MOVE, action_parameter="spam")

        self.mail_account_handler.handle_mail_account(account)

        # test that we still consume mail even if some mails throw errors.
        self.assertEqual(self.async_task.call_count, 2)

        # faulty mail still in inbox, untouched
        self.assertEqual(len(self.bogus_mailbox.messages), 1)
        self.assertEqual(self.bogus_mailbox.messages[0].from_, 'amazon@amazon.de')

    def test_error_create_correspondent(self):

        account = MailAccount.objects.create(name="test2", imap_server="", username="admin", password="secret")
        rule = MailRule.objects.create(
            name="testrule", filter_from="amazon@amazon.de",
            account=account, action=MailRule.ACTION_MOVE, action_parameter="spam",
            assign_correspondent_from=MailRule.CORRESPONDENT_FROM_EMAIL)

        self.mail_account_handler.handle_mail_account(account)

        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args

        c = Correspondent.objects.get(name="amazon@amazon.de")
        # should work
        self.assertEqual(kwargs['override_correspondent_id'], c.id)

        self.async_task.reset_mock()
        self.reset_bogus_mailbox()

        with mock.patch("paperless_mail.mail.Correspondent.objects.get_or_create") as m:
            m.side_effect = DatabaseError()

            self.mail_account_handler.handle_mail_account(account)

        args, kwargs = self.async_task.call_args
        self.async_task.assert_called_once()
        self.assertEqual(kwargs['override_correspondent_id'], None)


    def test_filters(self):

        account = MailAccount.objects.create(name="test3", imap_server="", username="admin", password="secret")
        rule = MailRule.objects.create(name="testrule3", account=account, action=MailRule.ACTION_DELETE, filter_subject="Claim")

        self.assertEqual(self.async_task.call_count, 0)

        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(self.async_task.call_count, 1)

        self.reset_bogus_mailbox()

        rule.filter_subject = None
        rule.filter_body = "electronic"
        rule.save()
        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(self.async_task.call_count, 2)

        self.reset_bogus_mailbox()

        rule.filter_from = "amazon"
        rule.filter_body = None
        rule.save()
        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(len(self.bogus_mailbox.messages), 1)
        self.assertEqual(self.async_task.call_count, 4)

        self.reset_bogus_mailbox()

        rule.filter_from = "amazon"
        rule.filter_body = "cables"
        rule.filter_subject = "Invoice"
        rule.save()
        self.assertEqual(len(self.bogus_mailbox.messages), 3)
        self.mail_account_handler.handle_mail_account(account)
        self.assertEqual(len(self.bogus_mailbox.messages), 2)
        self.assertEqual(self.async_task.call_count, 5)

class TestManagementCommand(TestCase):

    @mock.patch("paperless_mail.management.commands.mail_fetcher.tasks.process_mail_accounts")
    def test_mail_fetcher(self, m):

        call_command("mail_fetcher")

        m.assert_called_once()

class TestTasks(TestCase):

    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_all_accounts(self, m):
        m.side_effect = lambda account: 6

        MailAccount.objects.create(name="A", imap_server="A", username="A", password="A")
        MailAccount.objects.create(name="B", imap_server="A", username="A", password="A")

        result = tasks.process_mail_accounts()

        self.assertEqual(m.call_count, 2)
        self.assertIn("Added 12", result)

        m.side_effect = lambda account: 0
        result = tasks.process_mail_accounts()
        self.assertIn("No new", result)

    @mock.patch("paperless_mail.tasks.MailAccountHandler.handle_mail_account")
    def test_single_accounts(self, m):

        MailAccount.objects.create(name="A", imap_server="A", username="A", password="A")

        tasks.process_mail_account("A")

        m.assert_called_once()
        m.reset_mock()

        tasks.process_mail_account("B")
        m.assert_not_called()
