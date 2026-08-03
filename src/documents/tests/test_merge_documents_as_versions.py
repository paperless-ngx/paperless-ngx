import json
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bulk_edit import merge_as_versions
from documents.models import Document
from documents.serialisers import MergeDocumentsAsVersionsSerializer


class TestMergeDocumentsAsVersionsSerializer(TestCase):
    def setUp(self) -> None:
        self.doc1 = Document.objects.create(checksum="A", title="A")
        self.doc2 = Document.objects.create(checksum="B", title="B")
        self.doc3 = Document.objects.create(checksum="C", title="C")

    def test_accepts_selected_root_document(self) -> None:
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                "root_document_id": self.doc2.id,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data,
            {
                "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                "root_document_id": self.doc2.id,
            },
        )

    def test_requires_at_least_two_documents(self) -> None:
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id],
                "root_document_id": self.doc1.id,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "At least two documents are required.",
        )

    def test_requires_root_document_to_be_selected(self) -> None:
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": self.doc3.id,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "root_document_id must be one of the selected documents.",
        )

    def test_rejects_duplicate_documents(self) -> None:
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id, self.doc1.id],
                "root_document_id": self.doc1.id,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("documents", serializer.errors)

    def test_rejects_selected_version(self) -> None:
        version = Document.objects.create(
            checksum="D",
            title="D",
            root_document=self.doc1,
            version_index=1,
        )
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [version.id, self.doc2.id],
                "root_document_id": self.doc2.id,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "Only top-level documents can be merged as versions.",
        )

    def test_rejects_source_document_with_versions(self) -> None:
        Document.objects.create(
            checksum="D",
            title="D",
            root_document=self.doc1,
            version_index=1,
        )
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": self.doc2.id,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "Documents with existing versions cannot be merged into another document.",
        )

    def test_allows_root_document_with_versions(self) -> None:
        Document.objects.create(
            checksum="D",
            title="D",
            root_document=self.doc1,
            version_index=1,
        )
        serializer = MergeDocumentsAsVersionsSerializer(
            data={
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": self.doc1.id,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


class TestMergeDocumentsAsVersions(TestCase):
    @mock.patch("documents.bulk_edit.DocumentsStatusManager")
    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    @mock.patch("documents.search.get_backend")
    def test_merges_documents_in_creation_order(
        self,
        get_backend_mock,
        bulk_update_mock,
        status_manager_mock,
    ) -> None:
        root = Document.objects.create(checksum="A", title="Root")
        existing_version = Document.objects.create(
            checksum="B",
            title="Existing version",
            root_document=root,
            version_index=3,
        )
        source1 = Document.objects.create(
            checksum="C",
            title="Source 1",
            archive_serial_number=1,
        )
        source2 = Document.objects.create(
            checksum="D",
            title="Source 2",
            archive_serial_number=2,
        )
        original_modified = root.modified

        result = merge_as_versions(
            [source2.id, root.id, source1.id],
            root_document_id=root.id,
        )

        self.assertEqual(result, "OK")
        source1.refresh_from_db()
        source2.refresh_from_db()
        root.refresh_from_db()
        self.assertEqual(source2.root_document_id, root.id)
        self.assertEqual(source2.version_index, 5)
        self.assertEqual(source1.root_document_id, root.id)
        self.assertEqual(source1.version_index, 4)
        self.assertIsNone(source1.archive_serial_number)
        self.assertIsNone(source2.archive_serial_number)
        self.assertGreater(root.modified, original_modified)
        self.assertEqual(existing_version.root_document_id, root.id)

        batch = get_backend_mock.return_value.batch_update.return_value.__enter__.return_value
        self.assertEqual(
            [call.args[0] for call in batch.remove.call_args_list],
            [source1.id, source2.id],
        )
        bulk_update_mock.assert_called_once_with(
            kwargs={"document_ids": [root.id]},
            headers={"trigger_source": "system"},
        )
        status_manager_mock.return_value.send_documents_deleted.assert_called_once_with(
            [source1.id, source2.id],
        )

    @mock.patch("documents.bulk_edit.DocumentsStatusManager")
    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    @mock.patch("documents.search.get_backend")
    def test_rejects_source_document_with_versions(
        self,
        get_backend_mock,
        bulk_update_mock,
        status_manager_mock,
    ) -> None:
        source = Document.objects.create(checksum="A", title="Source")
        Document.objects.create(
            checksum="B",
            title="Source version",
            root_document=source,
            version_index=1,
        )
        root = Document.objects.create(checksum="C", title="Root")

        with self.assertRaisesRegex(ValueError, "existing versions"):
            merge_as_versions(
                [source.id, root.id],
                root_document_id=root.id,
            )

        source.refresh_from_db()
        self.assertIsNone(source.root_document_id)
        get_backend_mock.assert_not_called()
        bulk_update_mock.assert_not_called()
        status_manager_mock.assert_not_called()


class TestMergeDocumentsAsVersionsAPI(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="user")
        self.user.user_permissions.add(
            Permission.objects.get(codename="change_document"),
            Permission.objects.get(codename="view_document"),
        )
        self.doc1 = Document.objects.create(
            checksum="A",
            title="A",
            owner=self.user,
        )
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)

    @mock.patch("documents.views.bulk_edit.merge_as_versions")
    def test_merges_documents_as_versions(self, merge_mock) -> None:
        merge_mock.return_value = "OK"
        merge_mock.__name__ = "merge_as_versions"

        response = self.client.post(
            "/api/documents/merge_as_versions/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "root_document_id": self.doc2.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"result": "OK"})
        merge_mock.assert_called_once_with(
            [self.doc1.id, self.doc2.id],
            root_document_id=self.doc2.id,
        )

    @mock.patch("documents.views.bulk_edit.merge_as_versions")
    def test_requires_change_permission(self, merge_mock) -> None:
        merge_mock.__name__ = "merge_as_versions"
        user = User.objects.create_user(username="no-change")
        self.doc1.owner = user
        self.doc1.save()
        self.doc2.owner = user
        self.doc2.save()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/documents/merge_as_versions/",
            {
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": self.doc1.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        merge_mock.assert_not_called()

    @mock.patch("documents.views.bulk_edit.merge_as_versions")
    def test_rejects_unselected_root(self, merge_mock) -> None:
        doc3 = Document.objects.create(
            checksum="C",
            title="C",
            owner=self.user,
        )

        response = self.client.post(
            "/api/documents/merge_as_versions/",
            {
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": doc3.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        merge_mock.assert_not_called()

    @mock.patch("documents.bulk_edit.DocumentsStatusManager")
    @mock.patch("documents.bulk_edit.bulk_update_documents.apply_async")
    @mock.patch("documents.search.get_backend")
    def test_merges_and_returns_documents_as_versions(
        self,
        get_backend_mock,
        bulk_update_mock,
        status_manager_mock,
    ) -> None:
        response = self.client.post(
            "/api/documents/merge_as_versions/",
            {
                "documents": [self.doc1.id, self.doc2.id],
                "root_document_id": self.doc2.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.root_document_id, self.doc2.id)

        detail_response = self.client.get(
            f"/api/documents/{self.doc2.id}/?fields=id,versions",
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        versions = detail_response.data["versions"]
        self.assertEqual(
            {version["id"] for version in versions},
            {self.doc1.id, self.doc2.id},
        )
        self.assertEqual(
            [version["id"] for version in versions if version["is_root"]],
            [self.doc2.id],
        )
        get_backend_mock.assert_called_once()
        bulk_update_mock.assert_called_once()
        status_manager_mock.return_value.send_documents_deleted.assert_called_once_with(
            [self.doc1.id],
        )
