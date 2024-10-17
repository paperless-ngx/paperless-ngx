import hashlib
import importlib
import os
import shutil
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import override_settings

from documents.parsers import ParseError
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import TestMigrations

STORAGE_TYPE_GPG = "gpg"

migration_1012_obj = importlib.import_module(
    "documents.migrations.1012_fix_archive_files",
)


def archive_name_from_filename(filename):
    return os.path.splitext(filename)[0] + ".pdf"


def archive_path_old(self):
    if self.filename:
        fname = archive_name_from_filename(self.filename)
    else:
        fname = f"{self.pk:07}.pdf"

    return os.path.join(settings.ARCHIVE_DIR, fname)


def archive_path_new(doc):
    if doc.archive_filename is not None:
        return os.path.join(settings.ARCHIVE_DIR, str(doc.archive_filename))
    else:
        return None


def source_path(doc):
    if doc.filename:
        fname = str(doc.filename)
    else:
        fname = f"{doc.pk:07}{doc.file_type}"
        if doc.storage_type == STORAGE_TYPE_GPG:
            fname += ".gpg"  # pragma: no cover

    return os.path.join(settings.ORIGINALS_DIR, fname)


def thumbnail_path(doc):
    file_name = f"{doc.pk:07}.png"
    if doc.storage_type == STORAGE_TYPE_GPG:
        file_name += ".gpg"

    return os.path.join(settings.THUMBNAIL_DIR, file_name)


def make_test_document(
    document_class,
    title: str,
    mime_type: str,
    original: str,
    original_filename: str,
    archive: str | None = None,
    archive_filename: str | None = None,
):
    doc = document_class()
    doc.filename = original_filename
    doc.title = title
    doc.mime_type = mime_type
    doc.content = "the content, does not matter for this test"
    doc.save()

    shutil.copy2(original, source_path(doc))
    with open(original, "rb") as f:
        doc.checksum = hashlib.md5(f.read()).hexdigest()

    if archive:
        if archive_filename:
            doc.archive_filename = archive_filename
            shutil.copy2(archive, archive_path_new(doc))
        else:
            shutil.copy2(archive, archive_path_old(doc))

        with open(archive, "rb") as f:
            doc.archive_checksum = hashlib.md5(f.read()).hexdigest()

    doc.save()

    Path(thumbnail_path(doc)).touch()

    return doc


simple_jpg = os.path.join(os.path.dirname(__file__), "samples", "simple.jpg")
simple_pdf = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")
simple_pdf2 = os.path.join(
    os.path.dirname(__file__),
    "samples",
    "documents",
    "originals",
    "0000002.pdf",
)
simple_pdf3 = os.path.join(
    os.path.dirname(__file__),
    "samples",
    "documents",
    "originals",
    "0000003.pdf",
)
simple_txt = os.path.join(os.path.dirname(__file__), "samples", "simple.txt")
simple_png = os.path.join(os.path.dirname(__file__), "samples", "simple-noalpha.png")
simple_png2 = os.path.join(os.path.dirname(__file__), "examples", "no-text.png")


@override_settings(FILENAME_FORMAT="")
class TestMigrateArchiveFiles(DirectoriesMixin, FileSystemAssertsMixin, TestMigrations):
    migrate_from = "1006_auto_20201208_2209_squashed_1011_auto_20210101_2340"
    migrate_to = "1012_fix_archive_files"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")

        self.unrelated = make_test_document(
            Document,
            "unrelated",
            "application/pdf",
            simple_pdf3,
            "unrelated.pdf",
            simple_pdf,
        )
        self.no_text = make_test_document(
            Document,
            "no-text",
            "image/png",
            simple_png2,
            "no-text.png",
            simple_pdf,
        )
        self.doc_no_archive = make_test_document(
            Document,
            "no_archive",
            "text/plain",
            simple_txt,
            "no_archive.txt",
        )
        self.clash1 = make_test_document(
            Document,
            "clash",
            "application/pdf",
            simple_pdf,
            "clash.pdf",
            simple_pdf,
        )
        self.clash2 = make_test_document(
            Document,
            "clash",
            "image/jpeg",
            simple_jpg,
            "clash.jpg",
            simple_pdf,
        )
        self.clash3 = make_test_document(
            Document,
            "clash",
            "image/png",
            simple_png,
            "clash.png",
            simple_pdf,
        )
        self.clash4 = make_test_document(
            Document,
            "clash.png",
            "application/pdf",
            simple_pdf2,
            "clash.png.pdf",
            simple_pdf2,
        )

        self.assertEqual(archive_path_old(self.clash1), archive_path_old(self.clash2))
        self.assertEqual(archive_path_old(self.clash1), archive_path_old(self.clash3))
        self.assertNotEqual(
            archive_path_old(self.clash1),
            archive_path_old(self.clash4),
        )

    def testArchiveFilesMigrated(self):
        Document = self.apps.get_model("documents", "Document")

        for doc in Document.objects.all():
            if doc.archive_checksum:
                self.assertIsNotNone(doc.archive_filename)
                self.assertIsFile(archive_path_new(doc))
            else:
                self.assertIsNone(doc.archive_filename)

            with open(source_path(doc), "rb") as f:
                original_checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(original_checksum, doc.checksum)

            if doc.archive_checksum:
                self.assertIsFile(archive_path_new(doc))
                with open(archive_path_new(doc), "rb") as f:
                    archive_checksum = hashlib.md5(f.read()).hexdigest()
                self.assertEqual(archive_checksum, doc.archive_checksum)

        self.assertEqual(
            Document.objects.filter(archive_checksum__isnull=False).count(),
            6,
        )

    def test_filenames(self):
        Document = self.apps.get_model("documents", "Document")
        self.assertEqual(
            Document.objects.get(id=self.unrelated.id).archive_filename,
            "unrelated.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.no_text.id).archive_filename,
            "no-text.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.doc_no_archive.id).archive_filename,
            None,
        )
        self.assertEqual(
            Document.objects.get(id=self.clash1.id).archive_filename,
            f"{self.clash1.id:07}.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash2.id).archive_filename,
            f"{self.clash2.id:07}.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash3.id).archive_filename,
            f"{self.clash3.id:07}.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash4.id).archive_filename,
            "clash.png.pdf",
        )


@override_settings(FILENAME_FORMAT="{correspondent}/{title}")
class TestMigrateArchiveFilesWithFilenameFormat(TestMigrateArchiveFiles):
    def test_filenames(self):
        Document = self.apps.get_model("documents", "Document")
        self.assertEqual(
            Document.objects.get(id=self.unrelated.id).archive_filename,
            "unrelated.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.no_text.id).archive_filename,
            "no-text.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.doc_no_archive.id).archive_filename,
            None,
        )
        self.assertEqual(
            Document.objects.get(id=self.clash1.id).archive_filename,
            "none/clash.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash2.id).archive_filename,
            "none/clash_01.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash3.id).archive_filename,
            "none/clash_02.pdf",
        )
        self.assertEqual(
            Document.objects.get(id=self.clash4.id).archive_filename,
            "clash.png.pdf",
        )


def fake_parse_wrapper(parser, path, mime_type, file_name):
    parser.archive_path = None
    parser.text = "the text"


@override_settings(FILENAME_FORMAT="")
class TestMigrateArchiveFilesErrors(DirectoriesMixin, TestMigrations):
    migrate_from = "1006_auto_20201208_2209_squashed_1011_auto_20210101_2340"
    migrate_to = "1012_fix_archive_files"
    auto_migrate = False

    def test_archive_missing(self):
        Document = self.apps.get_model("documents", "Document")

        doc = make_test_document(
            Document,
            "clash",
            "application/pdf",
            simple_pdf,
            "clash.pdf",
            simple_pdf,
        )
        os.unlink(archive_path_old(doc))

        self.assertRaisesMessage(
            ValueError,
            "does not exist at: ",
            self.performMigration,
        )

    def test_parser_missing(self):
        Document = self.apps.get_model("documents", "Document")

        make_test_document(
            Document,
            "document",
            "invalid/typesss768",
            simple_png,
            "document.png",
            simple_pdf,
        )
        make_test_document(
            Document,
            "document",
            "invalid/typesss768",
            simple_jpg,
            "document.jpg",
            simple_pdf,
        )

        self.assertRaisesMessage(
            ValueError,
            "no parsers are available",
            self.performMigration,
        )

    @mock.patch(f"{__name__}.migration_1012_obj.parse_wrapper")
    def test_parser_error(self, m):
        m.side_effect = ParseError()
        Document = self.apps.get_model("documents", "Document")

        doc1 = make_test_document(
            Document,
            "document",
            "image/png",
            simple_png,
            "document.png",
            simple_pdf,
        )
        doc2 = make_test_document(
            Document,
            "document",
            "application/pdf",
            simple_jpg,
            "document.jpg",
            simple_pdf,
        )

        self.assertIsNotNone(doc1.archive_checksum)
        self.assertIsNotNone(doc2.archive_checksum)

        with self.assertLogs() as capture:
            self.performMigration()

        self.assertEqual(m.call_count, 6)

        self.assertEqual(
            len(
                list(
                    filter(
                        lambda log: "Parse error, will try again in 5 seconds" in log,
                        capture.output,
                    ),
                ),
            ),
            4,
        )

        self.assertEqual(
            len(
                list(
                    filter(
                        lambda log: "Unable to regenerate archive document for ID:"
                        in log,
                        capture.output,
                    ),
                ),
            ),
            2,
        )

        Document = self.apps.get_model("documents", "Document")

        doc1 = Document.objects.get(id=doc1.id)
        doc2 = Document.objects.get(id=doc2.id)

        self.assertIsNone(doc1.archive_checksum)
        self.assertIsNone(doc2.archive_checksum)
        self.assertIsNone(doc1.archive_filename)
        self.assertIsNone(doc2.archive_filename)

    @mock.patch(f"{__name__}.migration_1012_obj.parse_wrapper")
    def test_parser_no_archive(self, m):
        m.side_effect = fake_parse_wrapper

        Document = self.apps.get_model("documents", "Document")

        doc1 = make_test_document(
            Document,
            "document",
            "image/png",
            simple_png,
            "document.png",
            simple_pdf,
        )
        doc2 = make_test_document(
            Document,
            "document",
            "application/pdf",
            simple_jpg,
            "document.jpg",
            simple_pdf,
        )

        with self.assertLogs() as capture:
            self.performMigration()

        self.assertEqual(
            len(
                list(
                    filter(
                        lambda log: "Parser did not return an archive document for document"
                        in log,
                        capture.output,
                    ),
                ),
            ),
            2,
        )

        Document = self.apps.get_model("documents", "Document")

        doc1 = Document.objects.get(id=doc1.id)
        doc2 = Document.objects.get(id=doc2.id)

        self.assertIsNone(doc1.archive_checksum)
        self.assertIsNone(doc2.archive_checksum)
        self.assertIsNone(doc1.archive_filename)
        self.assertIsNone(doc2.archive_filename)


@override_settings(FILENAME_FORMAT="")
class TestMigrateArchiveFilesBackwards(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    TestMigrations,
):
    migrate_from = "1012_fix_archive_files"
    migrate_to = "1006_auto_20201208_2209_squashed_1011_auto_20210101_2340"

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("documents", "Document")

        make_test_document(
            Document,
            "unrelated",
            "application/pdf",
            simple_pdf2,
            "unrelated.txt",
            simple_pdf2,
            "unrelated.pdf",
        )
        make_test_document(
            Document,
            "no_archive",
            "text/plain",
            simple_txt,
            "no_archive.txt",
        )
        make_test_document(
            Document,
            "clash",
            "image/jpeg",
            simple_jpg,
            "clash.jpg",
            simple_pdf,
            "clash_02.pdf",
        )

    def testArchiveFilesReverted(self):
        Document = self.apps.get_model("documents", "Document")

        for doc in Document.objects.all():
            if doc.archive_checksum:
                self.assertIsFile(archive_path_old(doc))
            with open(source_path(doc), "rb") as f:
                original_checksum = hashlib.md5(f.read()).hexdigest()
            self.assertEqual(original_checksum, doc.checksum)

            if doc.archive_checksum:
                self.assertIsFile(archive_path_old(doc))
                with open(archive_path_old(doc), "rb") as f:
                    archive_checksum = hashlib.md5(f.read()).hexdigest()
                self.assertEqual(archive_checksum, doc.archive_checksum)

        self.assertEqual(
            Document.objects.filter(archive_checksum__isnull=False).count(),
            2,
        )


@override_settings(FILENAME_FORMAT="{correspondent}/{title}")
class TestMigrateArchiveFilesBackwardsWithFilenameFormat(
    TestMigrateArchiveFilesBackwards,
):
    pass


@override_settings(FILENAME_FORMAT="")
class TestMigrateArchiveFilesBackwardsErrors(DirectoriesMixin, TestMigrations):
    migrate_from = "1012_fix_archive_files"
    migrate_to = "1006_auto_20201208_2209_squashed_1011_auto_20210101_2340"
    auto_migrate = False

    def test_filename_clash(self):
        Document = self.apps.get_model("documents", "Document")

        self.clashA = make_test_document(
            Document,
            "clash",
            "application/pdf",
            simple_pdf,
            "clash.pdf",
            simple_pdf,
            "clash_02.pdf",
        )
        self.clashB = make_test_document(
            Document,
            "clash",
            "image/jpeg",
            simple_jpg,
            "clash.jpg",
            simple_pdf,
            "clash_01.pdf",
        )

        self.assertRaisesMessage(
            ValueError,
            "would clash with another archive filename",
            self.performMigration,
        )

    def test_filename_exists(self):
        Document = self.apps.get_model("documents", "Document")

        self.clashA = make_test_document(
            Document,
            "clash",
            "application/pdf",
            simple_pdf,
            "clash.pdf",
            simple_pdf,
            "clash.pdf",
        )
        self.clashB = make_test_document(
            Document,
            "clash",
            "image/jpeg",
            simple_jpg,
            "clash.jpg",
            simple_pdf,
            "clash_01.pdf",
        )

        self.assertRaisesMessage(
            ValueError,
            "file already exists.",
            self.performMigration,
        )
