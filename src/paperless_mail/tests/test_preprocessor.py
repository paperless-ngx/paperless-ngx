import email.contentmanager
import random
import tempfile
import uuid
from collections import namedtuple
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from typing import Optional
from typing import Union
from unittest import mock

import gnupg
from django.test import override_settings
from imap_tools import EmailAddress
from imap_tools import MailMessage

from documents.models import Correspondent
from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.preprocessor import MailMessageDecryptor
from paperless_mail.tests.test_mail import BogusMailBox
from paperless_mail.tests.test_mail import _AttachmentDef


class MessageEncryptor:
    def __init__(self):
        self.gpg_home = tempfile.mkdtemp()
        self.gpg = gnupg.GPG(gnupghome=self.gpg_home)
        self._testUser = "testuser@example.com"
        # Generate a new key
        input_data = self.gpg.gen_key_input(
            name_email=self._testUser,
            passphrase=None,
            key_type="RSA",
            key_length=2048,
            expire_date=0,
            no_protection=True,
        )
        self.gpg.gen_key(input_data)

    def encrypt(self, message):
        original_email: email.message.Message = message.obj
        encrypted_data = self.gpg.encrypt(
            original_email.as_bytes(),
            self._testUser,
            armor=True,
        )
        if not encrypted_data.ok:
            raise Exception(f"Encryption failed: {encrypted_data.stderr}")
        encrypted_email_content = encrypted_data.data

        new_email = MIMEMultipart("encrypted", protocol="application/pgp-encrypted")
        new_email["From"] = original_email["From"]
        new_email["To"] = original_email["To"]
        new_email["Subject"] = original_email["Subject"]

        # Add the control part
        control_part = MIMEApplication(_data=b"", _subtype="pgp-encrypted")
        control_part.set_payload("Version: 1")
        new_email.attach(control_part)

        # Add the encrypted data part
        encrypted_part = MIMEApplication(_data=b"", _subtype="octet-stream")
        encrypted_part.set_payload(encrypted_email_content.decode("ascii"))
        encrypted_part.add_header(
            "Content-Disposition",
            'attachment; filename="encrypted.asc"',
        )
        new_email.attach(encrypted_part)

        encrypted_message = MailMessage(
            [(f"UID {message.uid}".encode(), new_email.as_bytes())],
        )
        return encrypted_message


class TestPreprocessor:
    def setUp(self):
        self.bogus_mailbox = BogusMailBox()

        patcher = mock.patch("paperless_mail.mail.MailBox")
        m = patcher.start()
        m.return_value = self.bogus_mailbox
        self.addCleanup(patcher.stop)

        patcher = mock.patch("paperless_mail.mail.queue_consumption_tasks")
        self._queue_consumption_tasks_mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.reset_bogus_mailbox()

        self.messageEncryptor = MessageEncryptor()
        with override_settings(
            EMAIL_GNUPG_HOME=self.messageEncryptor.gpg_home,
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
        ):
            self.mail_account_handler = MailAccountHandler()

        super().setUp()

    def create_message(
        self,
        attachments: Union[int, list[_AttachmentDef]] = 1,
        body: str = "",
        subject: str = "the subject",
        from_: str = "no_one@mail.com",
        to: Optional[list[str]] = None,
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
        uid = random.randint(1, 10000)
        while uid in self._used_uids:
            uid = random.randint(1, 10000)
        self._used_uids.add(uid)

        imap_msg._raw_uid_data = f"UID {uid}".encode()

        imap_msg.seen = seen
        imap_msg.flagged = flagged
        if processed:
            imap_msg._raw_flag_data.append(b"+FLAGS (processed)")
            MailMessage.flags.fget.cache_clear()

        return imap_msg

    def reset_bogus_mailbox(self):
        self.bogus_mailbox.messages = []
        self.bogus_mailbox.messages_spam = []
        self.bogus_mailbox.messages.append(
            self.create_message(
                subject="Invoice 1",
                from_="amazon@amazon.de",
                to=["me@myselfandi.com", "helpdesk@mydomain.com"],
                body="cables",
                seen=True,
                flagged=False,
                processed=False,
            ),
        )
        self.bogus_mailbox.messages.append(
            self.create_message(
                subject="Invoice 2",
                body="from my favorite electronic store",
                to=["invoices@mycompany.com"],
                seen=False,
                flagged=True,
                processed=True,
            ),
        )
        self.bogus_mailbox.messages.append(
            self.create_message(
                subject="Claim your $10M price now!",
                from_="amazon@amazon-some-indian-site.org",
                to="special@me.me",
                seen=False,
            ),
        )
        self.bogus_mailbox.updateClient()

    def test_get_correspondent(self):
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

        me_localhost = Correspondent.objects.create(name=message2.from_)
        someone_else = Correspondent.objects.create(name="someone else")

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

    def test_decrypt_encrypted_mail(self):
        """
        Creates a mail with attachments. Then encrypts it with a new key.
        Verifies that this encrypted message can be decrypted with attachments intact.
        """
        message = self.create_message(
            body="Test message with 2 attachments",
            attachments=[
                _AttachmentDef(
                    filename="f1.pdf",
                    disposition="inline",
                ),
                _AttachmentDef(filename="f2.pdf"),
            ],
        )
        headers = message.headers
        text = message.text
        encrypted_message = self.messageEncryptor.encrypt(message)

        self.assertEqual(len(encrypted_message.attachments), 1)
        self.assertEqual(encrypted_message.attachments[0].filename, "encrypted.asc")
        self.assertEqual(encrypted_message.text, "")

        with override_settings(
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
            EMAIL_GNUPG_HOME=self.messageEncryptor.gpg_home,
        ):
            message_decryptor = MailMessageDecryptor()
            self.assertTrue(message_decryptor.able_to_run())
            decrypted_message = message_decryptor.run(encrypted_message)

        self.assertEqual(len(decrypted_message.attachments), 2)
        self.assertEqual(decrypted_message.attachments[0].filename, "f1.pdf")
        self.assertEqual(decrypted_message.attachments[1].filename, "f2.pdf")
        self.assertEqual(decrypted_message.headers, headers)
        self.assertEqual(decrypted_message.text, text)
        self.assertEqual(decrypted_message.uid, message.uid)

    def test_handle_encrypted_message(self):
        message = self.create_message(
            subject="the message title",
            from_="Myself",
            attachments=2,
            body="Test mail",
        )

        encrypted_message = self.messageEncryptor.encrypt(message)

        account = MailAccount.objects.create()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            consumption_scope=MailRule.ConsumptionScope.EVERYTHING,
            account=account,
        )
        rule.save()

        result = self.mail_account_handler._handle_message(encrypted_message, rule)

        self.assertEqual(result, 3)

        self._queue_consumption_tasks_mock.assert_called()

        self.assert_queue_consumption_tasks_call_args(
            [
                [
                    {
                        "override_title": message.subject,
                        "override_filename": f"{message.subject}.eml",
                    },
                ],
                [
                    {"override_title": "file_0", "override_filename": "file_0.pdf"},
                    {"override_title": "file_1", "override_filename": "file_1.pdf"},
                ],
            ],
        )
