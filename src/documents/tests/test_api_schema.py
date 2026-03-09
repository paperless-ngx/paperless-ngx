from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework import status
from rest_framework.test import APITestCase


class TestApiSchema(APITestCase):
    ENDPOINT = "/api/schema/"

    def test_valid_schema(self) -> None:
        """
        Test that the schema is valid
        """
        try:
            call_command("spectacular", "--validate", "--fail-on-warn")
        except CommandError as e:
            self.fail(f"Schema validation failed: {e}")

    def test_get_schema_endpoints(self) -> None:
        """
        Test that the schema endpoints exist and return a 200 status code
        """
        schema_response = self.client.get(self.ENDPOINT)
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)

        ui_response = self.client.get(self.ENDPOINT + "view/")
        self.assertEqual(ui_response.status_code, status.HTTP_200_OK)

    def test_schema_includes_dedicated_document_edit_endpoints(self) -> None:
        schema_response = self.client.get(self.ENDPOINT)
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)

        paths = schema_response.data["paths"]
        self.assertIn("/api/documents/delete/", paths)
        self.assertIn("/api/documents/reprocess/", paths)
        self.assertIn("/api/documents/rotate/", paths)
        self.assertIn("/api/documents/merge/", paths)
        self.assertIn("/api/documents/edit_pdf/", paths)
        self.assertIn("/api/documents/remove_password/", paths)

    def test_schema_bulk_edit_advertises_legacy_document_action_methods(self) -> None:
        schema_response = self.client.get(self.ENDPOINT)
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)

        schema = schema_response.data["components"]["schemas"]
        bulk_schema = schema["BulkEditRequest"]
        method_schema = bulk_schema["properties"]["method"]

        # drf-spectacular emits the enum as a referenced schema for this field
        enum_ref = method_schema["allOf"][0]["$ref"].split("/")[-1]
        advertised_methods = schema[enum_ref]["enum"]

        for action_method in [
            "delete",
            "reprocess",
            "rotate",
            "merge",
            "edit_pdf",
            "remove_password",
            "split",
            "delete_pages",
        ]:
            self.assertIn(action_method, advertised_methods)
