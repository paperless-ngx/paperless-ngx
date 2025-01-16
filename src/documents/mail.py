from email.encoders import encode_base64
from email.mime.base import MIMEBase
from pathlib import Path
from urllib.parse import quote

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
            file_content = f.read()

            main_type, sub_type = (
                attachment_mime_type.split("/", 1)
                if attachment_mime_type
                else ("application", "octet-stream")
            )
            mime_part = MIMEBase(main_type, sub_type)
            mime_part.set_payload(file_content)

            encode_base64(mime_part)

            # see https://github.com/stumpylog/tika-client/blob/f65a2b792fc3cf15b9b119501bba9bddfac15fcc/src/tika_client/_base.py#L46-L57
            try:
                attachment.name.encode("ascii")
            except UnicodeEncodeError:
                filename_safed = attachment.name.encode("ascii", "ignore").decode(
                    "ascii",
                )
                filepath_quoted = quote(attachment.name, encoding="utf-8")
                mime_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={filename_safed}; filename*=UTF-8''{filepath_quoted}",
                )
            else:
                mime_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={attachment.name}",
                )

            email.attach(mime_part)
    return email.send()
