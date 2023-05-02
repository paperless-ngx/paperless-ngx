from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from documents import index
from documents.admin import DocumentAdmin
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestDocumentAdmin(DirectoriesMixin, TestCase):
    def get_document_from_index(self, doc):
        ix = index.open_index()
        with ix.searcher() as searcher:
            return searcher.document(id=doc.id)

    def setUp(self) -> None:
        super().setUp()
        self.doc_admin = DocumentAdmin(model=Document, admin_site=AdminSite())

    def test_save_model(self):
        doc = Document.objects.create(title="test")

        doc.title = "new title"
        self.doc_admin.save_model(None, doc, None, None)
        self.assertEqual(Document.objects.get(id=doc.id).title, "new title")
        self.assertEqual(self.get_document_from_index(doc)["id"], doc.id)

    def test_delete_model(self):
        doc = Document.objects.create(title="test")
        index.add_or_update_document(doc)
        self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_model(None, doc)

        self.assertRaises(Document.DoesNotExist, Document.objects.get, id=doc.id)
        self.assertIsNone(self.get_document_from_index(doc))

    def test_delete_queryset(self):
        docs = []
        for i in range(42):
            doc = Document.objects.create(
                title="Many documents with the same title",
                checksum=f"{i:02}",
            )
            docs.append(doc)
            index.add_or_update_document(doc)

        self.assertEqual(Document.objects.count(), 42)

        for doc in docs:
            self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_queryset(None, Document.objects.all())

        self.assertEqual(Document.objects.count(), 0)

        for doc in docs:
            self.assertIsNone(self.get_document_from_index(doc))

    def test_created(self):
        doc = Document.objects.create(
            title="test",
            created=timezone.make_aware(timezone.datetime(2020, 4, 12)),
        )
        self.assertEqual(self.doc_admin.created_(doc), "2020-04-12")
