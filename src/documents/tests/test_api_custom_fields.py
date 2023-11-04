from datetime import date

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
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
            ("boolean", "Is Active"),
            ("float", "Total Paid"),
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
        """
        GIVEN:
            - Field of each data type is created
        WHEN:
            - API request to create custom metadata instance with each data type
        THEN:
            - the field instance is created
            - the field returns the correct fields and values
            - the field is attached to the given document
        """
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
        custom_field_float = CustomField.objects.create(
            name="Test Custom Field Float",
            data_type=CustomField.FieldDataType.FLOAT,
        )
        custom_field_monetary = CustomField.objects.create(
            name="Test Custom Field Monetary",
            data_type=CustomField.FieldDataType.MONETARY,
        )

        date_value = date.today()

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
                        "value": date_value.isoformat(),
                    },
                    {
                        "field": custom_field_int.id,
                        "value": 3,
                    },
                    {
                        "field": custom_field_boolean.id,
                        "value": True,
                    },
                    {
                        "field": custom_field_url.id,
                        "value": "https://example.com",
                    },
                    {
                        "field": custom_field_float.id,
                        "value": 12.3456,
                    },
                    {
                        "field": custom_field_monetary.id,
                        "value": 11.10,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp_data = resp.json()["custom_fields"]

        self.assertCountEqual(
            resp_data,
            [
                {"field": custom_field_string.id, "value": "test value"},
                {"field": custom_field_date.id, "value": date_value.isoformat()},
                {"field": custom_field_int.id, "value": 3},
                {"field": custom_field_boolean.id, "value": True},
                {"field": custom_field_url.id, "value": "https://example.com"},
                {"field": custom_field_float.id, "value": 12.3456},
                {"field": custom_field_monetary.id, "value": 11.10},
            ],
        )

        doc.refresh_from_db()
        self.assertEqual(len(doc.custom_fields.all()), 7)

    def test_change_custom_field_instance_value(self):
        """
        GIVEN:
            - Custom field instance is created and attached to document
        WHEN:
            - API request to create change the value of the custom field
        THEN:
            - the field instance is updated
            - the field returns the correct fields and values
        """
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

        # Create
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
        self.assertEqual(CustomFieldInstance.objects.count(), 1)
        self.assertEqual(doc.custom_fields.first().value, "test value")

        # Update
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
        self.assertEqual(CustomFieldInstance.objects.count(), 1)
        self.assertEqual(doc.custom_fields.first().value, "a new test value")

    def test_delete_custom_field_instance(self):
        """
        GIVEN:
            - Multiple custom field instances are created and attached to document
        WHEN:
            - API request to remove a field
        THEN:
            - the field instance is removed
            - the other field remains unchanged
            - the field returns the correct fields and values
        """
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

        date_value = date.today()

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_string.id,
                        "value": "a new test value",
                    },
                    {
                        "field": custom_field_date.id,
                        "value": date_value.isoformat(),
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomFieldInstance.objects.count(), 2)
        self.assertEqual(len(doc.custom_fields.all()), 2)

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_date.id,
                        "value": date_value.isoformat(),
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomFieldInstance.objects.count(), 1)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(len(doc.custom_fields.all()), 1)
        self.assertEqual(doc.custom_fields.first().value, date_value)

    def test_custom_field_validation(self):
        """
        GIVEN:
            - Document exists with no fields
        WHEN:
            - API request to remove a field
            - API request is not valid
        THEN:
            - HTTP 400 is returned
            - No field created
            - No field attached to the document
        """
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

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_string.id,
                        # Whoops, spelling
                        "valeu": "a new test value",
                    },
                ],
            },
            format="json",
        )
        from pprint import pprint

        pprint(resp.json())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value
        THEN:
            - HTTP 400 is returned
            - No field instance is created or attached to the document
        """
        doc = Document.objects.create(
            title="WOW",
            content="the content",
            checksum="123",
            mime_type="application/pdf",
        )
        custom_field_url = CustomField.objects.create(
            name="Test Custom Field URL",
            data_type=CustomField.FieldDataType.URL,
        )
        custom_field_int = CustomField.objects.create(
            name="Test Custom Field INT",
            data_type=CustomField.FieldDataType.INT,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_url.id,
                        "value": "not a url",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

        self.assertRaises(
            Exception,
            self.client.patch,
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_int.id,
                        "value": "not an int",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)
