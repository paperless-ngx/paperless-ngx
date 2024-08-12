from email import message_from_bytes
from email import policy
from email.message import Message

from gnupg import GPG
from imap_tools import MailMessage

from documents.loggers import LoggingMixin


class MailMessageDecryptor(LoggingMixin):
    logging_name = "paperless_mail_message_decryptor"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.renew_logging_group()
        self._gpg = GPG(*args, **kwargs)

    def __call__(self, message: MailMessage) -> MailMessage:
        if not hasattr(message, "obj"):
            self.log.debug("Message does not have 'obj' attribute")
            return message
        if message.obj.get_content_type() != "multipart/encrypted":
            self.log.debug("Message not encrypted. Keep unchanged")
            return message

        self.log.debug("Message is encrypted.")
        email_message = self._to_email_message(message)
        decrypted_raw_message = self._gpg.decrypt(email_message.as_string())

        if not decrypted_raw_message.ok:
            self.log.debug(
                f"Message decryption failed with status message "
                f"{decrypted_raw_message.status}",
            )
            raise Exception(
                f"Decryption failed: {decrypted_raw_message.status}, {decrypted_raw_message.stderr}",
            )
        self.log.debug("Message decrypted successfully.")

        decrypted_message = self._build_decrypted_message(
            decrypted_raw_message,
            email_message,
        )

        return MailMessage(
            [(f"UID {message.uid}".encode(), decrypted_message.as_bytes())],
        )

    @staticmethod
    def _to_email_message(message: MailMessage) -> Message:
        email_message = message_from_bytes(
            message.obj.as_bytes(),
            policy=policy.default,
        )
        return email_message

    @staticmethod
    def _build_decrypted_message(decrypted_raw_message, email_message):
        decrypted_message = message_from_bytes(
            decrypted_raw_message.data,
            policy=policy.default,
        )
        for header, value in email_message.items():
            if not decrypted_message.get(header):
                decrypted_message.add_header(header, value)
        return decrypted_message
