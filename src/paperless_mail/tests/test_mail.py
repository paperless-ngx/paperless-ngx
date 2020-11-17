from collections import namedtuple
from unittest import mock

from django.test import TestCase

from documents.models import Correspondent
from paperless_mail.mail import get_correspondent, get_title, handle_message
from paperless_mail.models import MailRule


class TestMail(TestCase):

    def test_get_correspondent(self):
        message = namedtuple('MailMessage', [])
        message.from_ = "someone@somewhere.com"
        message.from_values = {'name': "Someone!", 'email': "someone@somewhere.com"}

        message2 = namedtuple('MailMessage', [])
        message2.from_ = "me@localhost.com"
        message2.from_values = {'name': "", 'email': "fake@localhost.com"}

        me_localhost = Correspondent.objects.create(name=message2.from_)
        someone_else = Correspondent.objects.create(name="someone else")

        rule = MailRule(assign_correspondent_from=MailRule.CORRESPONDENT_FROM_NOTHING)
        self.assertIsNone(get_correspondent(message, rule))

        rule = MailRule(assign_correspondent_from=MailRule.CORRESPONDENT_FROM_EMAIL)
        c = get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "someone@somewhere.com")
        c = get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "me@localhost.com")
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(assign_correspondent_from=MailRule.CORRESPONDENT_FROM_NAME)
        c = get_correspondent(message, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "Someone!")
        c = get_correspondent(message2, rule)
        self.assertIsNotNone(c)
        self.assertEqual(c.id, me_localhost.id)

        rule = MailRule(assign_correspondent_from=MailRule.CORRESPONDENT_FROM_CUSTOM, assign_correspondent=someone_else)
        c = get_correspondent(message, rule)
        self.assertEqual(c, someone_else)

    def test_get_title(self):
        message = namedtuple('MailMessage', [])
        message.subject = "the message title"
        att = namedtuple('Attachment', [])
        att.filename = "this_is_the_file.pdf"
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME)
        self.assertEqual(get_title(message, att, rule), "this_is_the_file")
        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_SUBJECT)
        self.assertEqual(get_title(message, att, rule), "the message title")

    @mock.patch("paperless_mail.mail.async_task")
    def test_handle_message(self, m):
        message = namedtuple('MailMessage', [])
        message.subject = "the message title"

        att = namedtuple('Attachment', [])
        att.filename = "test1.pdf"
        att.content_type = 'application/pdf'
        att.payload = b"attachment contents"

        att2 = namedtuple('Attachment', [])
        att2.filename = "test2.pdf"
        att2.content_type = 'application/pdf'
        att2.payload = b"attachment contents"

        att3 = namedtuple('Attachment', [])
        att3.filename = "test3.pdf"
        att3.content_type = 'application/invalid'
        att3.payload = b"attachment contents"

        message.attachments = [att, att2, att3]

        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME)

        result = handle_message(message, rule)

        self.assertEqual(result, 2)

        self.assertEqual(len(m.call_args_list), 2)

        args1, kwargs1 = m.call_args_list[0]
        args2, kwargs2 = m.call_args_list[1]

        self.assertEqual(kwargs1['force_title'], "test1")
        self.assertEqual(kwargs1['original_filename'], "test1.pdf")

        self.assertEqual(kwargs2['force_title'], "test2")
        self.assertEqual(kwargs2['original_filename'], "test2.pdf")

    @mock.patch("paperless_mail.mail.async_task")
    def test_handle_empty_message(self, m):
        message = namedtuple('MailMessage', [])

        message.attachments = []
        rule = MailRule()

        result = handle_message(message, rule)

        self.assertFalse(m.called)
        self.assertEqual(result, 0)
