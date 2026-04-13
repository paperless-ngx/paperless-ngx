import json
from unittest import mock
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models_ocr_templates import OcrTemplate
from documents.models_ocr_templates import OcrTemplateZone
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

        return super().setUp()

    def test_create_template(self):
        """
        GIVEN:
            - A document type and custom fields exist
        WHEN:
            - API request to create an OCR template is made
        THEN:
            - The template is created with the correct fields
        """
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps({
                "name": "Invoice Template",
                "document_type": self.doc_type.pk,
                "default_page": 0,
                "source_width": 2480,
                "source_height": 3508,
                "enabled": True,
                "zones": [
                    {
                        "name": "Invoice Number",
                        "custom_field": self.custom_field_text.pk,
                        "x": 1500,
                        "y": 200,
                        "width": 800,
                        "height": 100,
                        "ocr_language": "deu+eng",
                        "transform": "strip",
                        "order": 0,
                    },
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = resp.json()
        self.assertEqual(data["name"], "Invoice Template")
        self.assertEqual(data["document_type"], self.doc_type.pk)
        self.assertEqual(len(data["zones"]), 1)
        self.assertEqual(data["zones"][0]["name"], "Invoice Number")
        self.assertEqual(data["zones"][0]["x"], 1500)
        self.assertEqual(data["zones"][0]["width"], 800)

        self.assertEqual(OcrTemplate.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.count(), 1)

    def test_create_template_multiple_zones(self):
        """
        GIVEN:
            - Multiple custom fields exist
        WHEN:
            - A template with multiple zones is created
        THEN:
            - All zones are created correctly
        """
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps({
                "name": "Multi-zone Template",
                "document_type": self.doc_type.pk,
                "default_page": 0,
                "source_width": 2480,
                "source_height": 3508,
                "enabled": True,
                "zones": [
                    {
                        "name": "Invoice Number",
                        "custom_field": self.custom_field_text.pk,
                        "x": 1500,
                        "y": 200,
                        "width": 800,
                        "height": 100,
                        "ocr_language": "deu+eng",
                        "transform": "strip",
                        "order": 0,
                    },
                    {
                        "name": "Invoice Date",
                        "custom_field": self.custom_field_date.pk,
                        "x": 1500,
                        "y": 350,
                        "width": 800,
                        "height": 100,
                        "ocr_language": "deu",
                        "transform": "date_dmy",
                        "order": 1,
                    },
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.json()["zones"]), 2)
        self.assertEqual(OcrTemplateZone.objects.count(), 2)

    def test_list_templates(self):
        """
        GIVEN:
            - Templates exist in the database
        WHEN:
            - API request to list templates is made
        THEN:
            - All templates are returned with their zones
        """
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
            x=100,
            y=100,
            width=200,
            height=50,
        )

        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["results"][0]["zones"]), 1)

    def test_update_template(self):
        """
        GIVEN:
            - A template with zones exists
        WHEN:
            - API request to update the template is made with new zones
        THEN:
            - Old zones are replaced with new ones
        """
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
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = self.client.put(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps({
                "name": "New Name",
                "document_type": self.doc_type.pk,
                "default_page": 0,
                "source_width": 2480,
                "source_height": 3508,
                "enabled": True,
                "zones": [
                    {
                        "name": "New Zone",
                        "custom_field": self.custom_field_date.pk,
                        "x": 500,
                        "y": 500,
                        "width": 300,
                        "height": 150,
                        "ocr_language": "eng",
                        "transform": "date_ymd",
                        "order": 0,
                    },
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        template.refresh_from_db()
        self.assertEqual(template.name, "New Name")
        self.assertEqual(OcrTemplateZone.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.first().name, "New Zone")

    def test_delete_template(self):
        """
        GIVEN:
            - A template with zones exists
        WHEN:
            - API request to delete the template is made
        THEN:
            - Template and its zones are deleted
        """
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
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = self.client.delete(f"{self.ENDPOINT}{template.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OcrTemplate.objects.count(), 0)
        self.assertEqual(OcrTemplateZone.objects.count(), 0)

    def test_patch_template_toggle_enabled(self):
        """
        GIVEN:
            - An enabled template exists
        WHEN:
            - API request to patch enabled=false
        THEN:
            - Template is disabled
        """
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
