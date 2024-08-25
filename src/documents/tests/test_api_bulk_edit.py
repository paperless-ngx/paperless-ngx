import json
from unittest import mock

from django.contrib.auth.models import User
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
    def setUp(self):
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.user = user
        self.client.force_authenticate(user=user)

        patcher = mock.patch("documents.bulk_edit.bulk_update_documents.delay")
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
        self.cf1 = CustomField.objects.create(name="cf1", data_type="text")
        self.cf2 = CustomField.objects.create(name="cf2", data_type="text")

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_set_correspondent(self, bulk_update_task_mock):
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
        bulk_update_task_mock.assert_called_once_with(document_ids=[self.doc1.pk])

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_unset_correspondent(self, bulk_update_task_mock):
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

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_set_type(self, bulk_update_task_mock):
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
        bulk_update_task_mock.assert_called_once_with(document_ids=[self.doc1.pk])

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_unset_type(self, bulk_update_task_mock):
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
        bulk_update_task_mock.assert_called_once_with(document_ids=[self.doc1.pk])

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_add_tag(self, bulk_update_task_mock):
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

        bulk_update_task_mock.assert_called_once_with(document_ids=[self.doc1.pk])

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_remove_tag(self, bulk_update_task_mock):
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
    def test_api_modify_tags(self, m):
        m.return_value = "OK"
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
    def test_api_modify_tags_not_provided(self, m):
        """
        GIVEN:
            - API data to modify tags is missing modify_tags field
        WHEN:
            - API to edit tags is called
        THEN:
            - API returns HTTP 400
            - modify_tags is not called
        """
        m.return_value = "OK"
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
    def test_api_modify_custom_fields(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_custom_fields",
                    "parameters": {
                        "add_custom_fields": [self.cf1.id],
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
    def test_api_modify_custom_fields_invalid_params(self, m):
        """
        GIVEN:
            - API data to modify custom fields is malformed
        WHEN:
            - API to edit custom fields is called
        THEN:
            - API returns HTTP 400
            - modify_custom_fields is not called
        """
        m.return_value = "OK"

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

        # Not a list of integers

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
    def test_api_delete(self, m):
        m.return_value = "OK"
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

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_set_storage_path(self, m):
        """
        GIVEN:
            - API data to set the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        m.return_value = "OK"

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
    def test_api_unset_storage_path(self, m):
        """
        GIVEN:
            - API data to clear/unset the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and None storage_path
        """
        m.return_value = "OK"

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

    def test_api_invalid_storage_path(self):
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

    def test_api_set_storage_path_not_provided(self):
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

    def test_api_invalid_doc(self):
        self.assertEqual(Document.objects.count(), 5)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps({"documents": [-235], "method": "delete"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 5)

    def test_api_invalid_method(self):
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

    def test_api_invalid_correspondent(self):
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

    def test_api_no_correspondent(self):
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

    def test_api_invalid_document_type(self):
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

    def test_api_no_document_type(self):
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

    def test_api_add_invalid_tag(self):
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

    def test_api_add_tag_no_tag(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "add_tag"},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_delete_invalid_tag(self):
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

    def test_api_delete_tag_no_tag(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "remove_tag"},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_modify_invalid_tags(self):
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

    def test_api_modify_tags_no_tags(self):
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

    def test_api_selection_data_empty(self):
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

    def test_api_selection_data(self):
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

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_set_permissions(self, m):
        m.return_value = "OK"
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
    def test_set_permissions_merge(self, m):
        m.return_value = "OK"
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
        args, kwargs = m.call_args
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
        args, kwargs = m.call_args
        self.assertEqual(kwargs["merge"], True)

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_insufficient_permissions_ownership(self, m):
        """
        GIVEN:
            - Documents owned by user other than logged in user
        WHEN:
            - set_permissions bulk edit API endpoint is called
        THEN:
            - User is not able to change permissions
        """
        m.return_value = "OK"
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
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
    def test_insufficient_permissions_edit(self, m):
        """
        GIVEN:
            - Documents for which current user only has view permissions
        WHEN:
            - API is called
        THEN:
            - set_storage_path only called if user can edit all docs
        """
        m.return_value = "OK"
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        assign_perm("view_document", user1, self.doc1)
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

    @mock.patch("documents.serialisers.bulk_edit.rotate")
    def test_rotate(self, m):
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "rotate",
                    "parameters": {"degrees": 90},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(kwargs["degrees"], 90)

    @mock.patch("documents.serialisers.bulk_edit.rotate")
    def test_rotate_invalid_params(self, m):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "rotate",
                    "parameters": {"degrees": "foo"},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "rotate",
                    "parameters": {"degrees": 90.5},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.merge")
    def test_merge(self, m):
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "merge",
                    "parameters": {"metadata_document_id": self.doc3.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(kwargs["metadata_document_id"], self.doc3.id)
        self.assertEqual(kwargs["user"], self.user)

    @mock.patch("documents.serialisers.bulk_edit.merge")
    def test_merge_and_delete_insufficient_permissions(self, m):
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        self.client.force_authenticate(user=user1)

        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "method": "merge",
                    "parameters": {
                        "metadata_document_id": self.doc2.id,
                        "delete_originals": True,
                    },
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
                    "method": "merge",
                    "parameters": {
                        "metadata_document_id": self.doc2.id,
                        "delete_originals": True,
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.serialisers.bulk_edit.merge")
    def test_merge_invalid_parameters(self, m):
        """
        GIVEN:
            - API data for merging documents is called
            - The parameters are invalid
        WHEN:
            - API is called
        THEN:
            - The API fails with a correct error code
        """
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "method": "merge",
                    "parameters": {
                        "delete_originals": "not_boolean",
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.split")
    def test_split(self, m):
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "split",
                    "parameters": {"pages": "1,2-4,5-6,7"},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id])
        self.assertEqual(kwargs["pages"], [[1], [2, 3, 4], [5, 6], [7]])
        self.assertEqual(kwargs["user"], self.user)

    def test_split_invalid_params(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "split",
                    "parameters": {},  # pages not specified
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"pages not specified", response.content)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "split",
                    "parameters": {"pages": "1:7"},  # wrong format
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"invalid pages specified", response.content)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [
                        self.doc1.id,
                        self.doc2.id,
                    ],  # only one document supported
                    "method": "split",
                    "parameters": {"pages": "1-2,3-7"},  # wrong format
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"Split method only supports one document", response.content)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "split",
                    "parameters": {
                        "pages": "1",
                        "delete_originals": "notabool",
                    },  # not a bool
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"delete_originals must be a boolean", response.content)

    @mock.patch("documents.serialisers.bulk_edit.delete_pages")
    def test_delete_pages(self, m):
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "delete_pages",
                    "parameters": {"pages": [1, 2, 3, 4]},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id])
        self.assertEqual(kwargs["pages"], [1, 2, 3, 4])

    def test_delete_pages_invalid_params(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [
                        self.doc1.id,
                        self.doc2.id,
                    ],  # only one document supported
                    "method": "delete_pages",
                    "parameters": {
                        "pages": [1, 2, 3, 4],
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            b"Delete pages method only supports one document",
            response.content,
        )

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "delete_pages",
                    "parameters": {},  # pages not specified
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"pages not specified", response.content)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "delete_pages",
                    "parameters": {"pages": "1-3"},  # not a list
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"pages must be a list", response.content)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "delete_pages",
                    "parameters": {"pages": ["1-3"]},  # not ints
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(b"pages must be a list of integers", response.content)
