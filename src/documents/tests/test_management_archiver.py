import filecmp
import os
import shutil

from django.core.management import call_command
from django.test import TestCase

from documents.management.commands.document_archiver import handle_document
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


sample_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")


class TestArchiver(DirectoriesMixin, TestCase):

    def make_models(self):
        self.d1 = Document.objects.create(checksum="A", title="A", content="first document", pk=1, mime_type="application/pdf")
        #self.d2 = Document.objects.create(checksum="B", title="B", content="second document")
        #self.d3 = Document.objects.create(checksum="C", title="C", content="unrelated document")

    def test_archiver(self):

        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, "0000001.pdf"))
        self.make_models()

        call_command('document_archiver')

    def test_handle_document(self):

        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, "0000001.pdf"))
        self.make_models()

        handle_document(self.d1)

        doc = Document.objects.get(id=self.d1.id)

        self.assertIsNotNone(doc.checksum)
        self.assertTrue(os.path.isfile(doc.archive_path))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(filecmp.cmp(sample_file, doc.source_path))
