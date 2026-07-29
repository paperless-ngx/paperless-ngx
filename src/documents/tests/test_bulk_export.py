import csv
import io
import shutil

from django.contrib.auth.models import User
from django.db.models import Count
from django.test import TestCase
from django.utils import timezone
from guardian.shortcuts import assign_perm

from documents.bulk_export import STANDARD_FIELDS
from documents.bulk_export import _get_field_value
from documents.bulk_export import build_export_field_list
from documents.bulk_export import custom_field_column_id
from documents.bulk_export import export_documents_to_csv
from documents.bulk_export import get_csv_headers
from documents.bulk_export import get_custom_field_names
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin


class TestBulkExport(DirectoriesMixin, SampleDirMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.owner = User.objects.create_user(username="owner")
        self.other_user = User.objects.create_user(username="other")
        self.correspondent = Correspondent.objects.create(name="ACME Corp")
        self.document_type = DocumentType.objects.create(name="Invoice")
        self.storage_path = StoragePath.objects.create(
            name="Default",
            path="{title}",
        )
        self.tag = Tag.objects.create(name="important")
        self.custom_field = CustomField.objects.create(
            name="Reference",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.empty_custom_field = CustomField.objects.create(
            name="Optional",
            data_type=CustomField.FieldDataType.STRING,
        )

        self.document = Document.objects.create(
            title="Invoice 1",
            checksum="A",
            mime_type="application/pdf",
            content="OCR text",
            created=timezone.datetime(2024, 1, 15).date(),
            original_filename="invoice1.pdf",
            correspondent=self.correspondent,
            document_type=self.document_type,
            storage_path=self.storage_path,
            owner=self.owner,
            archive_serial_number=42,
            page_count=3,
            archive_filename="archive.pdf",
            archive_checksum="ARCHIVE",
        )
        self.document.tags.add(self.tag)
        shutil.copy(self.SAMPLE_DIR / "test_with_bom.pdf", self.document.archive_path)

        CustomFieldInstance.objects.create(
            document=self.document,
            field=self.custom_field,
            value_text="REF-001",
        )
        CustomFieldInstance.objects.create(
            document=self.document,
            field=self.empty_custom_field,
        )
        Note.objects.create(
            document=self.document,
            note="A note",
            user=self.owner,
        )
        assign_perm("view_document", self.other_user, self.document)

    def test_helper_functions(self) -> None:
        self.assertEqual(custom_field_column_id(5), "custom_field_5")
        self.assertEqual(
            build_export_field_list(["title"], [1, 2]),
            ["title", "custom_field_1", "custom_field_2"],
        )
        self.assertEqual(get_custom_field_names([]), {})
        self.assertEqual(
            get_custom_field_names([self.custom_field.id]),
            {self.custom_field.id: "Reference"},
        )
        self.assertEqual(
            get_csv_headers(
                ["title", custom_field_column_id(999)],
                {},
            ),
            ["Title", "custom_field_999"],
        )

    def test_get_field_value_covers_all_standard_fields(self) -> None:
        document = (
            Document.objects.filter(pk=self.document.pk)
            .select_related(
                "correspondent",
                "document_type",
                "storage_path",
                "owner",
            )
            .prefetch_related("tags", "custom_fields__field")
            .annotate(notes_count=Count("notes"))
            .get()
        )
        shared_pks = {document.id}

        self.assertEqual(_get_field_value(document, "id"), str(document.id))
        self.assertEqual(_get_field_value(document, "title"), "Invoice 1")
        self.assertEqual(_get_field_value(document, "created"), "2024-01-15")
        self.assertTrue(_get_field_value(document, "added"))
        self.assertTrue(_get_field_value(document, "modified"))
        self.assertEqual(_get_field_value(document, "tag"), "important")
        self.assertEqual(_get_field_value(document, "correspondent"), "ACME Corp")
        self.assertEqual(_get_field_value(document, "documenttype"), "Invoice")
        self.assertEqual(_get_field_value(document, "storagepath"), "Default")
        self.assertEqual(
            _get_field_value(document, "note", notes_count=document.notes_count),
            "1",
        )
        self.assertEqual(_get_field_value(document, "owner"), "owner")
        self.assertEqual(
            _get_field_value(
                document,
                "shared",
                user=self.owner,
                shared_object_pks=shared_pks,
            ),
            "Yes",
        )
        self.assertEqual(
            _get_field_value(
                document,
                "shared",
                user=self.owner,
                shared_object_pks=set(),
            ),
            "No",
        )
        self.assertEqual(_get_field_value(document, "shared", user=None), "")
        self.assertEqual(_get_field_value(document, "asn"), "42")
        self.assertEqual(_get_field_value(document, "pagecount"), "3")
        self.assertEqual(_get_field_value(document, "mime_type"), "application/pdf")
        self.assertEqual(_get_field_value(document, "filename"), "invoice1.pdf")
        self.assertTrue(_get_field_value(document, "archived_filename"))
        self.assertEqual(_get_field_value(document, "content"), "OCR text")
        self.assertEqual(
            _get_field_value(
                document,
                custom_field_column_id(self.custom_field.id),
                custom_field_values={self.custom_field.id: "REF-001"},
            ),
            "REF-001",
        )
        self.assertEqual(_get_field_value(document, "unknown_field"), "")

    def test_export_documents_to_csv_with_all_fields(self) -> None:
        document = (
            Document.objects.filter(pk=self.document.pk)
            .select_related(
                "correspondent",
                "document_type",
                "storage_path",
                "owner",
            )
            .prefetch_related("tags", "custom_fields__field")
            .annotate(notes_count=Count("notes"))
            .get()
        )
        fields = build_export_field_list(
            sorted(STANDARD_FIELDS),
            [self.custom_field.id, self.empty_custom_field.id],
        )

        csv_bytes = export_documents_to_csv([document], fields, user=self.owner)
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))

        self.assertEqual(len(rows), 2)
        self.assertIn("Reference", rows[0])
        self.assertIn("Optional", rows[0])
        self.assertIn("REF-001", rows[1])
        self.assertIn("Yes", rows[1])

    def test_export_documents_to_csv_counts_notes_without_annotation(self) -> None:
        document = (
            Document.objects.filter(pk=self.document.pk)
            .prefetch_related("tags", "custom_fields__field")
            .get()
        )

        csv_bytes = export_documents_to_csv([document], ["note"])
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))

        self.assertEqual(rows[1][0], "1")

    def test_export_documents_to_csv_without_archive_or_optional_values(self) -> None:
        document = Document.objects.create(
            title="Plain",
            checksum="B",
            mime_type="application/pdf",
        )

        csv_bytes = export_documents_to_csv(
            [document],
            ["archived_filename", "asn", "pagecount", "owner"],
        )
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))

        self.assertEqual(rows[1], ["", "", "", ""])

    def test_format_date_none(self) -> None:
        from documents.bulk_export import _format_date

        self.assertEqual(_format_date(None), "")
