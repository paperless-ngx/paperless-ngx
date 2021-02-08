import hashlib
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from documents.sanity_checker import SanityFailedError
from documents.tasks import sanity_check
from documents.tests.utils import DirectoriesMixin, TestMigrations


STORAGE_TYPE_GPG = "gpg"


def archive_name_from_filename_old(filename):
    return os.path.splitext(filename)[0] + ".pdf"


def archive_path_old(self):
    if self.filename:
        fname = archive_name_from_filename_old(self.filename)
    else:
        fname = "{:07}.pdf".format(self.pk)

    return os.path.join(
        settings.ARCHIVE_DIR,
        fname
    )


def archive_name_from_filename_new(filename):
    name, ext = os.path.splitext(filename)
    if ext == ".pdf":
        return filename
    else:
        return filename + ".pdf"


def archive_path_new(self):
    if self.filename:
        fname = archive_name_from_filename_new(self.filename)
    else:
        fname = "{:07}.pdf".format(self.pk)

    return os.path.join(
        settings.ARCHIVE_DIR,
        fname
    )


def source_path(doc):
    if doc.filename:
        fname = str(doc.filename)
    else:
        fname = "{:07}{}".format(doc.pk, doc.file_type)
        if doc.storage_type == STORAGE_TYPE_GPG:
            fname += ".gpg"  # pragma: no cover

    return os.path.join(
        settings.ORIGINALS_DIR,
        fname
    )


def thumbnail_path(doc):
    file_name = "{:07}.png".format(doc.pk)
    if doc.storage_type == STORAGE_TYPE_GPG:
        file_name += ".gpg"

    return os.path.join(
        settings.THUMBNAIL_DIR,
        file_name
    )


def make_test_document(document_class, title: str, filename: str, mime_type: str, original: str, archive: str = None, new: bool = False):
    doc = document_class()
    doc.filename = filename
    doc.title = title
    doc.mime_type = mime_type
    doc.content = "the content, does not matter for this test"

    shutil.copy2(original, source_path(doc))
    with open(original, "rb") as f:
        doc.checksum = hashlib.md5(f.read()).hexdigest()

    if archive:
        if new:
            shutil.copy2(archive, archive_path_new(doc))
        else:
            shutil.copy2(archive, archive_path_old(doc))
        with open(archive, "rb") as f:
            doc.archive_checksum = hashlib.md5(f.read()).hexdigest()

    doc.save()

    Path(thumbnail_path(doc)).touch()

    return doc


@override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
class TestMigrateArchiveFiles(DirectoriesMixin, TestMigrations):

    migrate_from = '1011_auto_20210101_2340'
    migrate_to = '1012_fix_archive_files'

    def setUpBeforeMigration(self, apps):
        simple_jpg = os.path.join(os.path.dirname(__file__), "samples", "simple.jpg")
        simple_pdf = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")
        simple_pdf2 = os.path.join(os.path.dirname(__file__), "samples", "documents", "originals", "0000002.pdf")
        simple_txt = os.path.join(os.path.dirname(__file__), "samples", "simple.txt")
        simple_png = os.path.join(os.path.dirname(__file__), "samples", "simple-noalpha.png")

        Document = apps.get_model("documents", "Document")

        self.doc_unrelated = make_test_document(Document, "unrelated", "unrelated.txt", "application/pdf", simple_pdf2, simple_pdf2)
        self.doc_no_archive = make_test_document(Document, "no_archive", "no_archive.txt", "text/plain", simple_txt)
        self.clashA = make_test_document(Document, "clash", "clash.pdf", "application/pdf", simple_pdf, simple_pdf)
        self.clashB = make_test_document(Document, "clash", "clash.jpg", "image/jpeg", simple_jpg, simple_pdf)
        self.clashC = make_test_document(Document, "clash", "clash.png", "image/png", simple_png, simple_pdf)

        self.assertEqual(archive_path_old(self.clashA), archive_path_old(self.clashB))
        self.assertEqual(archive_path_old(self.clashA), archive_path_old(self.clashC))
        self.assertRaises(SanityFailedError, sanity_check)

    def testArchiveFilesMigrated(self):
        Document = self.apps.get_model('documents', 'Document')

        for doc in Document.objects.all():
            self.assertTrue(os.path.isfile(archive_path_new(self.clashB)))
            with open(source_path(doc), "rb") as f:
                original_checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(original_checksum, doc.checksum)

            if doc.archive_checksum:
                self.assertTrue(os.path.isfile(archive_path_new(doc)))
                with open(archive_path_new(doc), "rb") as f:
                    archive_checksum = hashlib.md5(f.read()).hexdigest()
                self.assertEqual(archive_checksum, doc.archive_checksum)

        self.assertEqual(Document.objects.filter(archive_checksum__isnull=False).count(), 4)

        # this will raise errors when any inconsistencies remain after migration
        sanity_check()


class TestMigrateArchiveFilesBackwards(DirectoriesMixin, TestMigrations):

    migrate_from = '1012_fix_archive_files'
    migrate_to = '1011_auto_20210101_2340'

    def setUpBeforeMigration(self, apps):
        simple_jpg = os.path.join(os.path.dirname(__file__), "samples", "simple.jpg")
        simple_pdf = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")
        simple_pdf2 = os.path.join(os.path.dirname(__file__), "samples", "documents", "originals", "0000002.pdf")
        simple_txt = os.path.join(os.path.dirname(__file__), "samples", "simple.txt")

        Document = apps.get_model("documents", "Document")

        self.doc_unrelated = make_test_document(Document, "unrelated", "unrelated.txt", "application/pdf", simple_pdf2, simple_pdf2, new=True)
        self.doc_no_archive = make_test_document(Document, "no_archive", "no_archive.txt", "text/plain", simple_txt, new=True)
        self.clashB = make_test_document(Document, "clash", "clash.jpg", "image/jpeg", simple_jpg, simple_pdf, new=True)

    def testArchiveFilesReverted(self):
        Document = self.apps.get_model('documents', 'Document')

        for doc in Document.objects.all():
            self.assertTrue(os.path.isfile(archive_path_old(self.clashB)))
            with open(source_path(doc), "rb") as f:
                original_checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(original_checksum, doc.checksum)

            if doc.archive_checksum:
                self.assertTrue(os.path.isfile(archive_path_old(doc)))
                with open(archive_path_old(doc), "rb") as f:
                    archive_checksum = hashlib.md5(f.read()).hexdigest()
                self.assertEqual(archive_checksum, doc.archive_checksum)
