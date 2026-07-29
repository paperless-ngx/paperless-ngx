import csv
import io
from typing import TYPE_CHECKING

from django.utils.translation import gettext as _

from documents.models import CustomField
from documents.models import Document
from documents.serialisers import OwnedObjectSerializer

if TYPE_CHECKING:
    from django.contrib.auth.models import User

CUSTOM_FIELD_PREFIX = "custom_field_"

FIELD_LABELS: dict[str, str] = {
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


def get_custom_field_names(field_ids: list[int]) -> dict[int, str]:
    if not field_ids:
        return {}
    return dict(
        CustomField.objects.filter(id__in=field_ids).values_list("id", "name"),
    )


def get_csv_headers(
    fields: list[str],
    custom_field_names: dict[int, str],
) -> list[str]:
    headers = []
    for field in fields:
        if field.startswith(CUSTOM_FIELD_PREFIX):
            field_id = int(field[len(CUSTOM_FIELD_PREFIX) :])
            headers.append(custom_field_names.get(field_id, field))
        else:
            headers.append(str(FIELD_LABELS.get(field, field)))
    return headers


def _format_date(value) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _get_field_value(
    document: Document,
    field: str,
    *,
    user: "User | None" = None,
    shared_object_pks: set[int] | None = None,
    notes_count: int | None = None,
    custom_field_values: dict[int, str] | None = None,
) -> str:
    if field.startswith(CUSTOM_FIELD_PREFIX):
        field_id = int(field[len(CUSTOM_FIELD_PREFIX) :])
        return (custom_field_values or {}).get(field_id, "")

    if field == "id":
        return str(document.id)
    if field == "title":
        return document.title or ""
    if field == "created":
        return _format_date(document.created)
    if field == "added":
        return _format_date(document.added)
    if field == "modified":
        return _format_date(document.modified)
    if field == "tag":
        return ", ".join(tag.name for tag in document.tags.all())
    if field == "correspondent":
        return document.correspondent.name if document.correspondent else ""
    if field == "documenttype":
        return document.document_type.name if document.document_type else ""
    if field == "storagepath":
        return document.storage_path.name if document.storage_path else ""
    if field == "note":
        if notes_count is not None:
            return str(notes_count)
        return str(document.notes.count())
    if field == "owner":
        return document.owner.username if document.owner else ""
    if field == "shared":
        if user is None:
            return ""
        is_shared = (
            document.owner == user
            and shared_object_pks is not None
            and document.id in shared_object_pks
        )
        return _("Yes") if is_shared else _("No")
    if field == "asn":
        return (
            str(document.archive_serial_number)
            if document.archive_serial_number is not None
            else ""
        )
    if field == "pagecount":
        return str(document.page_count) if document.page_count is not None else ""
    if field == "mime_type":
        return document.mime_type or ""
    if field == "filename":
        return document.original_filename or ""
    if field == "archived_filename":
        if document.has_archive_version:
            return document.get_public_filename(archive=True)
        return ""
    if field == "content":
        return document.content or ""

    return ""


def export_documents_to_csv(
    documents: list[Document],
    fields: list[str],
    *,
    user: "User | None" = None,
) -> bytes:
    custom_field_ids = [
        int(field[len(CUSTOM_FIELD_PREFIX) :])
        for field in fields
        if field.startswith(CUSTOM_FIELD_PREFIX)
    ]
    custom_field_names = get_custom_field_names(custom_field_ids)
    shared_object_pks = None
    if user is not None and "shared" in fields:
        shared_object_pks = OwnedObjectSerializer.get_shared_object_pks(
            documents,
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(get_csv_headers(fields, custom_field_names))

    for document in documents:
        notes_count = None
        if "note" in fields and hasattr(document, "notes_count"):
            notes_count = document.notes_count

        custom_field_values = {}
        if custom_field_ids:
            for instance in document.custom_fields.all():
                if instance.field_id in custom_field_ids:
                    value = instance.value_for_search
                    custom_field_values[instance.field_id] = (
                        "" if value is None else str(value)
                    )

        row = [
            _get_field_value(
                document,
                field,
                user=user,
                shared_object_pks=shared_object_pks,
                notes_count=notes_count,
                custom_field_values=custom_field_values,
            )
            for field in fields
        ]
        writer.writerow(row)

    return output.getvalue().encode("utf-8")
