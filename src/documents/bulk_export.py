from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from documents.models import CustomField
from documents.permissions import get_shared_object_pks

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Sequence
    from datetime import date
    from datetime import datetime
    from typing import IO

    from django.contrib.auth.models import User
    from django.utils.functional import Promise

    from documents.models import Document

CUSTOM_FIELD_PREFIX = "custom_field_"

MAX_EXPORT_DOCUMENTS = 10_000

FIELD_LABELS: dict[str, Promise] = {
    "id": _("ID"),
    "title": _("Title"),
    "created": _("Created"),
    "added": _("Added"),
    "modified": _("Modified"),
    "tag": _("Tags"),
    "correspondent": _("Correspondent"),
    "documenttype": _("Document type"),
    "storagepath": _("Storage path"),
    "note": _("Notes"),
    "owner": _("Owner"),
    "shared": _("Shared"),
    "asn": _("ASN"),
    "pagecount": _("Pages"),
    "mime_type": _("MIME type"),
    "filename": _("Filename"),
    "archived_filename": _("Archived filename"),
    "content": _("Content"),
}

STANDARD_FIELDS = frozenset(FIELD_LABELS.keys())

FILE_FIELDS = frozenset(
    {
        "content",
        "mime_type",
        "pagecount",
        "filename",
        "archived_filename",
    },
)

FIELD_PERMISSIONS: dict[str, str] = {
    "tag": "documents.view_tag",
    "correspondent": "documents.view_correspondent",
    "documenttype": "documents.view_documenttype",
    "storagepath": "documents.view_storagepath",
    "note": "documents.view_note",
    "owner": "auth.view_user",
}

CUSTOM_FIELD_PERMISSION = "documents.view_customfield"

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True, slots=True)
class ExportDocument:
    """
    A root document together with the version supplying its file fields.

    ``file_doc`` is the root itself for documents that have no further versions.
    """

    root: Document
    file_doc: Document


def custom_field_column_id(field_id: int) -> str:
    return f"{CUSTOM_FIELD_PREFIX}{field_id}"


def build_export_field_list(
    fields: list[str],
    custom_field_ids: list[int],
) -> list[str]:
    export_fields = list(fields)
    for field_id in custom_field_ids:
        export_fields.append(custom_field_column_id(field_id))
    return export_fields


def custom_field_ids_from_fields(fields: Sequence[str]) -> list[int]:
    return [
        int(field[len(CUSTOM_FIELD_PREFIX) :])
        for field in fields
        if field.startswith(CUSTOM_FIELD_PREFIX)
    ]


def requires_latest_version(fields: Sequence[str]) -> bool:
    return any(field in FILE_FIELDS for field in fields)


def get_custom_field_names(field_ids: list[int]) -> dict[int, str]:
    if not field_ids:
        return {}
    return dict(
        CustomField.objects.filter(id__in=field_ids).values_list("id", "name"),
    )


def sanitize_csv_value(value: str) -> str:
    """
    Neutralize spreadsheet formulas by prefixing suspicious cells with a quote.

    Quoting alone does not stop Excel and friends from evaluating a cell that
    begins with a formula prefix, so any such value -- including document
    titles, tag names and custom field values -- has to be escaped explicitly.
    """
    if value and value[0] in FORMULA_PREFIXES:
        return "'" + value
    return value


def get_csv_headers(
    fields: Sequence[str],
    custom_field_names: dict[int, str],
) -> list[str]:
    headers = []
    for field in fields:
        if field.startswith(CUSTOM_FIELD_PREFIX):
            field_id = int(field[len(CUSTOM_FIELD_PREFIX) :])
            headers.append(custom_field_names.get(field_id, field))
        else:
            headers.append(str(FIELD_LABELS.get(field, field)))
    return [sanitize_csv_value(header) for header in headers]


def _format_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _get_field_value(
    entry: ExportDocument,
    field: str,
    *,
    user: User | None = None,
    shared_object_pks: set[int] | None = None,
    custom_field_values: dict[int, str] | None = None,
) -> str:
    if field.startswith(CUSTOM_FIELD_PREFIX):
        field_id = int(field[len(CUSTOM_FIELD_PREFIX) :])
        return (custom_field_values or {}).get(field_id, "")

    root = entry.root
    file_doc = entry.file_doc

    if field == "id":
        return str(root.id)
    if field == "title":
        return root.title or ""
    if field == "created":
        return _format_date(root.created)
    if field == "added":
        return _format_date(root.added)
    if field == "modified":
        return _format_date(root.modified)
    if field == "tag":
        return ", ".join(tag.name for tag in root.tags.all())
    if field == "correspondent":
        return root.correspondent.name if root.correspondent else ""
    if field == "documenttype":
        return root.document_type.name if root.document_type else ""
    if field == "storagepath":
        return root.storage_path.name if root.storage_path else ""
    if field == "note":
        notes_count = getattr(root, "notes_count", None)
        if notes_count is None:
            notes_count = getattr(root, "notes").count()
        return str(notes_count)
    if field == "owner":
        return root.owner.username if root.owner else ""
    if field == "shared":
        if user is None:
            return ""
        is_shared = (
            root.owner == user
            and shared_object_pks is not None
            and root.id in shared_object_pks
        )
        return str(_("Yes")) if is_shared else str(_("No"))
    if field == "asn":
        return (
            str(root.archive_serial_number)
            if root.archive_serial_number is not None
            else ""
        )
    if field == "pagecount":
        return str(file_doc.page_count) if file_doc.page_count is not None else ""
    if field == "mime_type":
        return file_doc.mime_type or ""
    if field == "filename":
        return file_doc.original_filename or ""
    if field == "archived_filename":
        if file_doc.has_archive_version:
            return file_doc.get_public_filename(archive=True)
        return ""
    if field == "content":
        return file_doc.content or ""

    return ""


def iter_csv_rows(
    documents: Sequence[ExportDocument],
    fields: Sequence[str],
    *,
    user: User | None = None,
) -> Iterator[list[str]]:
    """
    Yield the header row followed by one sanitized row per exported document.
    """
    custom_field_ids = custom_field_ids_from_fields(fields)
    custom_field_names = get_custom_field_names(custom_field_ids)

    shared_object_pks = None
    if user is not None and "shared" in fields:
        shared_object_pks = get_shared_object_pks(
            [entry.root for entry in documents],
        )

    yield get_csv_headers(fields, custom_field_names)

    for entry in documents:
        custom_field_values = {}
        if custom_field_ids:
            for instance in getattr(entry.root, "custom_fields").all():
                if instance.field_id in custom_field_ids:
                    value = instance.value_for_search
                    custom_field_values[instance.field_id] = (
                        "" if value is None else str(value)
                    )

        yield [
            sanitize_csv_value(
                _get_field_value(
                    entry,
                    field,
                    user=user,
                    shared_object_pks=shared_object_pks,
                    custom_field_values=custom_field_values,
                ),
            )
            for field in fields
        ]


def write_documents_csv(
    stream: IO[str],
    documents: Sequence[ExportDocument],
    fields: Sequence[str],
    *,
    user: User | None = None,
) -> None:
    """
    Write the CSV export for the given documents into an open text stream.
    """
    writer = csv.writer(stream)
    for row in iter_csv_rows(documents, fields, user=user):
        writer.writerow(row)
