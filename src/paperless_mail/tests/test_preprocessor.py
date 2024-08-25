import tempfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from typing import TYPE_CHECKING

import gnupg
from django.test import TestCase
from django.test import override_settings
from imap_tools import MailMessage

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.preprocessor import MailMessageDecryptor
from paperless_mail.tests.test_mail import MailMocker
from paperless_mail.tests.test_mail import _AttachmentDef

if TYPE_CHECKING:
    import email.contentmanager


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


class TestPreprocessor(TestCase):
    def setUp(self):
        self.mailMocker = MailMocker()
        self.mailMocker.setUp()

        self.messageEncryptor = MessageEncryptor()
        with override_settings(
            EMAIL_GNUPG_HOME=self.messageEncryptor.gpg_home,
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
        ):
            self.mail_account_handler = MailAccountHandler()

        super().setUp()

    def test_decrypt_encrypted_mail(self):
        """
        Creates a mail with attachments. Then encrypts it with a new key.
        Verifies that this encrypted message can be decrypted with attachments intact.
        """
        message = self.mailMocker.messageBuilder.create_message(
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
        message = self.mailMocker.messageBuilder.create_message(
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

        self.mailMocker._queue_consumption_tasks_mock.assert_called()

        self.mailMocker.assert_queue_consumption_tasks_call_args(
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
