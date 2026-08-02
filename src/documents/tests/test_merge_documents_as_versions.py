from unittest import mock

from django.test import TestCase

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
    def test_merges_documents_in_selection_order(
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
        self.assertEqual(source2.version_index, 4)
        self.assertEqual(source1.root_document_id, root.id)
        self.assertEqual(source1.version_index, 5)
        self.assertIsNone(source1.archive_serial_number)
        self.assertIsNone(source2.archive_serial_number)
        self.assertGreater(root.modified, original_modified)
        self.assertEqual(existing_version.root_document_id, root.id)

        batch = get_backend_mock.return_value.batch_update.return_value.__enter__.return_value
        self.assertEqual(
            [call.args[0] for call in batch.remove.call_args_list],
            [source2.id, source1.id],
        )
        bulk_update_mock.assert_called_once_with(
            kwargs={"document_ids": [root.id]},
            headers={"trigger_source": "system"},
        )
        status_manager_mock.return_value.send_documents_deleted.assert_called_once_with(
            [source2.id, source1.id],
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
