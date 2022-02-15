from django.test import TestCase

from documents import index
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestAutoComplete(DirectoriesMixin, TestCase):

    def test_auto_complete(self):

        doc1 = Document.objects.create(title="doc1", checksum="A", content="test test2 test3")
        doc2 = Document.objects.create(title="doc2", checksum="B", content="test test2")
        doc3 = Document.objects.create(title="doc3", checksum="C", content="test2")

        index.add_or_update_document(doc1)
        index.add_or_update_document(doc2)
        index.add_or_update_document(doc3)

        ix = index.open_index()

        self.assertListEqual(index.autocomplete(ix, "tes"), [b"test3", b"test", b"test2"])
        self.assertListEqual(index.autocomplete(ix, "tes", limit=3), [b"test3", b"test", b"test2"])
        self.assertListEqual(index.autocomplete(ix, "tes", limit=1), [b"test3"])
        self.assertListEqual(index.autocomplete(ix, "tes", limit=0), [])
