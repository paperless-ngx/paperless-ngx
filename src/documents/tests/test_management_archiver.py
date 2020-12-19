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
        return Document.objects.create(checksum="A", title="A", content="first document", mime_type="application/pdf")

    def test_archiver(self):

        doc = self.make_models()
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"))

        call_command('document_archiver')

    def test_handle_document(self):

        doc = self.make_models()
        shutil.copy(sample_file, os.path.join(self.dirs.originals_dir, f"{doc.id:07}.pdf"))

        handle_document(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertTrue(os.path.isfile(doc.archive_path))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(filecmp.cmp(sample_file, doc.source_path))
