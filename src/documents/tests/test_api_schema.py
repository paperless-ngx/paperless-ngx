import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase


@pytest.fixture(scope="session")
def api_schema():
    generator = SchemaGenerator()
    return generator.get_schema(request=None, public=True)


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


class TestTasksSummarySchema:
    """tasks_summary_retrieve: response must be an array of TaskSummarySerializer."""

    def test_summary_response_is_array(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/tasks/summary/"]["get"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_200["type"] == "array", (
            "tasks_summary_retrieve response must be type:array"
        )

    def test_summary_items_have_total_count(self, api_schema: SchemaGenerator):
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


class TestTasksActiveSchema:
    """tasks_active_retrieve: response must be an array of TaskSerializerV10."""

    def test_active_response_is_array(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/tasks/active/"]["get"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_200["type"] == "array", (
            "tasks_active_retrieve response must be type:array"
        )

    def test_active_items_ref_named_schema(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/tasks/active/"]["get"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        items = resp_200.get("items", {})
        ref = items.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        assert component_name, "items should be a $ref to a named schema"
        assert component_name in api_schema["components"]["schemas"]


class TestMetadataSchema:
    """Metadata component: array fields and optional archive fields."""

    @pytest.mark.parametrize("field", ["original_metadata", "archive_metadata"])
    def test_metadata_field_is_array(self, api_schema: SchemaGenerator, field: str):
        props = api_schema["components"]["schemas"]["Metadata"]["properties"]
        assert props[field]["type"] == "array", (
            f"{field} should be type:array, not type:object"
        )

    @pytest.mark.parametrize("field", ["original_metadata", "archive_metadata"])
    def test_metadata_items_have_key_field(
        self,
        api_schema: SchemaGenerator,
        field: str,
    ):
        props = api_schema["components"]["schemas"]["Metadata"]["properties"]
        items = props[field]["items"]
        ref = items.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        if component_name:
            item_props = api_schema["components"]["schemas"][component_name][
                "properties"
            ]
        else:
            item_props = items.get("properties", {})
        assert "key" in item_props

    @pytest.mark.parametrize(
        "field",
        [
            "archive_checksum",
            "archive_media_filename",
            "archive_size",
            "archive_metadata",
        ],
    )
    def test_archive_field_not_required(self, api_schema, field):
        schema = api_schema["components"]["schemas"]["Metadata"]
        required = schema.get("required", [])
        assert field not in required
        props = schema["properties"]
        assert props[field].get("nullable") is True, (
            f"{field} should be nullable (allow_null=True)"
        )


class TestStoragePathTestSchema:
    """storage_paths_test_create: response must be a string, not a StoragePath object."""

    def test_test_action_response_is_string(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/storage_paths/test/"]["post"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_200.get("type") == "string", (
            "storage_paths_test_create 200 response must be type:string"
        )

    def test_test_action_request_uses_storage_path_test_serializer(
        self,
        api_schema: SchemaGenerator,
    ):
        op = api_schema["paths"]["/api/storage_paths/test/"]["post"]
        content = (
            op.get("requestBody", {}).get("content", {}).get("application/json", {})
        )
        schema_ref = content.get("schema", {}).get("$ref", "")
        component_name = schema_ref.split("/")[-1]
        # COMPONENT_SPLIT_REQUEST=True causes drf-spectacular to append "Request"
        # to request body component names, so StoragePathTestSerializer -> StoragePathTestRequest
        assert component_name == "StoragePathTestRequest", (
            f"Request body should reference StoragePathTestRequest, got {component_name!r}"
        )


class TestProcessedMailBulkDeleteSchema:
    """processed_mail_bulk_delete_create: response must be {result, deleted_mail_ids}."""

    def _get_props(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/processed_mail/bulk_delete/"]["post"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        ref = resp_200.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        if component_name:
            return api_schema["components"]["schemas"][component_name]["properties"]
        return resp_200.get("properties", {})

    @pytest.mark.parametrize("field", ["result", "deleted_mail_ids"])
    def test_bulk_delete_response_has_field(
        self,
        api_schema: SchemaGenerator,
        field: str,
    ):
        props = self._get_props(api_schema)
        assert field in props, f"bulk_delete 200 response must have a '{field}' field"

    def test_bulk_delete_response_is_not_processed_mail_serializer(self, api_schema):
        op = api_schema["paths"]["/api/processed_mail/bulk_delete/"]["post"]
        resp_200 = op["responses"]["200"]["content"]["application/json"]["schema"]
        ref = resp_200.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        assert component_name != "ProcessedMail", (
            "bulk_delete 200 response must not be the full ProcessedMail serializer"
        )


class TestShareLinkBundleRebuildSchema:
    """share_link_bundles_rebuild_create: 200 returns bundle data; 400 is documented."""

    def test_rebuild_has_400_response(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/share_link_bundles/{id}/rebuild/"]["post"]
        assert "400" in op["responses"], (
            "rebuild must document the 400 response for 'Bundle is already being processed.'"
        )

    def test_rebuild_400_has_detail_field(self, api_schema: SchemaGenerator):
        op = api_schema["paths"]["/api/share_link_bundles/{id}/rebuild/"]["post"]
        resp_400 = op["responses"]["400"]["content"]["application/json"]["schema"]
        ref = resp_400.get("$ref", "")
        component_name = ref.split("/")[-1] if ref else ""
        if component_name:
            props = api_schema["components"]["schemas"][component_name]["properties"]
        else:
            props = resp_400.get("properties", {})
        assert "detail" in props, "rebuild 400 response must have a 'detail' field"
