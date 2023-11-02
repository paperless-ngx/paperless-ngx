from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField, CustomFieldInstance, CustomFieldShortText
from documents.models import Document
from documents.tests.utils import DirectoriesMixin
from pprint import pprint


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
            ("boolean", "Is Active"),
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
        custom_field_string = CustomField.objects.create(
            name="Test Custom Field String",
            data_type=CustomField.FieldDataType.STRING,
        )
        custom_field_date = CustomField.objects.create(
            name="Test Custom Field Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        custom_field_int = CustomField.objects.create(
            name="Test Custom Field Int",
            data_type=CustomField.FieldDataType.INT,
        )
        custom_field_boolean = CustomField.objects.create(
            name="Test Custom Field Boolean",
            data_type=CustomField.FieldDataType.BOOL,
        )
        custom_field_url = CustomField.objects.create(
            name="Test Custom Field Url",
            data_type=CustomField.FieldDataType.URL,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_string.id,
                        "value": "test value",
                    },
                    {
                        "field": custom_field_date.id,
                        "value": "2023-10-31",
                    },
                    {
                        "field": custom_field_int.id,
                        "value": "3",
                    },
                    {
                        "field": custom_field_boolean.id,
                        "value": "True",
                    },
                    {
                        "field": custom_field_url.id,
                        "value": "https://example.com",
                    },
                ],
            },
            format="json",
        )
        from pprint import pprint

        print("Response data")
        pprint(resp.json())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp_data = resp.json()["custom_fields"]

        self.assertCountEqual(
            resp_data,
            [
                {"field": custom_field_string.id, "value": "test value"},
                {"field": custom_field_date.id, "value": "2023-10-31"},
                {"field": custom_field_int.id, "value": 3},
                {"field": custom_field_boolean.id, "value": True},
                {"field": custom_field_url.id, "value": "https://example.com"},
            ],
        )

        doc.refresh_from_db()
        self.assertEqual(len(doc.custom_fields.all()), 5)
        for custom_field in doc.custom_fields.all():
            print(custom_field.value, type(custom_field.value))

    def test_change_custom_field_instance_value(self):
        doc = Document.objects.create(
            title="WOW",
            content="the content",
            checksum="123",
            mime_type="application/pdf",
        )
        custom_field_string = CustomField.objects.create(
            name="Test Custom Field String",
            data_type=CustomField.FieldDataType.STRING,
        )

        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(CustomFieldShortText.objects.count(), 0)

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_string.id,
                        "value": "test value",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        pprint(resp.json())

        self.assertEqual(doc.custom_fields.first().value, "test value")
        self.assertEqual(CustomFieldInstance.objects.count(), 1)
        self.assertEqual(CustomFieldShortText.objects.count(), 1)

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_string.id,
                        "value": "a new test value",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        pprint(resp.json())

        self.assertEqual(doc.custom_fields.first().value, "a new test value")
        self.assertEqual(CustomFieldInstance.objects.count(), 1)
        self.assertEqual(CustomFieldShortText.objects.count(), 1)
