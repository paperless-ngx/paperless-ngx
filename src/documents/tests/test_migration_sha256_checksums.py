import hashlib
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.test import override_settings

from documents.tests.utils import TestMigrations


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestSha256ChecksumDataMigration(TestMigrations):
    """recompute_checksums correctly updates document checksums from MD5 to SHA256."""

    migrate_from = "0015_document_version_index_and_more"
    migrate_to = "0016_sha256_checksums"
    reset_sequences = True

    ORIGINAL_CONTENT = b"original file content for sha256 migration test"
    ARCHIVE_CONTENT = b"archive file content for sha256 migration test"

    def setUpBeforeMigration(self, apps) -> None:
        self._originals_dir = Path(tempfile.mkdtemp())
        self._archive_dir = Path(tempfile.mkdtemp())
        self._settings_override = override_settings(
            ORIGINALS_DIR=self._originals_dir,
            ARCHIVE_DIR=self._archive_dir,
        )
        self._settings_override.enable()
        Document = apps.get_model("documents", "Document")

        # doc1: original file present, no archive
        (settings.ORIGINALS_DIR / "doc1.txt").write_bytes(self.ORIGINAL_CONTENT)
        self.doc1_id = Document.objects.create(
            title="Doc 1",
            mime_type="text/plain",
            filename="doc1.txt",
            checksum="a" * 32,
        ).pk

        # doc2: original and archive both present
        (settings.ORIGINALS_DIR / "doc2.txt").write_bytes(self.ORIGINAL_CONTENT)
        (settings.ARCHIVE_DIR / "doc2.pdf").write_bytes(self.ARCHIVE_CONTENT)
        self.doc2_id = Document.objects.create(
            title="Doc 2",
            mime_type="text/plain",
            filename="doc2.txt",
            checksum="b" * 32,
            archive_filename="doc2.pdf",
            archive_checksum="c" * 32,
        ).pk

        # doc3: original file missing — checksum must stay unchanged
        self.doc3_id = Document.objects.create(
            title="Doc 3",
            mime_type="text/plain",
            filename="missing_original.txt",
            checksum="d" * 32,
        ).pk

        # doc4: original present, archive_filename set but archive file missing
        (settings.ORIGINALS_DIR / "doc4.txt").write_bytes(self.ORIGINAL_CONTENT)
        self.doc4_id = Document.objects.create(
            title="Doc 4",
            mime_type="text/plain",
            filename="doc4.txt",
            checksum="e" * 32,
            archive_filename="missing_archive.pdf",
            archive_checksum="f" * 32,
        ).pk

        # doc5: original present, archive_filename is None — archive_checksum must stay null
        (settings.ORIGINALS_DIR / "doc5.txt").write_bytes(self.ORIGINAL_CONTENT)
        self.doc5_id = Document.objects.create(
            title="Doc 5",
            mime_type="text/plain",
            filename="doc5.txt",
            checksum="0" * 32,
            archive_filename=None,
            archive_checksum=None,
        ).pk

    def _fixture_teardown(self) -> None:
        super()._fixture_teardown()
        # Django's SQLite backend returns [] from sequence_reset_sql(), so
        # reset_sequences=True flushes rows but never clears sqlite_sequence.
        # Explicitly delete the entry so subsequent tests start from pk=1.
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sqlite_sequence WHERE name='documents_document'",
                )

    def tearDown(self) -> None:
        super().tearDown()
        self._settings_override.disable()
        shutil.rmtree(self._originals_dir, ignore_errors=True)
        shutil.rmtree(self._archive_dir, ignore_errors=True)

    def test_original_checksum_updated_to_sha256_when_file_exists(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        doc = Document.objects.get(pk=self.doc1_id)
        self.assertEqual(doc.checksum, _sha256(self.ORIGINAL_CONTENT))

    def test_both_checksums_updated_when_original_and_archive_exist(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        doc = Document.objects.get(pk=self.doc2_id)
        self.assertEqual(doc.checksum, _sha256(self.ORIGINAL_CONTENT))
        self.assertEqual(doc.archive_checksum, _sha256(self.ARCHIVE_CONTENT))

    def test_checksum_unchanged_when_original_file_missing(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        doc = Document.objects.get(pk=self.doc3_id)
        self.assertEqual(doc.checksum, "d" * 32)

    def test_archive_checksum_unchanged_when_archive_file_missing(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        doc = Document.objects.get(pk=self.doc4_id)
        # Original was updated (file exists)
        self.assertEqual(doc.checksum, _sha256(self.ORIGINAL_CONTENT))
        # Archive was not updated (file missing)
        self.assertEqual(doc.archive_checksum, "f" * 32)

    def test_archive_checksum_stays_null_when_no_archive_filename(self) -> None:
        Document = self.apps.get_model("documents", "Document")
        doc = Document.objects.get(pk=self.doc5_id)
        self.assertIsNone(doc.archive_checksum)
