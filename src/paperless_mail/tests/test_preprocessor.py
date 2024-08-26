import email
import email.contentmanager
import tempfile
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from unittest import mock

import gnupg
from django.test import override_settings
from imap_tools import MailMessage

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.preprocessor import MailMessageDecryptor
from paperless_mail.tests.test_mail import TestMail
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

    @staticmethod
    def get_email_body_without_headers(email_message: Message) -> bytes:
        """
        Filters some relevant headers from an EmailMessage and returns just the body.
        """
        message_copy = email.message_from_bytes(email_message.as_bytes())

        message_copy._headers = [
            header
            for header in message_copy._headers
            if header[0].lower() not in ("from", "to", "subject")
        ]
        return message_copy.as_bytes()

    def encrypt(self, message):
        original_email: email.message.Message = message.obj
        encrypted_data = self.gpg.encrypt(
            self.get_email_body_without_headers(original_email),
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

        encrypted_message: MailMessage = MailMessage(
            [(f"UID {message.uid}".encode(), new_email.as_bytes())],
        )
        return encrypted_message


class TestMailMessageGpgDecryptor(TestMail):
    def setUp(self):
        self.messageEncryptor = MessageEncryptor()
        with override_settings(
            EMAIL_GNUPG_HOME=self.messageEncryptor.gpg_home,
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
        ):
            super().setUp()

    def test_preprocessor_is_able_to_run(self):
        with override_settings(
            EMAIL_GNUPG_HOME=self.messageEncryptor.gpg_home,
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
        ):
            self.assertTrue(MailMessageDecryptor.able_to_run())

    def test_preprocessor_is_able_to_run2(self):
        with override_settings(
            EMAIL_GNUPG_HOME=None,
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
        ):
            self.assertTrue(MailMessageDecryptor.able_to_run())

    def test_is_not_able_to_run_disabled(self):
        with override_settings(
            EMAIL_ENABLE_GPG_DECRYPTOR=False,
        ):
            self.assertFalse(MailMessageDecryptor.able_to_run())

    def test_is_not_able_to_run_bogus_path(self):
        with override_settings(
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
            EMAIL_GNUPG_HOME="_)@# notapath &%#$",
        ):
            self.assertFalse(MailMessageDecryptor.able_to_run())

    def test_fails_at_initialization(self):
        with (
            mock.patch("gnupg.GPG.__init__") as mock_run,
            override_settings(
                EMAIL_ENABLE_GPG_DECRYPTOR=True,
            ),
        ):

            def side_effect(*args, **kwargs):
                raise OSError("Cannot find 'gpg' binary")

            mock_run.side_effect = side_effect

            handler = MailAccountHandler()
            self.assertEqual(len(handler._message_preprocessors), 0)

    def test_decrypt_fails(self):
        encrypted_message, _ = self.create_encrypted_unencrypted_message_pair()
        empty_gpg_home = tempfile.mkdtemp()
        with override_settings(
            EMAIL_ENABLE_GPG_DECRYPTOR=True,
            EMAIL_GNUPG_HOME=empty_gpg_home,
        ):
            message_decryptor = MailMessageDecryptor()
            self.assertRaises(Exception, message_decryptor.run, encrypted_message)

    def test_decrypt_encrypted_mail(self):
        """
        Creates a mail with attachments. Then encrypts it with a new key.
        Verifies that this encrypted message can be decrypted with attachments intact.
        """
        encrypted_message, message = self.create_encrypted_unencrypted_message_pair()
        headers = message.headers
        text = message.text

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

    def create_encrypted_unencrypted_message_pair(self):
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
        encrypted_message = self.messageEncryptor.encrypt(message)
        return encrypted_message, message

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
