from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from documents.admin import DocumentAdmin
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestDocumentAdmin(DirectoriesMixin, TestCase):

    def setUp(self) -> None:
        super(TestDocumentAdmin, self).setUp()
        self.doc_admin = DocumentAdmin(model=Document, admin_site=AdminSite())

    @mock.patch("documents.admin.index.add_or_update_document")
    def test_save_model(self, m):
        doc = Document.objects.create(title="test")
        doc.title = "new title"
        self.doc_admin.save_model(None, doc, None, None)
        self.assertEqual(Document.objects.get(id=doc.id).title, "new title")
        m.assert_called_once()

    @mock.patch("documents.admin.index.remove_document")
    def test_delete_model(self, m):
        doc = Document.objects.create(title="test")
        self.doc_admin.delete_model(None, doc)
        self.assertRaises(Document.DoesNotExist, Document.objects.get, id=doc.id)
        m.assert_called_once()

    @mock.patch("documents.admin.index.remove_document")
    def test_delete_queryset(self, m):
        for i in range(42):
            Document.objects.create(title="Many documents with the same title", checksum=f"{i:02}")

        self.assertEqual(Document.objects.count(), 42)

        self.doc_admin.delete_queryset(None, Document.objects.all())

        self.assertEqual(m.call_count, 42)
        self.assertEqual(Document.objects.count(), 0)

    def test_created(self):
        doc = Document.objects.create(title="test", created=timezone.datetime(2020, 4, 12))
        self.assertEqual(self.doc_admin.created_(doc), "2020-04-12")
