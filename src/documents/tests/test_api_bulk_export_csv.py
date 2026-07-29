import csv
import io
import json
from datetime import date
from typing import Any
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.db import connection
from django.http import FileResponse
from django.http import HttpResponse
from django.test.utils import CaptureQueriesContext
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bulk_export import STANDARD_FIELDS
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin
from documents.tests.utils import read_streaming_response
from documents.views import BulkExportCsvView


class TestBulkExportCsv(DirectoriesMixin, SampleDirMixin, APITestCase):
    ENDPOINT = "/api/documents/bulk_export_csv/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.correspondent = Correspondent.objects.create(name="ACME Corp")
        self.document_type = DocumentType.objects.create(name="Invoice")
        self.tag = Tag.objects.create(name="important")

        self.doc1 = Document.objects.create(
            title="Invoice 1",
            checksum="A",
            mime_type="application/pdf",
            content="root content",
            created=date(2024, 1, 15),
            original_filename="invoice1.pdf",
            correspondent=self.correspondent,
            document_type=self.document_type,
            archive_serial_number=42,
            page_count=3,
        )
        self.doc1.tags.add(self.tag)

        self.doc2 = Document.objects.create(
            title="Invoice 2",
            checksum="B",
            mime_type="application/pdf",
            created=date(2024, 2, 20),
            original_filename="invoice2.pdf",
        )

        self.custom_field = CustomField.objects.create(
            name="Reference",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstance.objects.create(
            document=self.doc1,
            field=self.custom_field,
            value_text="REF-001",
        )

    def _post(self, payload: dict[str, Any]) -> HttpResponse:
        return self.client.post(
            self.ENDPOINT,
            json.dumps(payload),
            content_type="application/json",
        )

    def _read_csv(self, response: HttpResponse) -> list[list[str]]:
        content = read_streaming_response(response).decode("utf-8")  # type: ignore[arg-type]
        return list(csv.reader(io.StringIO(content)))

    def _export(self, payload: dict[str, Any]) -> list[list[str]]:
        response = self._post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return self._read_csv(response)

    def test_export_selected_documents(self) -> None:
        response = self._post(
            {
                "documents": [self.doc1.id, self.doc2.id],
                "fields": [
                    "title",
                    "created",
                    "added",
                    "correspondent",
                    "tag",
                    "documenttype",
                    "filename",
                ],
                "custom_fields": [self.custom_field.id],
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("documents.csv", response["Content-Disposition"])

        rows = self._read_csv(response)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0],
            [
                "Title",
                "Created",
                "Added",
                "Correspondent",
                "Tags",
                "Document type",
                "Filename",
                "Reference",
            ],
        )

        self.assertEqual(rows[1][0], "Invoice 1")
        self.assertEqual(rows[1][1], "2024-01-15")
        self.assertEqual(rows[1][3], "ACME Corp")
        self.assertEqual(rows[1][4], "important")
        self.assertEqual(rows[1][5], "Invoice")
        self.assertEqual(rows[1][6], "invoice1.pdf")
        self.assertEqual(rows[1][7], "REF-001")

        self.assertEqual(rows[2][0], "Invoice 2")
        self.assertEqual(rows[2][3], "")
        self.assertEqual(rows[2][4], "")
        self.assertEqual(rows[2][7], "")

    def test_response_is_streamed_and_leaves_no_temporary_file(self) -> None:
        response = self._post({"documents": [self.doc1.id], "fields": ["title"]})

        self.assertIsInstance(response, FileResponse)
        self.assertEqual(self._read_csv(response)[1], ["Invoice 1"])

        # The CSV is generated into a scratch file that is unlinked immediately,
        # so nothing is left behind even though the response is still streaming.
        leftovers = list(settings.SCRATCH_DIR.glob("*-export-csv"))
        self.assertEqual(leftovers, [])

    def test_selection_order_is_preserved(self) -> None:
        rows = self._export(
            {"documents": [self.doc2.id, self.doc1.id], "fields": ["title"]},
        )
        self.assertEqual([row[0] for row in rows[1:]], ["Invoice 2", "Invoice 1"])

    def test_export_requires_at_least_one_field(self) -> None:
        response = self._post(
            {"documents": [self.doc1.id], "fields": [], "custom_fields": []},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_invalid_field(self) -> None:
        response = self._post(
            {"documents": [self.doc1.id], "fields": ["not_a_real_field"]},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_rejects_duplicate_standard_fields(self) -> None:
        response = self._post(
            {"documents": [self.doc1.id], "fields": ["title", "title"]},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fields", response.data)

    def test_export_rejects_duplicate_custom_fields(self) -> None:
        response = self._post(
            {
                "documents": [self.doc1.id],
                "custom_fields": [self.custom_field.id, self.custom_field.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("custom_fields", response.data)

    def test_export_all_filtered_documents(self) -> None:
        rows = self._export(
            {
                "all": True,
                "filters": {"title__icontains": "Invoice"},
                "fields": ["title"],
            },
        )
        self.assertEqual({row[0] for row in rows[1:]}, {"Invoice 1", "Invoice 2"})
        self.assertEqual(len(rows), 3)

    def test_export_custom_fields_only(self) -> None:
        rows = self._export(
            {
                "documents": [self.doc1.id],
                "fields": [],
                "custom_fields": [self.custom_field.id],
            },
        )
        self.assertEqual(rows[0], ["Reference"])
        self.assertEqual(rows[1], ["REF-001"])

    def test_export_all_standard_fields(self) -> None:
        rows = self._export(
            {"documents": [self.doc1.id], "fields": sorted(STANDARD_FIELDS)},
        )
        self.assertEqual(len(rows[0]), len(STANDARD_FIELDS))
        self.assertEqual(len(rows), 2)

    @mock.patch.object(BulkExportCsvView, "_resolve_document_ids")
    def test_export_skips_missing_documents(self, resolve_document_ids) -> None:
        resolve_document_ids.return_value = [self.doc1.id, 99999]

        rows = self._export({"documents": [self.doc1.id], "fields": ["title"]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "Invoice 1")


class TestBulkExportCsvVersioning(DirectoriesMixin, SampleDirMixin, APITestCase):
    """
    A document's metadata lives on its root record while its file lives on the
    latest version, and a selection may reference either of them.
    """

    ENDPOINT = "/api/documents/bulk_export_csv/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.correspondent = Correspondent.objects.create(name="ACME Corp")
        self.tag = Tag.objects.create(name="important")
        self.custom_field = CustomField.objects.create(
            name="Reference",
            data_type=CustomField.FieldDataType.STRING,
        )

        self.root = Document.objects.create(
            title="Invoice 1",
            checksum="root",
            mime_type="application/pdf",
            content="root content",
            original_filename="invoice1.pdf",
            correspondent=self.correspondent,
            archive_serial_number=42,
            page_count=1,
            owner=self.user,
        )
        self.root.tags.add(self.tag)
        CustomFieldInstance.objects.create(
            document=self.root,
            field=self.custom_field,
            value_text="REF-001",
        )
        Note.objects.create(document=self.root, note="A note", user=self.user)

        # Versions only copy title/owner/created and carry their own file.
        Document.objects.create(
            title="Invoice 1",
            checksum="v1",
            mime_type="application/pdf",
            content="v1 content",
            original_filename="invoice1-v1.pdf",
            page_count=2,
            root_document=self.root,
        )
        self.latest = Document.objects.create(
            title="Invoice 1",
            checksum="v2",
            mime_type="image/png",
            content="v2 content",
            original_filename="invoice1-v2.png",
            page_count=5,
            root_document=self.root,
        )

        self.fields = [
            "id",
            "title",
            "correspondent",
            "tag",
            "note",
            "asn",
            "content",
            "mime_type",
            "pagecount",
            "filename",
        ]

    def _post(self, payload: dict[str, Any]) -> HttpResponse:
        return self.client.post(
            self.ENDPOINT,
            json.dumps(payload),
            content_type="application/json",
        )

    def _export(self, payload: dict[str, Any]) -> list[list[str]]:
        response = self._post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = read_streaming_response(response).decode("utf-8")  # type: ignore[arg-type]
        return list(csv.reader(io.StringIO(content)))

    def _assert_single_correct_row(self, rows: list[list[str]]) -> None:
        self.assertEqual(len(rows), 2, msg="expected exactly one data row")
        self.assertEqual(
            rows[1],
            [
                str(self.root.id),
                "Invoice 1",
                "ACME Corp",
                "important",
                "1",
                "42",
                "v2 content",
                "image/png",
                "5",
                "invoice1-v2.png",
            ],
        )

    def test_selecting_the_root_exports_root_metadata_and_latest_file(self) -> None:
        self._assert_single_correct_row(
            self._export({"documents": [self.root.id], "fields": self.fields}),
        )

    def test_selecting_a_version_exports_its_root(self) -> None:
        self._assert_single_correct_row(
            self._export({"documents": [self.latest.id], "fields": self.fields}),
        )

    def test_selecting_a_root_and_its_versions_yields_one_row(self) -> None:
        versions = list(
            Document.objects.filter(root_document=self.root).values_list(
                "pk",
                flat=True,
            ),
        )
        self._assert_single_correct_row(
            self._export(
                {"documents": [self.root.id, *versions], "fields": self.fields},
            ),
        )

    def test_select_all_does_not_duplicate_versions(self) -> None:
        self._assert_single_correct_row(
            self._export({"all": True, "fields": self.fields}),
        )

    def test_custom_fields_are_read_from_the_root(self) -> None:
        rows = self._export(
            {
                "documents": [self.latest.id],
                "fields": [],
                "custom_fields": [self.custom_field.id],
            },
        )
        self.assertEqual(rows[1], ["REF-001"])

    def test_metadata_only_export_does_not_query_for_versions(self) -> None:
        """
        Resolving latest versions is only worth paying for when a file field was
        actually requested.
        """
        with CaptureQueriesContext(connection) as metadata_only:
            self._export({"documents": [self.root.id], "fields": ["title", "note"]})
        with CaptureQueriesContext(connection) as with_file_field:
            self._export({"documents": [self.root.id], "fields": ["title", "content"]})

        self.assertLess(
            len(metadata_only.captured_queries),
            len(with_file_field.captured_queries),
        )


class TestBulkExportCsvSecurity(DirectoriesMixin, SampleDirMixin, APITestCase):
    ENDPOINT = "/api/documents/bulk_export_csv/"

    def setUp(self) -> None:
        super().setUp()

        self.owner = User.objects.create_superuser(username="owner")
        self.user = User.objects.create_user(username="regular")
        self.client.force_authenticate(user=self.user)

        self.doc = Document.objects.create(
            title="Visible",
            checksum="A",
            mime_type="application/pdf",
        )
        self.private_doc = Document.objects.create(
            title="Private",
            checksum="B",
            mime_type="application/pdf",
            owner=self.owner,
        )
        self.custom_field = CustomField.objects.create(
            name="Reference",
            data_type=CustomField.FieldDataType.STRING,
        )

    def _post(self, payload: dict[str, Any]) -> HttpResponse:
        return self.client.post(
            self.ENDPOINT,
            json.dumps(payload),
            content_type="application/json",
        )

    def _grant(self, *codenames: str) -> None:
        self.user.user_permissions.add(
            *Permission.objects.filter(codename__in=codenames),
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_authenticate(user=self.user)

    def test_documents_the_user_cannot_view_are_rejected(self) -> None:
        response = self._post(
            {"documents": [self.private_doc.id], "fields": ["title"]},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")

    def test_a_version_of_an_inaccessible_document_is_rejected(self) -> None:
        version = Document.objects.create(
            title="Private v1",
            checksum="B1",
            mime_type="application/pdf",
            root_document=self.private_doc,
        )
        response = self._post({"documents": [version.id], "fields": ["title"]})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_related_fields_require_the_matching_view_permission(self) -> None:
        """
        Field selection is gated in the UI; without a matching backend check the
        API could simply be called directly to read related objects.
        """
        for field in (
            "tag",
            "correspondent",
            "documenttype",
            "storagepath",
            "note",
            "owner",
        ):
            with self.subTest(field=field):
                response = self._post(
                    {"documents": [self.doc.id], "fields": [field]},
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("fields", response.data)

    def test_unrestricted_fields_do_not_require_permissions(self) -> None:
        response = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["id", "title", "created", "added", "content"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    def test_related_fields_are_allowed_once_permitted(self) -> None:
        self._grant("view_tag", "view_correspondent")
        response = self._post(
            {"documents": [self.doc.id], "fields": ["tag", "correspondent"]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    def test_custom_fields_require_permission(self) -> None:
        response = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["title"],
                "custom_fields": [self.custom_field.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self._grant("view_customfield")
        response = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["title"],
                "custom_fields": [self.custom_field.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    def test_custom_field_errors_do_not_leak_which_ids_exist(self) -> None:
        """
        Distinguishable responses for existing and nonexistent custom fields
        would let any authenticated caller enumerate them.
        """
        existing = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["title"],
                "custom_fields": [self.custom_field.id],
            },
        )
        missing = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["title"],
                "custom_fields": [99999],
            },
        )

        self.assertEqual(existing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(existing.data, missing.data)
        self.assertNotIn(str(self.custom_field.id), json.dumps(existing.data))

        self._grant("view_customfield")
        missing = self._post(
            {
                "documents": [self.doc.id],
                "fields": ["title"],
                "custom_fields": [99999],
            },
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("99999", json.dumps(missing.data))

    def test_formula_injection_is_neutralized_end_to_end(self) -> None:
        assign_perm("view_document", self.user, self.private_doc)
        Document.objects.filter(pk=self.private_doc.pk).update(
            title='=HYPERLINK("http://evil.example","Click")',
            content="@SUM(1+1)",
        )

        response = self._post(
            {
                "documents": [self.private_doc.id],
                "fields": ["title", "content"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = read_streaming_response(response).decode("utf-8")  # type: ignore[arg-type]
        rows = list(csv.reader(io.StringIO(content)))

        self.assertEqual(
            rows[1],
            ['\'=HYPERLINK("http://evil.example","Click")', "'@SUM(1+1)"],
        )


class TestBulkExportCsvLimits(DirectoriesMixin, SampleDirMixin, APITestCase):
    ENDPOINT = "/api/documents/bulk_export_csv/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.documents = [
            Document.objects.create(
                title=f"Document {index}",
                checksum=f"checksum-{index}",
                mime_type="application/pdf",
            )
            for index in range(5)
        ]

    def _post(self, payload: dict[str, Any]) -> HttpResponse:
        return self.client.post(
            self.ENDPOINT,
            json.dumps(payload),
            content_type="application/json",
        )

    @mock.patch("documents.views.MAX_EXPORT_DOCUMENTS", 3)
    def test_export_over_the_limit_is_rejected(self) -> None:
        response = self._post(
            {"documents": [doc.id for doc in self.documents], "fields": ["title"]},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("documents", response.data)

    @mock.patch("documents.views.MAX_EXPORT_DOCUMENTS", 3)
    def test_select_all_stops_resolving_after_the_limit(self) -> None:
        ids = BulkExportCsvView()._resolve_document_ids(
            user=self.user,
            validated_data={"all": True, "filters": {}},
            roots_only=True,
            max_results=3,
        )
        self.assertEqual(len(ids), 4)

        response = self._post({"all": True, "fields": ["title"]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("documents", response.data)

    @mock.patch("documents.views.MAX_EXPORT_DOCUMENTS", 5)
    def test_export_at_the_limit_is_allowed(self) -> None:
        response = self._post(
            {"documents": [doc.id for doc in self.documents], "fields": ["title"]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    @mock.patch("documents.views.MAX_EXPORT_DOCUMENTS", 3)
    def test_limit_counts_unique_roots_rather_than_selected_ids(self) -> None:
        root = self.documents[0]
        version_ids = [
            Document.objects.create(
                title=f"v{index}",
                checksum=f"v-{index}",
                mime_type="application/pdf",
                root_document=root,
            ).id
            for index in range(5)
        ]

        response = self._post(
            {"documents": [root.id, *version_ids], "fields": ["title"]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    def test_query_count_does_not_grow_with_the_number_of_documents(self) -> None:
        """
        Every column must be answered from batched queries; a per-row lookup for
        versions, owners, tags, notes or custom fields would make a large export
        quadratic.
        """
        fields = [
            "id",
            "title",
            "tag",
            "correspondent",
            "documenttype",
            "storagepath",
            "owner",
            "note",
            "shared",
            "content",
            "mime_type",
            "pagecount",
            "filename",
        ]
        # A regular user reading documents owned by somebody else is the worst
        # case: those are the rows needing an actual guardian permission check.
        reader = User.objects.create_user(username="reader")
        reader.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_tag",
                    "view_correspondent",
                    "view_documenttype",
                    "view_storagepath",
                    "view_note",
                    "view_user",
                ],
            ),
        )
        for document in self.documents:
            document.owner = self.user
            document.save()
            assign_perm("view_document", reader, document)
            Document.objects.create(
                title=f"{document.title} v1",
                checksum=f"{document.checksum}-v1",
                mime_type="application/pdf",
                root_document=document,
            )
        self.client.force_authenticate(user=User.objects.get(pk=reader.pk))

        def export(document_ids: list[int]) -> None:
            response = self._post({"documents": document_ids, "fields": fields})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            read_streaming_response(response)  # type: ignore[arg-type]

        # Warm the request-scoped permission caches so they aren't attributed to
        # whichever measurement happens to run first.
        export([self.documents[0].id])

        with CaptureQueriesContext(connection) as single:
            export([self.documents[0].id])

        with CaptureQueriesContext(connection) as many:
            export([document.id for document in self.documents])

        self.assertEqual(
            len(many.captured_queries),
            len(single.captured_queries),
            msg="\n".join(query["sql"] for query in many.captured_queries),
        )
