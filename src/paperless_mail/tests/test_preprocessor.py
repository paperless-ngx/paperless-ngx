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
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailRule
from paperless_mail.preprocessor import MailMessageDecryptor
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.test_mail import MailMocker
from paperless_mail.tests.test_mail import _AttachmentDef


def _kill_gpg_agent(gpg_home: str) -> None:
    """
    Terminate any gpg-agent attached to `gpg_home` so the directory is
    removable. Uses `gpgconf --kill`, the GnuPG project's recommended cleanup
    path; python-gnupg has no built-in cleanup since it only wraps the CLI.
    """
    try:
        subprocess.run(
            ["gpgconf", "--kill", "gpg-agent"],
            env={"GNUPGHOME": gpg_home},
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


class MessageEncryptor:
    """
    Test helper: generates a throwaway GPG keypair in a tempdir and exposes
    `encrypt(MailMessage) -> MailMessage`.
    """

    TEST_USER = "testuser@example.com"

    def __init__(self, gpg_home: Path) -> None:
        self.gpg_home = str(gpg_home)
        self.gpg = gnupg.GPG(gnupghome=self.gpg_home)
        self.gpg.gen_key(
            self.gpg.gen_key_input(
                name_email=self.TEST_USER,
                passphrase=None,
                key_type="RSA",
                key_length=2048,
                expire_date=0,
                no_protection=True,
            ),
        )

    def kill_agent(self) -> None:
        _kill_gpg_agent(self.gpg_home)

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

    def encrypt(self, message: MailMessage) -> MailMessage:
        original_email: Message = message.obj
        encrypted_data = self.gpg.encrypt(
            self.get_email_body_without_headers(original_email),
            self.TEST_USER,
            armor=True,
        )
        if not encrypted_data.ok:
            raise Exception(f"Encryption failed: {encrypted_data.stderr}")

        new_email = MIMEMultipart("encrypted", protocol="application/pgp-encrypted")
        new_email["From"] = original_email["From"]
        new_email["To"] = original_email["To"]
        new_email["Subject"] = original_email["Subject"]

        control_part = MIMEApplication(_data=b"", _subtype="pgp-encrypted")
        control_part.set_payload("Version: 1")
        new_email.attach(control_part)

        encrypted_part = MIMEApplication(_data=b"", _subtype="octet-stream")
        encrypted_part.set_payload(encrypted_data.data.decode("ascii"))
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
    encryptor = MessageEncryptor(tmp_path_factory.mktemp("gpg-home"))
    yield encryptor
    encryptor.kill_agent()


@pytest.fixture
def gpg_settings(
    settings: SettingsWrapper,
    message_encryptor: MessageEncryptor,
) -> SettingsWrapper:
    settings.EMAIL_GNUPG_HOME = message_encryptor.gpg_home
    settings.EMAIL_ENABLE_GPG_DECRYPTOR = True
    return settings


@pytest.fixture
def encrypted_pair(
    mail_mocker: MailMocker,
    message_encryptor: MessageEncryptor,
) -> tuple[MailMessage, MailMessage]:
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
    return message_encryptor.encrypt(plaintext), plaintext


# Sentinel used in `test_able_to_run` parametrization to request the real
# GPG home from the session-scoped `message_encryptor` fixture at runtime.
_VALID_GPG_HOME = object()


class TestMailMessageDecryptorAbleToRun:
    """`MailMessageDecryptor.able_to_run()` configuration matrix."""

    @pytest.mark.parametrize(
        ("settings_overrides", "expected"),
        [
            pytest.param(
                {
                    "EMAIL_GNUPG_HOME": _VALID_GPG_HOME,
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
        settings: SettingsWrapper,
        message_encryptor: MessageEncryptor,
        settings_overrides: dict,
        *,
        expected: bool,
    ) -> None:
        for key, value in settings_overrides.items():
            if value is _VALID_GPG_HOME:
                value = message_encryptor.gpg_home
            setattr(settings, key, value)
        assert MailMessageDecryptor.able_to_run() is expected


@pytest.mark.django_db
class TestMailMessageDecryptor:
    """End-to-end decrypt and consumption flow with a real GPG keyring."""

    def test_fails_at_initialization(
        self,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        settings.EMAIL_ENABLE_GPG_DECRYPTOR = True
        mocker.patch(
            "gnupg.GPG.__init__",
            side_effect=OSError("Cannot find 'gpg' binary"),
        )

        handler = MailAccountHandler()

        assert len(handler._message_preprocessors) == 0

    def test_decrypt_fails(
        self,
        settings: SettingsWrapper,
        encrypted_pair: tuple[MailMessage, MailMessage],
        tmp_path: Path,
    ) -> None:
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

        try:
            with pytest.raises(Exception):
                MailMessageDecryptor().run(encrypted_message)
        finally:
            _kill_gpg_agent(str(empty_gpg_home))

    def test_decrypt_encrypted_mail(
        self,
        gpg_settings: SettingsWrapper,
        encrypted_pair: tuple[MailMessage, MailMessage],
    ) -> None:
        """
        Creates a mail with attachments. Then encrypts it with a new key.
        Verifies that this encrypted message can be decrypted with attachments intact.
        """
        encrypted_message, plaintext = encrypted_pair

        assert len(encrypted_message.attachments) == 1
        assert encrypted_message.attachments[0].filename == "encrypted.asc"
        assert encrypted_message.text == ""

        decryptor = MailMessageDecryptor()
        assert decryptor.able_to_run()
        decrypted = decryptor.run(encrypted_message)

        assert len(decrypted.attachments) == 2
        assert decrypted.attachments[0].filename == "f1.pdf"
        assert decrypted.attachments[1].filename == "f2.pdf"
        assert decrypted.headers == plaintext.headers
        assert decrypted.text == plaintext.text
        assert decrypted.uid == plaintext.uid

    def test_handle_encrypted_message(
        self,
        gpg_settings: SettingsWrapper,
        mail_mocker: MailMocker,
        message_encryptor: MessageEncryptor,
    ) -> None:
        plaintext = mail_mocker.messageBuilder.create_message(
            subject="the message title",
            from_="Myself",
            attachments=2,
            body="Test mail",
        )
        encrypted = message_encryptor.encrypt(plaintext)

        rule = MailRule.objects.create(
            assign_title_from=MailRule.TitleSource.FROM_FILENAME,
            consumption_scope=MailRule.ConsumptionScope.EVERYTHING,
            account=MailAccountFactory(),
        )

        result = MailAccountHandler()._handle_message(encrypted, rule)

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
