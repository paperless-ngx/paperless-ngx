import csv
import io
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bulk_export import STANDARD_FIELDS
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin
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
            created=timezone.datetime(2024, 1, 15).date(),
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
            created=timezone.datetime(2024, 2, 20).date(),
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

    def _read_csv(self, response) -> list[list[str]]:
        return list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

    def test_export_selected_documents(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
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
            ),
            content_type="application/json",
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

        doc1_row = next(row for row in rows[1:] if row[0] == "Invoice 1")
        self.assertEqual(doc1_row[1], "2024-01-15")
        self.assertEqual(doc1_row[3], "ACME Corp")
        self.assertEqual(doc1_row[4], "important")
        self.assertEqual(doc1_row[5], "Invoice")
        self.assertEqual(doc1_row[6], "invoice1.pdf")
        self.assertEqual(doc1_row[7], "REF-001")

        doc2_row = next(row for row in rows[1:] if row[0] == "Invoice 2")
        self.assertEqual(doc2_row[3], "")
        self.assertEqual(doc2_row[4], "")
        self.assertEqual(doc2_row[7], "")

    def test_export_requires_at_least_one_field(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {"documents": [self.doc1.id], "fields": [], "custom_fields": []},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_invalid_field(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {"documents": [self.doc1.id], "fields": ["not_a_real_field"]},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    )
    def test_export_all_filtered_documents(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "all": True,
                    "filters": {"title__icontains": "Invoice"},
                    "fields": ["title"],
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = self._read_csv(response)
        self.assertEqual(len(rows), 3)
        titles = {row[0] for row in rows[1:]}
        self.assertEqual(titles, {"Invoice 1", "Invoice 2"})

    def test_export_invalid_custom_field(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "fields": ["title"],
                    "custom_fields": [99999],
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_custom_fields_only(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "fields": [],
                    "custom_fields": [self.custom_field.id],
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = self._read_csv(response)
        self.assertEqual(rows[0], ["Reference"])
        self.assertEqual(rows[1], ["REF-001"])

    def test_export_all_standard_fields(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "fields": sorted(STANDARD_FIELDS),
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = self._read_csv(response)
        self.assertEqual(len(rows[0]), len(STANDARD_FIELDS))
        self.assertEqual(len(rows), 2)

    def test_export_insufficient_permissions(self) -> None:
        user = User.objects.create_user(username="temp_user")
        self.client.force_authenticate(user=user)

        self.doc2.owner = self.user
        self.doc2.save()

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "fields": ["title"],
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")

    @mock.patch.object(BulkExportCsvView, "_resolve_document_ids")
    def test_export_skips_missing_documents(
        self,
        resolve_document_ids,
    ) -> None:
        resolve_document_ids.return_value = [self.doc1.id, 99999]

        response = self.client.post(
            self.ENDPOINT,
            json.dumps({"documents": [self.doc1.id], "fields": ["title"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = self._read_csv(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "Invoice 1")
