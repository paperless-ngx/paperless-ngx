import textwrap

from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning
from django.core.checks import register
from django.core.exceptions import FieldError
from django.db.utils import OperationalError
from django.db.utils import ProgrammingError

from documents.signals import document_consumer_declaration
from documents.templating.utils import convert_format_str_to_template_format


@register()
def changed_password_check(app_configs, **kwargs):
    from documents.models import Document
    from paperless.db import GnuPG

    try:
        encrypted_doc = (
            Document.objects.filter(
                storage_type=Document.STORAGE_TYPE_GPG,
            )
            .only("pk", "storage_type")
            .first()
        )
    except (OperationalError, ProgrammingError, FieldError):
        return []  # No documents table yet

    if encrypted_doc:
        if not settings.PASSPHRASE:
            return [
                Error(
                    "The database contains encrypted documents but no password "
                    "is set.",
                ),
            ]

        if not GnuPG.decrypted(encrypted_doc.source_file):
            return [
                Error(
                    textwrap.dedent(
                        """
                The current password doesn't match the password of the
                existing documents.

                If you intend to change your password, you must first export
                all of the old documents, start fresh with the new password
                and then re-import them."
                """,
                    ),
                ),
            ]

    return []


@register()
def parser_check(app_configs, **kwargs):
    parsers = []
    for response in document_consumer_declaration.send(None):
        parsers.append(response[1])

    if len(parsers) == 0:
        return [
            Error(
                "No parsers found. This is a bug. The consumer won't be "
                "able to consume any documents without parsers.",
            ),
        ]
    else:
        return []


@register()
def filename_format_check(app_configs, **kwargs):
    if settings.FILENAME_FORMAT:
        converted_format = convert_format_str_to_template_format(
            settings.FILENAME_FORMAT,
        )
        if converted_format != settings.FILENAME_FORMAT:
            return [
                Warning(
                    f"Filename format {settings.FILENAME_FORMAT} is using the old style, please update to use double curly brackets",
                    hint=converted_format,
                ),
            ]
    return []
