from email import message_from_bytes
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from filelock import FileLock


def send_email(
    subject: str,
    body: str,
    to: list[str],
    attachment: Path | None = None,
    attachment_mime_type: str | None = None,
) -> int:
    """
    Send an email with an optional attachment.
    TODO: re-evaluate this pending https://code.djangoproject.com/ticket/35581 / https://github.com/django/django/pull/18966
    """
    email = EmailMessage(
        subject=subject,
        body=body,
        to=to,
    )
    if attachment:
        # Something could be renaming the file concurrently so it can't be attached
        with FileLock(settings.MEDIA_LOCK), attachment.open("rb") as f:
            content = f.read()
            if attachment_mime_type == "message/rfc822":
                # See https://forum.djangoproject.com/t/using-emailmessage-with-an-attached-email-file-crashes-due-to-non-ascii/37981
                content = message_from_bytes(f.read())

            email.attach(
                filename=attachment.name,
                content=content,
                mimetype=attachment_mime_type,
            )
    return email.send()
