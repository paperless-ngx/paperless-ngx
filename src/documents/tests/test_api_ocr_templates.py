"""Tests for the OCR Template API."""

import json

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import DocumentType
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.tests.utils import DirectoriesMixin


class TestOcrTemplatesAPI(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/ocr_templates/"

    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.custom_field_text = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.custom_field_date = CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        self.custom_field_int = CustomField.objects.create(
            name="Amount",
            data_type=CustomField.FieldDataType.INT,
        )
        self.custom_field_doclink = CustomField.objects.create(
            name="Related Docs",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )

        return super().setUp()

    def _make_template_data(self, **overrides):
        data = {
            "name": "Invoice Template",
            "document_type": self.doc_type.pk,
            "default_page": 0,
            "source_width": 2480,
            "source_height": 3508,
            "enabled": True,
            "zones": [],
        }
        data.update(overrides)
        return data

    def _make_zone_data(self, **overrides):
        data = {
            "name": "Zone 1",
            "custom_field": self.custom_field_text.pk,
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 50,
            "ocr_language": "deu+eng",
            "transform": "strip",
            "order": 0,
        }
        data.update(overrides)
        return data

    # --- Create ---

    def test_create_template(self):
        """
        GIVEN:
            - A document type and custom fields exist
        WHEN:
            - API request to create an OCR template with one zone
        THEN:
            - The template and zone are created
        """
        data = self._make_template_data(
            zones=[self._make_zone_data(name="Invoice Number", x=1500, y=200, width=800, height=100)],
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        result = resp.json()
        self.assertEqual(result["name"], "Invoice Template")
        self.assertEqual(result["document_type"], self.doc_type.pk)
        self.assertEqual(len(result["zones"]), 1)
        self.assertEqual(result["zones"][0]["name"], "Invoice Number")
        self.assertEqual(OcrTemplate.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.count(), 1)

    def test_create_template_multiple_zones(self):
        """
        GIVEN:
            - Multiple custom fields exist
        WHEN:
            - A template with multiple zones is created
        THEN:
            - All zones are created
        """
        data = self._make_template_data(
            zones=[
                self._make_zone_data(name="Invoice Number", custom_field=self.custom_field_text.pk),
                self._make_zone_data(name="Invoice Date", custom_field=self.custom_field_date.pk, order=1),
            ],
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.json()["zones"]), 2)
        self.assertEqual(OcrTemplateZone.objects.count(), 2)

    def test_create_template_no_zones(self):
        """
        GIVEN:
            - Valid template data without zones
        WHEN:
            - Template is created
        THEN:
            - Template is created with no zones
        """
        data = self._make_template_data()
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.json()["zones"]), 0)

    # --- Validation ---

    def test_create_template_zero_source_width_rejected(self):
        """
        GIVEN:
            - Template data with source_width=0
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        data = self._make_template_data(source_width=0)
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_template_zero_source_height_rejected(self):
        data = self._make_template_data(source_height=0)
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_zero_width_rejected(self):
        data = self._make_template_data(
            zones=[self._make_zone_data(width=0)],
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_zero_height_rejected(self):
        data = self._make_template_data(
            zones=[self._make_zone_data(height=0)],
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_exceeds_source_width_rejected(self):
        """Zone that extends beyond the source image width should be rejected."""
        data = self._make_template_data(
            source_width=1000,
            zones=[self._make_zone_data(x=800, width=300)],  # 800+300 > 1000
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_exceeds_source_height_rejected(self):
        data = self._make_template_data(
            source_height=1000,
            zones=[self._make_zone_data(y=900, height=200)],  # 900+200 > 1000
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_unsupported_custom_field_type_rejected(self):
        """DOCUMENTLINK and SELECT fields can't be populated via OCR."""
        data = self._make_template_data(
            zones=[self._make_zone_data(custom_field=self.custom_field_doclink.pk)],
        )
        resp = self.client.post(self.ENDPOINT, data=json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- List ---

    def test_list_templates(self):
        template = OcrTemplate.objects.create(
            name="Test Template",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone 1",
            custom_field=self.custom_field_text,
            x=100, y=100, width=200, height=50,
        )

        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["results"][0]["zones"]), 1)

    def test_list_empty(self):
        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 0)

    # --- Update ---

    def test_update_template_replaces_zones(self):
        """PUT should replace all zones with the new set."""
        template = OcrTemplate.objects.create(
            name="Old Name",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Old Zone",
            custom_field=self.custom_field_text,
            x=0, y=0, width=100, height=100,
        )

        data = self._make_template_data(
            name="New Name",
            zones=[self._make_zone_data(name="New Zone", custom_field=self.custom_field_date.pk)],
        )
        resp = self.client.put(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        template.refresh_from_db()
        self.assertEqual(template.name, "New Name")
        self.assertEqual(OcrTemplateZone.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.first().name, "New Zone")

    # --- Delete ---

    def test_delete_template_cascades_zones(self):
        template = OcrTemplate.objects.create(
            name="To Delete",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone",
            custom_field=self.custom_field_text,
            x=0, y=0, width=100, height=100,
        )

        resp = self.client.delete(f"{self.ENDPOINT}{template.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OcrTemplate.objects.count(), 0)
        self.assertEqual(OcrTemplateZone.objects.count(), 0)

    def test_delete_nonexistent_returns_404(self):
        resp = self.client.delete(f"{self.ENDPOINT}99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --- Patch ---

    def test_patch_toggle_enabled(self):
        template = OcrTemplate.objects.create(
            name="Toggle Test",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
            enabled=True,
        )

        resp = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps({"enabled": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        template.refresh_from_db()
        self.assertFalse(template.enabled)

    def test_patch_preserves_zones(self):
        """PATCH without zones field should not delete existing zones."""
        template = OcrTemplate.objects.create(
            name="Patch Test",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Existing Zone",
            custom_field=self.custom_field_text,
            x=0, y=0, width=100, height=100,
        )

        resp = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps({"name": "Updated Name"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(OcrTemplateZone.objects.count(), 1)

    # --- Auth ---

    def test_unauthenticated_rejected(self):
        self.client.logout()
        resp = self.client.get(self.ENDPOINT)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # --- Quick create field ---

    def test_quick_create_field(self):
        """Creating a custom field inline from the template editor."""
        resp = self.client.post(
            f"{self.ENDPOINT}quick-create-field/",
            data=json.dumps({"name": "New Field", "data_type": "string"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["name"], "New Field")
        self.assertEqual(data["data_type"], "string")
        self.assertTrue(data["created"])
        self.assertTrue(CustomField.objects.filter(name="New Field").exists())

    def test_quick_create_field_existing(self):
        """If a field with the same name exists, return it without creating."""
        resp = self.client.post(
            f"{self.ENDPOINT}quick-create-field/",
            data=json.dumps({"name": "Invoice Number", "data_type": "string"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["id"], self.custom_field_text.pk)
        self.assertFalse(data["created"])

    def test_quick_create_field_empty_name_rejected(self):
        resp = self.client.post(
            f"{self.ENDPOINT}quick-create-field/",
            data=json.dumps({"name": "", "data_type": "string"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quick_create_field_unsupported_type_rejected(self):
        resp = self.client.post(
            f"{self.ENDPOINT}quick-create-field/",
            data=json.dumps({"name": "Bad Field", "data_type": "documentlink"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quick_create_field_select_type_rejected(self):
        resp = self.client.post(
            f"{self.ENDPOINT}quick-create-field/",
            data=json.dumps({"name": "Bad Field", "data_type": "select"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
