import json
from datetime import date

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestCustomFieldsAPI(DirectoriesMixin, APITestCase):
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
            ("float", "Average Value"),
            ("monetary", "Total Paid"),
            ("documentlink", "Related Documents"),
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

            self.assertEqual(data["name"], name)
            self.assertEqual(data["data_type"], field_type)

        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "select",
                    "name": "Select Field",
                    "extra_data": {
                        "select_options": ["Option 1", "Option 2"],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = resp.json()

        self.assertCountEqual(
            data["extra_data"]["select_options"],
            ["Option 1", "Option 2"],
        )

    def test_create_custom_field_nonunique_name(self):
        """
        GIVEN:
            - Custom field exists
        WHEN:
            - API request to create custom field with the same name
        THEN:
            - HTTP 400 is returned
        """
        CustomField.objects.create(
            name="Test Custom Field",
            data_type=CustomField.FieldDataType.STRING,
        )

        resp = self.client.post(
            self.ENDPOINT,
            data={
                "data_type": "string",
                "name": "Test Custom Field",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_custom_field_select_invalid_options(self):
        """
        GIVEN:
            - Custom field does not exist
        WHEN:
            - API request to create custom field with invalid select options
        THEN:
            - HTTP 400 is returned
        """

        # Not a list
        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "select",
                    "name": "Select Field",
                    "extra_data": {
                        "select_options": "not a list",
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # No options
        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "select",
                    "name": "Select Field",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_custom_field_monetary_validation(self):
        """
        GIVEN:
            - Custom field does not exist
        WHEN:
            - API request to create custom field with invalid default currency option
            - API request to create custom field with valid default currency option
        THEN:
            - HTTP 400 is returned
            - HTTP 201 is returned
        """

        # not a string
        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "monetary",
                    "name": "Monetary Field",
                    "extra_data": {
                        "default_currency": 123,
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # not a 3-letter currency code
        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "monetary",
                    "name": "Monetary Field",
                    "extra_data": {
                        "default_currency": "EU",
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # valid currency code
        resp = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "data_type": "monetary",
                    "name": "Monetary Field",
                    "extra_data": {
                        "default_currency": "EUR",
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

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
        doc2 = Document.objects.create(
            title="WOW2",
            content="the content2",
            checksum="1234",
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
        custom_field_monetary2 = CustomField.objects.create(
            name="Test Custom Field Monetary 2",
            data_type=CustomField.FieldDataType.MONETARY,
        )
        custom_field_documentlink = CustomField.objects.create(
            name="Test Custom Field Doc Link",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )
        custom_field_select = CustomField.objects.create(
            name="Test Custom Field Select",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={
                "select_options": ["Option 1", "Option 2"],
            },
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
                        "value": "EUR11.10",
                    },
                    {
                        "field": custom_field_monetary2.id,
                        "value": 11.10,  # Legacy format
                    },
                    {
                        "field": custom_field_documentlink.id,
                        "value": [doc2.id],
                    },
                    {
                        "field": custom_field_select.id,
                        "value": 0,
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
                {"field": custom_field_monetary.id, "value": "EUR11.10"},
                {"field": custom_field_monetary2.id, "value": "11.1"},
                {"field": custom_field_documentlink.id, "value": [doc2.id]},
                {"field": custom_field_select.id, "value": 0},
            ],
        )

        doc.refresh_from_db()
        self.assertEqual(len(doc.custom_fields.all()), 10)

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

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_url_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to something which is or is not a link
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

        for value in ["not a url", "file:"]:
            with self.subTest(f"Test value {value}"):
                resp = self.client.patch(
                    f"/api/documents/{doc.id}/",
                    data={
                        "custom_fields": [
                            {
                                "field": custom_field_url.id,
                                "value": value,
                            },
                        ],
                    },
                    format="json",
                )

                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(CustomFieldInstance.objects.count(), 0)
                self.assertEqual(len(doc.custom_fields.all()), 0)
        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_url.id,
                        "value": "tel:+1-816-555-1212",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_custom_field_value_integer_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to something not an integer
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
        custom_field_int = CustomField.objects.create(
            name="Test Custom Field INT",
            data_type=CustomField.FieldDataType.INT,
        )

        resp = self.client.patch(
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

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_monetary_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to something not a valid monetary decimal (legacy) or not a new monetary format e.g. USD12.34
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
        custom_field_money = CustomField.objects.create(
            name="Test Custom Field MONETARY",
            data_type=CustomField.FieldDataType.MONETARY,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_money.id,
                        # Too many places past decimal
                        "value": 12.123,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_money.id,
                        # Too many places past decimal
                        "value": "GBP12.123",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_money.id,
                        # Not a 3-letter currency code
                        "value": "G12.12",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_short_text_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to a too long string
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
        custom_field_string = CustomField.objects.create(
            name="Test Custom Field STRING",
            data_type=CustomField.FieldDataType.STRING,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {"field": custom_field_string.id, "value": "a" * 129},
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_select_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to something not in the select options
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
        custom_field_select = CustomField.objects.create(
            name="Test Custom Field SELECT",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={
                "select_options": ["Option 1", "Option 2"],
            },
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {"field": custom_field_select.id, "value": 3},
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_value_documentlink_validation(self):
        """
        GIVEN:
            - Document & custom field exist
        WHEN:
            - API request to set a field value to a document that does not exist
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
        custom_field_documentlink = CustomField.objects.create(
            name="Test Custom Field Doc Link",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": [
                    {"field": custom_field_documentlink.id, "value": [999]},
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomFieldInstance.objects.count(), 0)
        self.assertEqual(len(doc.custom_fields.all()), 0)

    def test_custom_field_not_null(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - API request with custom_fields set to null
        THEN:
            - HTTP 400 is returned
        """
        doc = Document.objects.create(
            title="WOW",
            content="the content",
            checksum="123",
            mime_type="application/pdf",
        )

        resp = self.client.patch(
            f"/api/documents/{doc.id}/",
            data={
                "custom_fields": None,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_symmetric_doclink_fields(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Doc links are added or removed
        THEN:
            - Symmetrical link is created or removed as expected
        """
        doc1 = Document.objects.create(
            title="WOW1",
            content="1",
            checksum="1",
            mime_type="application/pdf",
        )
        doc2 = Document.objects.create(
            title="WOW2",
            content="the content2",
            checksum="2",
            mime_type="application/pdf",
        )
        doc3 = Document.objects.create(
            title="WOW3",
            content="the content3",
            checksum="3",
            mime_type="application/pdf",
        )
        doc4 = Document.objects.create(
            title="WOW4",
            content="the content4",
            checksum="4",
            mime_type="application/pdf",
        )
        custom_field_doclink = CustomField.objects.create(
            name="Test Custom Field Doc Link",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )

        # Add links, creates bi-directional
        resp = self.client.patch(
            f"/api/documents/{doc1.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_doclink.id,
                        "value": [2, 3, 4],
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomFieldInstance.objects.count(), 4)
        self.assertEqual(doc2.custom_fields.first().value, [1])
        self.assertEqual(doc3.custom_fields.first().value, [1])
        self.assertEqual(doc4.custom_fields.first().value, [1])

        # Add links appends if necessary
        resp = self.client.patch(
            f"/api/documents/{doc3.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_doclink.id,
                        "value": [1, 4],
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(doc4.custom_fields.first().value, [1, 3])

        # Remove one of the links, removed on other doc
        resp = self.client.patch(
            f"/api/documents/{doc1.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_doclink.id,
                        "value": [2, 3],
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(doc2.custom_fields.first().value, [1])
        self.assertEqual(doc3.custom_fields.first().value, [1, 4])
        self.assertEqual(doc4.custom_fields.first().value, [3])

        # Removes the field entirely
        resp = self.client.patch(
            f"/api/documents/{doc1.id}/",
            data={
                "custom_fields": [],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(doc2.custom_fields.first().value, [])
        self.assertEqual(doc3.custom_fields.first().value, [4])
        self.assertEqual(doc4.custom_fields.first().value, [3])

        # If field exists on target doc but value is None
        doc5 = Document.objects.create(
            title="WOW5",
            content="the content4",
            checksum="5",
            mime_type="application/pdf",
        )
        CustomFieldInstance.objects.create(document=doc5, field=custom_field_doclink)

        resp = self.client.patch(
            f"/api/documents/{doc1.id}/",
            data={
                "custom_fields": [
                    {
                        "field": custom_field_doclink.id,
                        "value": [doc5.id],
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(doc5.custom_fields.first().value, [1])

    def test_custom_field_filters(self):
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

        response = self.client.get(
            f"{self.ENDPOINT}?id={custom_field_string.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        response = self.client.get(
            f"{self.ENDPOINT}?id__in={custom_field_string.id},{custom_field_date.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        response = self.client.get(
            f"{self.ENDPOINT}?name__icontains=Int",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], custom_field_int.name)

    def test_custom_fields_document_count(self):
        custom_field_string = CustomField.objects.create(
            name="Test Custom Field String",
            data_type=CustomField.FieldDataType.STRING,
        )
        doc = Document.objects.create(
            title="WOW",
            content="the content",
            checksum="123",
            mime_type="application/pdf",
            owner=self.user,
        )

        response = self.client.get(
            f"{self.ENDPOINT}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["document_count"], 0)

        CustomFieldInstance.objects.create(
            document=doc,
            field=custom_field_string,
            value_text="test value",
        )

        response = self.client.get(
            f"{self.ENDPOINT}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["document_count"], 1)

        # Test as user without access to the document
        non_superuser = User.objects.create_user(username="non_superuser")
        non_superuser.user_permissions.add(
            *Permission.objects.all(),
        )
        non_superuser.save()
        self.client.force_authenticate(user=non_superuser)
        self.client.force_login(user=non_superuser)
        response = self.client.get(
            f"{self.ENDPOINT}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["document_count"], 0)
