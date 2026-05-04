import json
from unittest import mock

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


class TestBulkEditAPI(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.user = user
        self.client.force_authenticate(user=user)

        patcher = mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
        self.async_task = patcher.start()
        self.addCleanup(patcher.stop)
        self.c1 = Correspondent.objects.create(name="c1")
        self.c2 = Correspondent.objects.create(name="c2")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.dt2 = DocumentType.objects.create(name="dt2")
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.doc1 = Document.objects.create(checksum="A", title="A")
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            correspondent=self.c1,
            document_type=self.dt1,
            page_count=5,
        )
        self.doc3 = Document.objects.create(
            checksum="C",
            title="C",
            correspondent=self.c2,
            document_type=self.dt2,
        )
        self.doc4 = Document.objects.create(checksum="D", title="D")
        self.doc5 = Document.objects.create(checksum="E", title="E")
        self.doc2.tags.add(self.t1)
        self.doc3.tags.add(self.t2)
        self.doc4.tags.add(self.t1, self.t2)
        self.sp1 = StoragePath.objects.create(name="sp1", path="Something/{checksum}")
        self.cf1 = CustomField.objects.create(name="cf1", data_type="string")
        self.cf2 = CustomField.objects.create(name="cf2", data_type="string")

    def setup_mock(self, m, method_name, return_value="OK") -> None:
        m.return_value = return_value
        m.__name__ = method_name

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_set_correspondent(self, bulk_update_task_mock) -> None:
        self.assertNotEqual(self.doc1.correspondent, self.c1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": self.c1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.correspondent, self.c1)
        bulk_update_task_mock.assert_called_once()
        self.assertCountEqual(
            bulk_update_task_mock.call_args.kwargs["kwargs"]["document_ids"],
            [self.doc1.pk],
        )

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_unset_correspondent(self, bulk_update_task_mock) -> None:
        self.doc1.correspondent = self.c1
        self.doc1.save()
        self.assertIsNotNone(self.doc1.correspondent)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": None},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bulk_update_task_mock.assert_called_once()
        self.doc1.refresh_from_db()
        self.assertIsNone(self.doc1.correspondent)

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_set_type(self, bulk_update_task_mock) -> None:
        self.assertNotEqual(self.doc1.document_type, self.dt1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": self.dt1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.document_type, self.dt1)
        bulk_update_task_mock.assert_called_once()
        self.assertCountEqual(
            bulk_update_task_mock.call_args.kwargs["kwargs"]["document_ids"],
            [self.doc1.pk],
        )

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_unset_type(self, bulk_update_task_mock) -> None:
        self.doc1.document_type = self.dt1
        self.doc1.save()

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": None},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()
        self.assertIsNone(self.doc1.document_type)
        bulk_update_task_mock.assert_called_once()
        self.assertCountEqual(
            bulk_update_task_mock.call_args.kwargs["kwargs"]["document_ids"],
            [self.doc1.pk],
        )

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_add_tag(self, bulk_update_task_mock) -> None:
        self.assertFalse(self.doc1.tags.filter(pk=self.t1.pk).exists())

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "add_tag",
                    "parameters": {"tag": self.t1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()

        self.assertTrue(self.doc1.tags.filter(pk=self.t1.pk).exists())

        bulk_update_task_mock.assert_called_once()
        self.assertCountEqual(
            bulk_update_task_mock.call_args.kwargs["kwargs"]["document_ids"],
            [self.doc1.pk],
        )

    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    def test_api_remove_tag(self, bulk_update_task_mock) -> None:
        self.doc1.tags.add(self.t1)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "remove_tag",
                    "parameters": {"tag": self.t1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()
        self.assertFalse(self.doc1.tags.filter(pk=self.t1.pk).exists())

    @mock.patch("documents.serialisers.bulk_edit.modify_tags")
    def test_api_modify_tags(self, m) -> None:
        self.setup_mock(m, "modify_tags")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t1.id],
                        "remove_tags": [self.t2.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertListEqual(args[0], [self.doc1.id, self.doc3.id])
        self.assertEqual(kwargs["add_tags"], [self.t1.id])
        self.assertEqual(kwargs["remove_tags"], [self.t2.id])

    @mock.patch("documents.serialisers.bulk_edit.modify_tags")
    def test_api_modify_tags_not_provided(self, m) -> None:
        """
        GIVEN:
            - API data to modify tags is missing remove_tags field
        WHEN:
            - API to edit tags is called
        THEN:
            - API returns HTTP 400
            - modify_tags is not called
        """
        self.setup_mock(m, "modify_tags")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t1.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.modify_custom_fields")
    def test_api_modify_custom_fields(self, m) -> None:
        self.setup_mock(m, "modify_custom_fields")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": [
                            self.cf1.id,
                        ],  # old format accepts list of IDs
                        "remove_custom_fields": [self.cf2.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertListEqual(args[0], [self.doc1.id, self.doc3.id])
        self.assertEqual(kwargs["add_custom_fields"], [self.cf1.id])
        self.assertEqual(kwargs["remove_custom_fields"], [self.cf2.id])

    @mock.patch("documents.serialisers.bulk_edit.modify_custom_fields")
    def test_api_modify_custom_fields_documentlink_forbidden_for_unpermitted_target(
        self,
        m,
    ) -> None:
        self.setup_mock(m, "modify_custom_fields")
        user = User.objects.create_user(username="doc-owner")
        user.user_permissions.add(Permission.objects.get(codename="change_document"))
        other_user = User.objects.create_user(username="other-user")
        source_doc = Document.objects.create(
            checksum="source",
            title="Source",
            owner=user,
        )
        target_doc = Document.objects.create(
            checksum="target",
            title="Target",
            owner=other_user,
        )
        doclink_field = CustomField.objects.create(
            name="doclink",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [source_doc.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": {doclink_field.id: [target_doc.id]},
                        "remove_custom_fields": [],
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.modify_custom_fields")
    def test_api_modify_custom_fields_with_values(self, m) -> None:
        self.setup_mock(m, "modify_custom_fields")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": {self.cf1.id: "foo"},
                        "remove_custom_fields": [self.cf2.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertListEqual(args[0], [self.doc1.id, self.doc3.id])
        self.assertEqual(kwargs["add_custom_fields"], {str(self.cf1.id): "foo"})
        self.assertEqual(kwargs["remove_custom_fields"], [self.cf2.id])

    @mock.patch("documents.serialisers.bulk_edit.modify_custom_fields")
    def test_api_modify_custom_fields_invalid_params(self, m) -> None:
        """
        GIVEN:
            - API data to modify custom fields is malformed
        WHEN:
            - API to edit custom fields is called
        THEN:
            - API returns HTTP 400
            - modify_custom_fields is not called
        """
        self.setup_mock(m, "modify_custom_fields")
        # Missing add_custom_fields
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": [self.cf1.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

        # Missing remove_custom_fields
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "remove_custom_fields": [self.cf1.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

        # Not a list
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": self.cf1.id,
                        "remove_custom_fields": self.cf2.id,
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

        # Invalid dict
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": {"foo": 99},
                        "remove_custom_fields": [self.cf2.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

        # Missing remove_custom_fields
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": ["foo"],
                        "remove_custom_fields": ["bar"],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

        # Custom field ID not found

        # Missing remove_custom_fields
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": [self.cf1.id],
                        "remove_custom_fields": [99],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.delete")
    def test_api_delete(self, m) -> None:
        self.setup_mock(m, "delete")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc1.id], "method": "delete"},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(len(kwargs), 0)

    @mock.patch("documents.views.bulk_edit.delete")
    def test_delete_documents_endpoint(self, m) -> None:
        self.setup_mock(m, "delete")
        response = self.client.post(
            "/api/documents/delete/",
            json.dumps({"documents": [self.doc1.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(len(kwargs), 0)

    @mock.patch("documents.views.bulk_edit.reprocess")
    def test_reprocess_documents_endpoint(self, m) -> None:
        self.setup_mock(m, "reprocess")
        response = self.client.post(
            "/api/documents/reprocess/",
            json.dumps({"documents": [self.doc1.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(len(kwargs), 0)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_set_storage_path(self, m) -> None:
        """
        GIVEN:
            - API data to set the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        self.setup_mock(m, "set_storage_path")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args

        self.assertListEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["storage_path"], self.sp1.id)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_unset_storage_path(self, m) -> None:
        """
        GIVEN:
            - API data to clear/unset the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and None storage_path
        """
        self.setup_mock(m, "set_storage_path")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": None},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args

        self.assertListEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["storage_path"], None)

    def test_api_invalid_storage_path(self) -> None:
        """
        GIVEN:
            - API data to set the storage path of a document
            - Given storage_path ID isn't valid
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id + 10},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.async_task.assert_not_called()

    def test_api_set_storage_path_not_provided(self) -> None:
        """
        GIVEN:
            - API data to set the storage path of a document
            - API data is missing storage path ID
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.async_task.assert_not_called()

    def test_api_invalid_doc(self) -> None:
        self.assertEqual(Document.objects.count(), 5)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps({"documents": [-235], "method": "delete"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 5)

    def test_api_requires_documents_unless_all_is_true(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"documents is required unless all is true", response.content)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_bulk_edit_with_all_true_resolves_documents_from_filters(
        self,
        m,
    ) -> None:
        self.setup_mock(m, "set_storage_path")

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "all": True,
                    "filters": {"title__icontains": "B"},
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc2.id])
        self.assertEqual(kwargs["storage_path"], self.sp1.id)

    @mock.patch("documents.search.get_backend")
    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_bulk_edit_with_all_true_resolves_documents_from_search_filters(
        self,
        m,
        get_backend,
    ) -> None:
        self.setup_mock(m, "set_storage_path")

        for filters in (
            {"text": "new doc 2017-03-16"},
            {"title_search": "apple"},
        ):
            with self.subTest(filters=filters):
                get_backend.return_value.search_ids.return_value = [self.doc2.id]

                response = self.client.post(
                    "/api/documents/bulk_edit/",
                    json.dumps(
                        {
                            "all": True,
                            "filters": filters,
                            "method": "set_storage_path",
                            "parameters": {"storage_path": self.sp1.id},
                        },
                    ),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                get_backend.return_value.search_ids.assert_called_once()
                args, kwargs = m.call_args
                self.assertEqual(args[0], [self.doc2.id])
                self.assertEqual(kwargs["storage_path"], self.sp1.id)

                m.reset_mock()
                get_backend.return_value.search_ids.reset_mock()

    def test_api_bulk_edit_with_all_true_rejects_unsupported_methods(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "all": True,
                    "method": "merge",
                    "parameters": {"metadata_document_id": self.doc2.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"This method does not support all=true", response.content)

    def test_api_invalid_method(self) -> None:
        self.assertEqual(Document.objects.count(), 5)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "exterminate",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 5)

    def test_api_invalid_correspondent(self) -> None:
        self.assertEqual(self.doc2.correspondent, self.c1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        doc2 = Document.objects.get(id=self.doc2.id)
        self.assertEqual(doc2.correspondent, self.c1)

    def test_api_no_correspondent(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_correspondent",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_invalid_document_type(self) -> None:
        self.assertEqual(self.doc2.document_type, self.dt1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        doc2 = Document.objects.get(id=self.doc2.id)
        self.assertEqual(doc2.document_type, self.dt1)

    def test_api_no_document_type(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_document_type",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_add_invalid_tag(self) -> None:
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "add_tag",
                    "parameters": {"tag": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(list(self.doc2.tags.all()), [self.t1])

    def test_api_add_tag_no_tag(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "add_tag"},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_delete_invalid_tag(self) -> None:
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "remove_tag",
                    "parameters": {"tag": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(list(self.doc2.tags.all()), [self.t1])

    def test_api_delete_tag_no_tag(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "remove_tag"},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_modify_invalid_tags(self) -> None:
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t2.id, 1657],
                        "remove_tags": [1123123],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_modify_tags_no_tags(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {"remove_tags": [1123123]},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {"add_tags": [self.t2.id, 1657]},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_selection_data_empty(self) -> None:
        response = self.client.post(
            "/api/documents/selection_data/",
            json.dumps({"documents": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field, Entity in [
            ("selected_correspondents", Correspondent),
            ("selected_tags", Tag),
            ("selected_document_types", DocumentType),
        ]:
            self.assertEqual(len(response.data[field]), Entity.objects.count())
            for correspondent in response.data[field]:
                self.assertEqual(correspondent["document_count"], 0)
            self.assertCountEqual(
                map(lambda c: c["id"], response.data[field]),
                map(lambda c: c["id"], Entity.objects.values("id")),
            )

    def test_api_selection_data(self) -> None:
        response = self.client.post(
            "/api/documents/selection_data/",
            json.dumps(
                {"documents": [self.doc1.id, self.doc2.id, self.doc4.id, self.doc5.id]},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertCountEqual(
            response.data["selected_correspondents"],
            [
                {"id": self.c1.id, "document_count": 1},
                {"id": self.c2.id, "document_count": 0},
            ],
        )
        self.assertCountEqual(
            response.data["selected_tags"],
            [
                {"id": self.t1.id, "document_count": 2},
                {"id": self.t2.id, "document_count": 1},
            ],
        )
        self.assertCountEqual(
            response.data["selected_document_types"],
            [
                {"id": self.c1.id, "document_count": 1},
                {"id": self.c2.id, "document_count": 0},
            ],
        )

    def test_api_selection_data_requires_view_permission(self) -> None:
        self.doc2.owner = self.user
        self.doc2.save()

        user1 = User.objects.create(username="user1")
        self.client.force_authenticate(user=user1)

        response = self.client.post(
            "/api/documents/selection_data/",
            json.dumps({"documents": [self.doc2.id]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_set_permissions(self, m) -> None:
        self.setup_mock(m, "set_permissions")
        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")
        permissions = {
            "view": {
                "users": [user1.id, user2.id],
                "groups": None,
            },
            "change": {
                "users": [user1.id],
                "groups": None,
            },
        }

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(len(kwargs["set_permissions"]["view"]["users"]), 2)

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_set_permissions_merge(self, m) -> None:
        self.setup_mock(m, "set_permissions")
        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")
        permissions = {
            "view": {
                "users": [user1.id, user2.id],
                "groups": None,
            },
            "change": {
                "users": [user1.id],
                "groups": None,
            },
        }

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called()
        _, kwargs = m.call_args
        self.assertEqual(kwargs["merge"], False)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions, "merge": True},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called()
        _, kwargs = m.call_args
        self.assertEqual(kwargs["merge"], True)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    @mock.patch("documents.views.bulk_edit.merge")
    def test_insufficient_global_perms(self, mock_merge, mock_set_storage) -> None:
        """
        GIVEN:
            - User has no global permissions to change a document
            - User has no global permissions to add a document
            - User has no global permissions to delete a document
        WHEN:
            - API is called to set storage path
            - API is called to merge documents
            - API is called to merge with delete
        THEN:
            - API returns HTTP 403 for all calls unless global permissions are granted
        """
        user1 = User.objects.create(username="user1")
        user1.save()
        self.client.force_authenticate(user=user1)
        self.setup_mock(mock_set_storage, "set_storage_path")
        self.setup_mock(mock_merge, "merge")
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_set_storage.assert_not_called()

        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "metadata_document_id": self.doc1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_merge.assert_not_called()

        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "metadata_document_id": self.doc1.id,
                    "delete_originals": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_merge.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_insufficient_permissions_ownership(self, m) -> None:
        """
        GIVEN:
            - Documents owned by user other than logged in user
        WHEN:
            - set_permissions bulk edit API endpoint is called
        THEN:
            - User is not able to change permissions
        """
        self.setup_mock(m, "set_permissions")
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        permissions = {
            "owner": user1.id,
        }

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_insufficient_permissions_edit(self, m) -> None:
        """
        GIVEN:
            - Documents for which current user only has view permissions
        WHEN:
            - API is called
        THEN:
            - set_storage_path only called if user can edit all docs
        """
        self.setup_mock(m, "set_storage_path")
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        assign_perm("view_document", user1, self.doc1)
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        assign_perm("change_document", user1, self.doc1)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()

    @mock.patch("documents.views.bulk_edit.rotate")
    def test_rotate(self, m) -> None:
        self.setup_mock(m, "rotate")
        response = self.client.post(
            "/api/documents/rotate/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "degrees": 90,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(kwargs["degrees"], 90)
        self.assertEqual(kwargs["source_mode"], "latest_version")
        self.assertEqual(kwargs["user"], self.user)

    @mock.patch("documents.views.bulk_edit.rotate")
    def test_rotate_invalid_params(self, m) -> None:
        response = self.client.post(
            "/api/documents/rotate/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "degrees": "foo",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/documents/rotate/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "degrees": 90.5,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    @mock.patch("documents.views.bulk_edit.rotate")
    def test_rotate_insufficient_permissions(self, m) -> None:
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        self.setup_mock(m, "rotate")
        response = self.client.post(
            "/api/documents/rotate/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "degrees": 90,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/rotate/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "degrees": 90,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.views.bulk_edit.merge")
    def test_merge(self, m) -> None:
        self.setup_mock(m, "merge")
        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "metadata_document_id": self.doc3.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(kwargs["metadata_document_id"], self.doc3.id)
        self.assertEqual(kwargs["source_mode"], "latest_version")
        self.assertEqual(kwargs["user"], self.user)

    @mock.patch("documents.views.bulk_edit.merge")
    def test_merge_and_delete_insufficient_permissions(self, m) -> None:
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        self.setup_mock(m, "merge")
        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "metadata_document_id": self.doc2.id,
                    "delete_originals": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "metadata_document_id": self.doc2.id,
                    "delete_originals": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.views.bulk_edit.merge")
    def test_merge_invalid_parameters(self, m) -> None:
        self.setup_mock(m, "merge")
        response = self.client.post(
            "/api/documents/merge/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "delete_originals": "not_boolean",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    def test_bulk_edit_allows_legacy_file_methods_with_warning(self) -> None:
        method_payloads = {
            "delete": {},
            "reprocess": {},
            "rotate": {"degrees": 90},
            "merge": {"metadata_document_id": self.doc2.id},
            "edit_pdf": {"operations": [{"page": 1}]},
            "remove_password": {"password": "secret"},
            "split": {"pages": "1,2-4"},
            "delete_pages": {"pages": [1, 2]},
        }

        for version in (9, 10):
            for method, parameters in method_payloads.items():
                with self.subTest(method=method, version=version):
                    with mock.patch(
                        f"documents.views.bulk_edit.{method}",
                    ) as mocked_method:
                        self.setup_mock(mocked_method, method)
                        with self.assertLogs("paperless.api", level="WARNING") as logs:
                            response = self.client.post(
                                "/api/documents/bulk_edit/",
                                json.dumps(
                                    {
                                        "documents": [self.doc2.id],
                                        "method": method,
                                        "parameters": parameters,
                                    },
                                ),
                                content_type="application/json",
                                headers={
                                    "Accept": f"application/json; version={version}",
                                },
                            )

                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        mocked_method.assert_called_once()
                        self.assertTrue(
                            any(
                                "Deprecated bulk_edit method" in entry
                                and f"'{method}'" in entry
                                for entry in logs.output
                            ),
                        )

    @mock.patch("documents.views.bulk_edit.edit_pdf")
    def test_edit_pdf(self, m) -> None:
        self.setup_mock(m, "edit_pdf")
        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 1}],
                    "source_mode": "explicit_selection",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id])
        self.assertEqual(kwargs["operations"], [{"page": 1}])
        self.assertEqual(kwargs["source_mode"], "explicit_selection")
        self.assertEqual(kwargs["user"], self.user)

    def test_edit_pdf_invalid_params(self) -> None:
        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "operations": [{"page": 1}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"Edit PDF method only supports one document", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": "not_a_list",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"Expected a list of items", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": ["invalid_operation"],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"invalid operation entry", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": "not_an_int"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"page must be an integer", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 1, "rotate": "not_an_int"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"rotate must be an integer", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 1, "doc": "not_an_int"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"doc must be an integer", response.content)

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "update_document": True,
                    "operations": [{"page": 1, "doc": 1}, {"page": 2, "doc": 2}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            b"update_document only allowed with a single output document",
            response.content,
        )

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 1}],
                    "source_mode": "not_a_mode",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"Invalid source_mode", response.content)

    @mock.patch("documents.views.bulk_edit.edit_pdf")
    def test_edit_pdf_page_out_of_bounds(self, m) -> None:
        self.setup_mock(m, "edit_pdf")
        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 99}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"out of bounds", response.content)
        m.assert_not_called()

    @mock.patch("documents.views.bulk_edit.edit_pdf")
    def test_edit_pdf_insufficient_permissions(self, m) -> None:
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        self.setup_mock(m, "edit_pdf")
        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "operations": [{"page": 1}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/edit_pdf/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "operations": [{"page": 1}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.views.bulk_edit.remove_password")
    def test_remove_password(self, m) -> None:
        self.setup_mock(m, "remove_password")
        response = self.client.post(
            "/api/documents/remove_password/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "password": "secret",
                    "update_document": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id])
        self.assertEqual(kwargs["password"], "secret")
        self.assertTrue(kwargs["update_document"])
        self.assertEqual(kwargs["source_mode"], "latest_version")
        self.assertEqual(kwargs["user"], self.user)

    def test_remove_password_invalid_params(self) -> None:
        response = self.client.post(
            "/api/documents/remove_password/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/documents/remove_password/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "password": 123,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch("documents.views.bulk_edit.remove_password")
    def test_remove_password_insufficient_permissions(self, m) -> None:
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()
        self.client.force_authenticate(user=user1)

        self.setup_mock(m, "remove_password")
        response = self.client.post(
            "/api/documents/remove_password/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "password": "secret",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/remove_password/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "password": "secret",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @override_settings(AUDIT_LOG_ENABLED=True)
    def test_bulk_edit_audit_log_enabled_simple_field(self) -> None:
        """
        GIVEN:
            - Audit log is enabled
        WHEN:
            - API to bulk edit documents is called
        THEN:
            - Audit log is created
        """
        LogEntry.objects.all().delete()
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": self.c2.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(LogEntry.objects.filter(object_pk=self.doc1.id).count(), 1)

    @override_settings(AUDIT_LOG_ENABLED=True)
    def test_bulk_edit_audit_log_enabled_tags(self) -> None:
        """
        GIVEN:
            - Audit log is enabled
        WHEN:
            - API to bulk edit tags is called
        THEN:
            - Audit log is created
        """
        LogEntry.objects.all().delete()
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t1.id],
                        "remove_tags": [self.t2.id],
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(LogEntry.objects.filter(object_pk=self.doc1.id).count(), 1)

    @override_settings(AUDIT_LOG_ENABLED=True)
    def test_bulk_edit_audit_log_enabled_custom_fields(self) -> None:
        """
        GIVEN:
            - Audit log is enabled
        WHEN:
            - API to bulk edit custom fields is called
        THEN:
            - Audit log is created
        """
        LogEntry.objects.all().delete()
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": [self.cf1.id],
                        "remove_custom_fields": [],
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(LogEntry.objects.filter(object_pk=self.doc1.id).count(), 2)
