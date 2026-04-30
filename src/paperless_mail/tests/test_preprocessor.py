import email
import email.contentmanager
import subprocess
from collections.abc import Generator
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import gnupg
import pytest
from imap_tools import MailMessage

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailRule
from paperless_mail.preprocessor import MailMessageDecryptor
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.test_mail import _AttachmentDef


class MessageEncryptor:
    """
    Test helper: generates a throwaway GPG keypair in a tempdir and exposes
    `encrypt(MailMessage) -> MailMessage`.
    """

    def __init__(self, gpg_home: Path) -> None:
        self.gpg_home = str(gpg_home)
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

    def kill_agent(self) -> None:
        """
        Kill the gpg-agent so pytest can remove the GPG home.

        This uses gpgconf to properly terminate the agent, which is the officially
        recommended cleanup method from the GnuPG project. python-gnupg does not
        provide built-in cleanup methods as it's only a wrapper around the gpg CLI.
        """
        # Kill the gpg-agent using the official GnuPG cleanup tool
        try:
            subprocess.run(
                ["gpgconf", "--kill", "gpg-agent"],
                env={"GNUPGHOME": self.gpg_home},
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # gpgconf not found or hung - agent will timeout eventually
            pass

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

    def encrypt(self, message) -> MailMessage:
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

        return MailMessage(
            [(f"UID {message.uid}".encode(), new_email.as_bytes())],
        )


@pytest.fixture(scope="session")
def message_encryptor(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[MessageEncryptor, None, None]:
    """
    Session-scoped: GPG keypair generation is slow (~1s+), and nothing in
    these tests mutates the keyring after creation. The GPG home directory
    comes from `tmp_path_factory` so pytest cleans it up at session end;
    we still kill the gpg-agent ourselves so the dir is removable.
    """
    gpg_home = tmp_path_factory.mktemp("gpg-home")
    encryptor = MessageEncryptor(gpg_home)
    yield encryptor
    encryptor.kill_agent()


@pytest.fixture()
def gpg_settings(settings, message_encryptor: MessageEncryptor):
    settings.EMAIL_GNUPG_HOME = message_encryptor.gpg_home
    settings.EMAIL_ENABLE_GPG_DECRYPTOR = True
    return settings


@pytest.fixture()
def encrypted_pair(mail_mocker, message_encryptor: MessageEncryptor):
    """
    Build a (encrypted, plaintext) MailMessage pair sharing the same UID and
    headers, with two PDF attachments on the plaintext side.
    """
    plaintext = mail_mocker.messageBuilder.create_message(
        body="Test message with 2 attachments",
        attachments=[
            _AttachmentDef(filename="f1.pdf", disposition="inline"),
            _AttachmentDef(filename="f2.pdf"),
        ],
    )
    encrypted = message_encryptor.encrypt(plaintext)
    return encrypted, plaintext


class TestMailMessageDecryptorAbleToRun:
    """`MailMessageDecryptor.able_to_run()` configuration matrix — no DB needed."""

    @pytest.mark.parametrize(
        ("settings_overrides", "expected"),
        [
            pytest.param(
                {
                    "EMAIL_GNUPG_HOME": "_gpg_home_marker",
                    "EMAIL_ENABLE_GPG_DECRYPTOR": True,
                },
                True,
                id="enabled-with-valid-home",
            ),
            pytest.param(
                {"EMAIL_GNUPG_HOME": None, "EMAIL_ENABLE_GPG_DECRYPTOR": True},
                True,
                id="enabled-with-default-home",
            ),
            pytest.param(
                {"EMAIL_ENABLE_GPG_DECRYPTOR": False},
                False,
                id="disabled",
            ),
            pytest.param(
                {
                    "EMAIL_ENABLE_GPG_DECRYPTOR": True,
                    "EMAIL_GNUPG_HOME": "_)@# notapath &%#$",
                },
                False,
                id="enabled-with-bogus-path",
            ),
        ],
    )
    def test_able_to_run(
        self,
        settings,
        message_encryptor: MessageEncryptor,
        settings_overrides: dict,
        *,
        expected: bool,
    ) -> None:
        for key, value in settings_overrides.items():
            if value == "_gpg_home_marker":
                value = message_encryptor.gpg_home
            setattr(settings, key, value)
        assert MailMessageDecryptor.able_to_run() is expected


@pytest.mark.django_db
class TestMailMessageDecryptor:
    """End-to-end decrypt and consumption flow with a real GPG keyring."""

    def test_fails_at_initialization(self, settings, mocker) -> None:
        settings.EMAIL_ENABLE_GPG_DECRYPTOR = True
        mocker.patch(
            "gnupg.GPG.__init__",
            side_effect=OSError("Cannot find 'gpg' binary"),
        )

        handler = MailAccountHandler()

        assert len(handler._message_preprocessors) == 0

    def test_decrypt_fails(self, settings, encrypted_pair, tmp_path: Path) -> None:
        """
        A decryptor pointed at a fresh empty GPG home cannot decrypt the
        message — ensure it surfaces an exception rather than silently passing
        bytes through.
        """
        encrypted_message, _ = encrypted_pair
        empty_gpg_home = tmp_path / "empty-gpg-home"
        empty_gpg_home.mkdir()

        settings.EMAIL_ENABLE_GPG_DECRYPTOR = True
        settings.EMAIL_GNUPG_HOME = str(empty_gpg_home)

        decryptor = MailMessageDecryptor()
        try:
            with pytest.raises(Exception):
                decryptor.run(encrypted_message)
        finally:
            try:
                subprocess.run(
                    ["gpgconf", "--kill", "gpg-agent"],
                    env={"GNUPGHOME": str(empty_gpg_home)},
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    def test_decrypt_encrypted_mail(self, gpg_settings, encrypted_pair) -> None:
        """
        Creates a mail with attachments. Then encrypts it with a new key.
        Verifies that this encrypted message can be decrypted with attachments intact.
        """
        encrypted_message, plaintext = encrypted_pair
        headers = plaintext.headers
        text = plaintext.text

        assert len(encrypted_message.attachments) == 1
        assert encrypted_message.attachments[0].filename == "encrypted.asc"
        assert encrypted_message.text == ""

        decryptor = MailMessageDecryptor()
        assert decryptor.able_to_run()
        decrypted = decryptor.run(encrypted_message)

        assert len(decrypted.attachments) == 2
        assert decrypted.attachments[0].filename == "f1.pdf"
        assert decrypted.attachments[1].filename == "f2.pdf"
        assert decrypted.headers == headers
        assert decrypted.text == text
        assert decrypted.uid == plaintext.uid

    def test_handle_encrypted_message(
        self,
        gpg_settings,
        mail_mocker,
        message_encryptor: MessageEncryptor,
    ) -> None:
        plaintext = mail_mocker.messageBuilder.create_message(
            subject="the message title",
            from_="Myself",
            attachments=2,
            body="Test mail",
        )
        encrypted = message_encryptor.encrypt(plaintext)

        account = MailAccountFactory()
        rule = MailRule(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            consumption_scope=MailRule.ConsumptionScope.EVERYTHING,
            account=account,
        )
        rule.save()

        handler = MailAccountHandler()
        result = handler._handle_message(encrypted, rule)

        assert result == 3
        mail_mocker._queue_consumption_tasks_mock.assert_called()
        mail_mocker.assert_queue_consumption_tasks_call_args(
            [
                [
                    {
                        "override_title": plaintext.subject,
                        "override_filename": f"{plaintext.subject}.eml",
                    },
                ],
                [
                    {"override_title": "file_0", "override_filename": "file_0.pdf"},
                    {"override_title": "file_1", "override_filename": "file_1.pdf"},
                ],
            ],
        )
