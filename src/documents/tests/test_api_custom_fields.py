from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestCustomField(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/custom_fields/"

    def setUp(self):
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        return super().setUp()

    def test_create_custom_field(self):
        """
        GIVEN:
            - Each of the supported data types is created
        WHEN:
            - API request to create custom metadata is made
        THEN:
            - the field is created
            - the field returns the correct fields
        """
        for field_type, name in [
            ("string", "Custom Text"),
            ("url", "Wikipedia Link"),
            ("date", "Invoiced Date"),
            ("integer", "Invoice #"),
        ]:
            resp = self.client.post(
                self.ENDPOINT,
                data={
                    "data_type": field_type,
                    "name": name,
                },
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

            data = resp.json()

            self.assertEqual(len(data), 3)
            self.assertEqual(data["name"], name)
            self.assertEqual(data["data_type"], field_type)

    def test_create_custom_field_instance(self):
        doc = Document.objects.create(
            title="WOW",
            content="the content",
            checksum="123",
            mime_type="application/pdf",
        )
        custom_field = CustomField.objects.create(
            name="Test Custom Field",
            data_type=CustomField.FieldDataType.STRING,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "parent": {
                            "id": custom_field.id,
                        },
                        "value": "test value",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        doc.refresh_from_db()
        from pprint import pprint

        for item in doc.custom_fields.all():
            pprint(item)
        self.assertFalse(True)
