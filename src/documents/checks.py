import textwrap

from django.conf import settings
from django.core.checks import Error, register
from django.db.utils import OperationalError, ProgrammingError


@register()
def changed_password_check(app_configs, **kwargs):

    from documents.models import Document
    from paperless.db import GnuPG

    try:
        encrypted_doc = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_GPG).first()
    except (OperationalError, ProgrammingError):
        return []  # No documents table yet

    if encrypted_doc:

        if not settings.PASSPHRASE:
            return [Error(
                "The database contains encrypted documents but no password "
                "is set."
            )]

        if not GnuPG.decrypted(encrypted_doc.source_file):
            return [Error(textwrap.dedent(
                """
                The current password doesn't match the password of the
                existing documents.

                If you intend to change your password, you must first export
                all of the old documents, start fresh with the new password
                and then re-import them."
                """))]

    return []
