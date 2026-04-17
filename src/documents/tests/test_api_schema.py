import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase


class TestApiSchema(APITestCase):
    ENDPOINT = "/api/schema/"

    def test_valid_schema(self) -> None:
        """
        Test that the schema is valid
        """
        try:
            call_command(
                "spectacular",
                "--validate",
                "--fail-on-warn",
                skip_checks=True,
            )
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


# ---- session-scoped fixture: generate schema once for all TestXxx classes ----


@pytest.fixture(scope="session")
def api_schema():
    generator = SchemaGenerator()
    return generator.get_schema(request=None, public=True)


class TestTasksSummarySchema:
    """tasks_summary_retrieve: response must be an array of TaskSummarySerializer."""

    def test_summary_response_is_array(self, api_schema):
        op = api_schema["paths"]["/api/tasks/summary/"]["get"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_200["type"] == "array", (
            "tasks_summary_retrieve response must be type:array"
        )

    def test_summary_items_have_total_count(self, api_schema):
        op = api_schema["paths"]["/api/tasks/summary/"]["get"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        items = resp_200.get("items", {})
        ref = items.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        if component_name:
            props = api_schema["components"]["schemas"][component_name]["properties"]
        else:
            props = items.get("properties", {})
        assert "total_count" in props, (
            "summary items must have 'total_count' (TaskSummarySerializer)"
        )
