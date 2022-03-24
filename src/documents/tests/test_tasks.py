import os
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from documents import tasks
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag
from documents.sanity_checker import SanityCheckFailedException
from documents.sanity_checker import SanityCheckMessages
from documents.tests.utils import DirectoriesMixin

from PIL import Image
import tempfile


class TestTasks(DirectoriesMixin, TestCase):
    def test_index_reindex(self):
        Document.objects.create(
            title="test",
            content="my document",
            checksum="wow",
            added=timezone.now(),
            created=timezone.now(),
            modified=timezone.now(),
        )

        tasks.index_reindex()

    def test_index_optimize(self):
        Document.objects.create(
            title="test",
            content="my document",
            checksum="wow",
            added=timezone.now(),
            created=timezone.now(),
            modified=timezone.now(),
        )

        tasks.index_optimize()

    @mock.patch("documents.tasks.load_classifier")
    def test_train_classifier_no_auto_matching(self, load_classifier):
        tasks.train_classifier()
        load_classifier.assert_not_called()

    @mock.patch("documents.tasks.load_classifier")
    def test_train_classifier_with_auto_tag(self, load_classifier):
        load_classifier.return_value = None
        Tag.objects.create(matching_algorithm=Tag.MATCH_AUTO, name="test")
        tasks.train_classifier()
        load_classifier.assert_called_once()
        self.assertFalse(os.path.isfile(settings.MODEL_FILE))

    @mock.patch("documents.tasks.load_classifier")
    def test_train_classifier_with_auto_type(self, load_classifier):
        load_classifier.return_value = None
        DocumentType.objects.create(matching_algorithm=Tag.MATCH_AUTO, name="test")
        tasks.train_classifier()
        load_classifier.assert_called_once()
        self.assertFalse(os.path.isfile(settings.MODEL_FILE))

    @mock.patch("documents.tasks.load_classifier")
    def test_train_classifier_with_auto_correspondent(self, load_classifier):
        load_classifier.return_value = None
        Correspondent.objects.create(matching_algorithm=Tag.MATCH_AUTO, name="test")
        tasks.train_classifier()
        load_classifier.assert_called_once()
        self.assertFalse(os.path.isfile(settings.MODEL_FILE))

    def test_train_classifier(self):
        c = Correspondent.objects.create(matching_algorithm=Tag.MATCH_AUTO, name="test")
        doc = Document.objects.create(correspondent=c, content="test", title="test")
        self.assertFalse(os.path.isfile(settings.MODEL_FILE))

        tasks.train_classifier()
        self.assertTrue(os.path.isfile(settings.MODEL_FILE))
        mtime = os.stat(settings.MODEL_FILE).st_mtime

        tasks.train_classifier()
        self.assertTrue(os.path.isfile(settings.MODEL_FILE))
        mtime2 = os.stat(settings.MODEL_FILE).st_mtime
        self.assertEqual(mtime, mtime2)

        doc.content = "test2"
        doc.save()
        tasks.train_classifier()
        self.assertTrue(os.path.isfile(settings.MODEL_FILE))
        mtime3 = os.stat(settings.MODEL_FILE).st_mtime
        self.assertNotEqual(mtime2, mtime3)

    def test_barcode_reader(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t.pbm"
        )
        img = Image.open(test_file)
        self.assertEqual(tasks.barcode_reader(img), ["b'PATCHT'"])

    def test_barcode_reader2(self):
        test_file = os.path.join(os.path.dirname(__file__), "samples", "simple.png")
        img = Image.open(test_file)
        self.assertEqual(tasks.barcode_reader(img), [])

    def test_scan_file_for_separating_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t.pdf"
        )
        pages = tasks.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    def test_scan_file_for_separating_barcodes2(self):
        test_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")
        pages = tasks.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [])

    def test_scan_file_for_separating_barcodes3(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t-middle.pdf"
        )
        pages = tasks.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [1])

    def test_separate_pages(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t-middle.pdf"
        )
        pages = tasks.separate_pages(test_file, [1])
        self.assertEqual(len(pages), 2)

    def test_save_to_dir(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t.pdf"
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        tasks.save_to_dir(test_file, tempdir)
        target_file = os.path.join(tempdir, "patch-code-t.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_save_to_dir2(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t.pdf"
        )
        nonexistingdir = "/nowhere"
        if os.path.isdir(nonexistingdir):
            self.skipTest("non-existing dir exists")
        else:
            with self.assertLogs("paperless.tasks", level="WARNING") as cm:
                tasks.save_to_dir(test_file, nonexistingdir)
            self.assertEqual(
                cm.output,
                [
                    f"WARNING:paperless.tasks:{str(test_file)} or {str(nonexistingdir)} don't exist."
                ],
            )

    def test_barcode_splitter(self):
        test_file = os.path.join(
            os.path.dirname(__file__), "samples", "patch-code-t-middle.pdf"
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        separators = tasks.scan_file_for_separating_barcodes(test_file)
        self.assertTrue(separators != [])
        document_list = tasks.separate_pages(test_file, separators)
        self.assertTrue(document_list != [])
        for document in document_list:
            tasks.save_to_dir(document, tempdir)
        target_file1 = os.path.join(tempdir, "patch-code-t-middle_document_0.pdf")
        target_file2 = os.path.join(tempdir, "patch-code-t-middle_document_1.pdf")
        self.assertTrue(os.path.isfile(target_file1))
        self.assertTrue(os.path.isfile(target_file2))

    @mock.patch("documents.tasks.sanity_checker.check_sanity")
    def test_sanity_check_success(self, m):
        m.return_value = SanityCheckMessages()
        self.assertEqual(tasks.sanity_check(), "No issues detected.")
        m.assert_called_once()

    @mock.patch("documents.tasks.sanity_checker.check_sanity")
    def test_sanity_check_error(self, m):
        messages = SanityCheckMessages()
        messages.error("Some error")
        m.return_value = messages
        self.assertRaises(SanityCheckFailedException, tasks.sanity_check)
        m.assert_called_once()

    @mock.patch("documents.tasks.sanity_checker.check_sanity")
    def test_sanity_check_warning(self, m):
        messages = SanityCheckMessages()
        messages.warning("Some warning")
        m.return_value = messages
        self.assertEqual(
            tasks.sanity_check(),
            "Sanity check exited with warnings. See log.",
        )
        m.assert_called_once()

    @mock.patch("documents.tasks.sanity_checker.check_sanity")
    def test_sanity_check_info(self, m):
        messages = SanityCheckMessages()
        messages.info("Some info")
        m.return_value = messages
        self.assertEqual(
            tasks.sanity_check(),
            "Sanity check exited with infos. See log.",
        )
        m.assert_called_once()

    def test_bulk_update_documents(self):
        doc1 = Document.objects.create(
            title="test",
            content="my document",
            checksum="wow",
            added=timezone.now(),
            created=timezone.now(),
            modified=timezone.now(),
        )

        tasks.bulk_update_documents([doc1.pk])
