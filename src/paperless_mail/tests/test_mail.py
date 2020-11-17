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

    @mock.patch("django_q.tasks.async_task")
    def test_handle_message(self, m):
        message = namedtuple('MailMessage', [])
        message.subject = "the message title"
        att = namedtuple('Attachment', [])
        att.filename = "this_is_the_file.pdf"
        att.content_type = 'application/pdf'
        att.payload = b"attachment contents"
        message.attachments = [att]

        rule = MailRule(assign_title_from=MailRule.TITLE_FROM_FILENAME)

        #handle_message(message, rule)
