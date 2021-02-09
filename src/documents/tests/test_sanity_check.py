import os
import shutil
from pathlib import Path

import filelock
from django.conf import settings
from django.test import TestCase

from documents.models import Document
from documents.sanity_checker import check_sanity, SanityFailedError
from documents.tests.utils import DirectoriesMixin


class TestSanityCheck(DirectoriesMixin, TestCase):

    def make_test_data(self):

        with filelock.FileLock(settings.MEDIA_LOCK):
            # just make sure that the lockfile is present.
            shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "originals", "0000001.pdf"), os.path.join(self.dirs.originals_dir, "0000001.pdf"))
            shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "archive", "0000001.pdf"), os.path.join(self.dirs.archive_dir, "0000001.pdf"))
            shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "thumbnails", "0000001.png"), os.path.join(self.dirs.thumbnail_dir, "0000001.png"))

        return Document.objects.create(title="test", checksum="42995833e01aea9b3edee44bbfdd7ce1", archive_checksum="62acb0bcbfbcaa62ca6ad3668e4e404b", content="test", pk=1, filename="0000001.pdf", mime_type="application/pdf", archive_filename="0000001.pdf")

    def test_no_docs(self):
        self.assertEqual(len(check_sanity()), 0)

    def test_success(self):
        self.make_test_data()
        self.assertEqual(len(check_sanity()), 0)

    def test_no_thumbnail(self):
        doc = self.make_test_data()
        os.remove(doc.thumbnail_path)
        self.assertEqual(len(check_sanity()), 1)

    def test_thumbnail_no_access(self):
        doc = self.make_test_data()
        os.chmod(doc.thumbnail_path, 0o000)
        self.assertEqual(len(check_sanity()), 1)
        os.chmod(doc.thumbnail_path, 0o777)

    def test_no_original(self):
        doc = self.make_test_data()
        os.remove(doc.source_path)
        self.assertEqual(len(check_sanity()), 1)

    def test_original_no_access(self):
        doc = self.make_test_data()
        os.chmod(doc.source_path, 0o000)
        self.assertEqual(len(check_sanity()), 1)
        os.chmod(doc.source_path, 0o777)

    def test_original_checksum_mismatch(self):
        doc = self.make_test_data()
        doc.checksum = "WOW"
        doc.save()
        self.assertEqual(len(check_sanity()), 1)

    def test_no_archive(self):
        doc = self.make_test_data()
        os.remove(doc.archive_path)
        self.assertEqual(len(check_sanity()), 1)

    def test_archive_no_access(self):
        doc = self.make_test_data()
        os.chmod(doc.archive_path, 0o000)
        self.assertEqual(len(check_sanity()), 1)
        os.chmod(doc.archive_path, 0o777)

    def test_archive_checksum_mismatch(self):
        doc = self.make_test_data()
        doc.archive_checksum = "WOW"
        doc.save()
        self.assertEqual(len(check_sanity()), 1)

    def test_empty_content(self):
        doc = self.make_test_data()
        doc.content = ""
        doc.save()
        self.assertEqual(len(check_sanity()), 1)

    def test_orphaned_file(self):
        doc = self.make_test_data()
        Path(self.dirs.originals_dir, "orphaned").touch()
        self.assertEqual(len(check_sanity()), 1)

    def test_all(self):
        Document.objects.create(title="test", checksum="dgfhj", archive_checksum="dfhg", content="", pk=1, filename="0000001.pdf")
        string = str(SanityFailedError(check_sanity()))
