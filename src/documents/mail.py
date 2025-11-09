from __future__ import annotations

from email import message_from_bytes
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import EmailMessage
from filelock import FileLock

from documents.data_models import ConsumableDocument

if TYPE_CHECKING:
    from documents.models import Document


def send_email(
    subject: str,
    body: str,
    to: list[str],
    attachments: list[Document | ConsumableDocument],
    *,
    use_archive: bool,
) -> int:
    """
    Send an email with attachments.

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of documents to attach (the list may be empty)
        use_archive: Whether to attach archive versions when available

    Returns:
        Number of emails sent

    TODO: re-evaluate this pending https://code.djangoproject.com/ticket/35581 / https://github.com/django/django/pull/18966
    """
    email = EmailMessage(
        subject=subject,
        body=body,
        to=to,
    )

    used_filenames: set[str] = set()

    # Something could be renaming the file concurrently so it can't be attached
    with FileLock(settings.MEDIA_LOCK):
        for document in attachments:
            if isinstance(document, ConsumableDocument):
                attachment_path = document.original_file
                friendly_filename = document.original_file.name
            else:
                attachment_path = (
                    document.archive_path
                    if use_archive and document.has_archive_version
                    else document.source_path
                )
                friendly_filename = _get_unique_filename(
                    document,
                    used_filenames,
                    archive=use_archive and document.has_archive_version,
                )
            used_filenames.add(friendly_filename)

            with attachment_path.open("rb") as f:
                content = f.read()
                if document.mime_type == "message/rfc822":
                    # See https://forum.djangoproject.com/t/using-emailmessage-with-an-attached-email-file-crashes-due-to-non-ascii/37981
                    content = message_from_bytes(content)

                email.attach(
                    filename=friendly_filename,
                    content=content,
                    mimetype=document.mime_type,
                )

    return email.send()


def _get_unique_filename(doc: Document, used_names: set[str], *, archive: bool) -> str:
    """
    Constructs a unique friendly filename for the given document.

    The filename might not be unique enough, so a counter is appended if needed.
    """
    counter = 0
    while True:
        filename = doc.get_public_filename(archive=archive, counter=counter)
        if filename not in used_names:
            return filename
        counter += 1
