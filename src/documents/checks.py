import textwrap

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import FieldError
from django.db.utils import OperationalError, ProgrammingError

from documents.signals import document_consumer_declaration


@register()
def changed_password_check(app_configs, **kwargs):

    from documents.models import Document
    from paperless.db import GnuPG

    try:
        encrypted_doc = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_GPG).first()
    except (OperationalError, ProgrammingError, FieldError):
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


@register()
def parser_check(app_configs, **kwargs):

    parsers = []
    for response in document_consumer_declaration.send(None):
        parsers.append(response[1])

    if len(parsers) == 0:
        return [Error("No parsers found. This is a bug. The consumer won't be "
                      "able to consume any documents without parsers.")]
    else:
        return []
