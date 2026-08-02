from django.test import TestCase

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
