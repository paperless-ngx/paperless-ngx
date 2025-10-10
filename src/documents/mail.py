from email import message_from_bytes
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from filelock import FileLock


def send_email(
    subject: str,
    body: str,
    to: list[str],
    attachments: list[tuple[Path, str]],
) -> int:
    """
    Send an email with attachments.

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of (path, mime_type) tuples for attachments (the list may be empty)

    Returns:
        Number of emails sent

    TODO: re-evaluate this pending https://code.djangoproject.com/ticket/35581 / https://github.com/django/django/pull/18966
    """
    email = EmailMessage(
        subject=subject,
        body=body,
        to=to,
    )

    # Something could be renaming the file concurrently so it can't be attached
    with FileLock(settings.MEDIA_LOCK):
        for attachment_path, mime_type in attachments:
            with attachment_path.open("rb") as f:
                content = f.read()
                if mime_type == "message/rfc822":
                    # See https://forum.djangoproject.com/t/using-emailmessage-with-an-attached-email-file-crashes-due-to-non-ascii/37981
                    content = message_from_bytes(content)

                email.attach(
                    filename=attachment_path.name,
                    content=content,
                    mimetype=mime_type,
                )

    return email.send()
