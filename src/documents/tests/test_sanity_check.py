import logging
import shutil
from pathlib import Path

import filelock
from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from documents.models import Document
from documents.sanity_checker import check_sanity
from documents.tests.utils import DirectoriesMixin


class TestSanityCheck(DirectoriesMixin, TestCase):
    def make_test_data(self):
        with filelock.FileLock(settings.MEDIA_LOCK):
            # just make sure that the lockfile is present.
            shutil.copy(
                (
                    Path(__file__).parent
                    / "samples"
                    / "documents"
                    / "originals"
                    / "0000001.pdf"
                ),
                Path(self.dirs.originals_dir) / "0000001.pdf",
            )
            shutil.copy(
                (
                    Path(__file__).parent
                    / "samples"
                    / "documents"
                    / "archive"
                    / "0000001.pdf"
                ),
                Path(self.dirs.archive_dir) / "0000001.pdf",
            )
            shutil.copy(
                (
                    Path(__file__).parent
                    / "samples"
                    / "documents"
                    / "thumbnails"
                    / "0000001.webp"
                ),
                Path(self.dirs.thumbnail_dir) / "0000001.webp",
            )

        return Document.objects.create(
            title="test",
            checksum="42995833e01aea9b3edee44bbfdd7ce1",
            archive_checksum="62acb0bcbfbcaa62ca6ad3668e4e404b",
            content="test",
            pk=1,
            filename="0000001.pdf",
            mime_type="application/pdf",
            archive_filename="0000001.pdf",
        )

    def assertSanityError(self, doc: Document, messageRegex) -> None:
        messages = check_sanity()
        self.assertTrue(messages.has_error)
        with self.assertLogs() as capture:
            messages.log_messages()
            self.assertEqual(
                capture.records[0].message,
                f"Detected following issue(s) with document #{doc.pk}, titled {doc.title}",
            )
            self.assertRegex(capture.records[1].message, messageRegex)

    def test_no_issues(self) -> None:
        self.make_test_data()
        messages = check_sanity()
        self.assertFalse(messages.has_error)
        self.assertFalse(messages.has_warning)
        with self.assertLogs() as capture:
            messages.log_messages()
            self.assertEqual(len(capture.output), 1)
            self.assertEqual(capture.records[0].levelno, logging.INFO)
            self.assertEqual(
                capture.records[0].message,
                "Sanity checker detected no issues.",
            )

    def test_no_docs(self) -> None:
        self.assertEqual(len(check_sanity()), 0)

    def test_success(self) -> None:
        self.make_test_data()
        self.assertEqual(len(check_sanity()), 0)

    def test_no_thumbnail(self) -> None:
        doc = self.make_test_data()
        Path(doc.thumbnail_path).unlink()
        self.assertSanityError(doc, "Thumbnail of document does not exist")

    def test_thumbnail_no_access(self) -> None:
        doc = self.make_test_data()
        Path(doc.thumbnail_path).chmod(0o000)
        self.assertSanityError(doc, "Cannot read thumbnail file of document")
        Path(doc.thumbnail_path).chmod(0o777)

    def test_no_original(self) -> None:
        doc = self.make_test_data()
        Path(doc.source_path).unlink()
        self.assertSanityError(doc, "Original of document does not exist.")

    def test_original_no_access(self) -> None:
        doc = self.make_test_data()
        Path(doc.source_path).chmod(0o000)
        self.assertSanityError(doc, "Cannot read original file of document")
        Path(doc.source_path).chmod(0o777)

    def test_original_checksum_mismatch(self) -> None:
        doc = self.make_test_data()
        doc.checksum = "WOW"
        doc.save()
        self.assertSanityError(doc, "Checksum mismatch. Stored: WOW, actual: ")

    def test_no_archive(self) -> None:
        doc = self.make_test_data()
        Path(doc.archive_path).unlink()
        self.assertSanityError(doc, "Archived version of document does not exist.")

    def test_archive_no_access(self) -> None:
        doc = self.make_test_data()
        Path(doc.archive_path).chmod(0o000)
        self.assertSanityError(doc, "Cannot read archive file of document")
        Path(doc.archive_path).chmod(0o777)

    def test_archive_checksum_mismatch(self) -> None:
        doc = self.make_test_data()
        doc.archive_checksum = "WOW"
        doc.save()
        self.assertSanityError(doc, "Checksum mismatch of archived document")

    def test_empty_content(self) -> None:
        doc = self.make_test_data()
        doc.content = ""
        doc.save()
        messages = check_sanity()
        self.assertFalse(messages.has_error)
        self.assertFalse(messages.has_warning)
        self.assertEqual(len(messages), 1)
        self.assertRegex(
            messages[doc.pk][0]["message"],
            "Document contains no OCR data",
        )

    def test_orphaned_file(self) -> None:
        self.make_test_data()
        Path(self.dirs.originals_dir, "orphaned").touch()
        messages = check_sanity()
        self.assertTrue(messages.has_warning)
        self.assertRegex(
            messages._messages[None][0]["message"],
            "Orphaned file in media dir",
        )

    @override_settings(
        APP_LOGO="logo/logo.png",
    )
    def test_ignore_logo(self) -> None:
        self.make_test_data()
        logo_dir = Path(self.dirs.media_dir, "logo")
        logo_dir.mkdir(parents=True, exist_ok=True)
        Path(self.dirs.media_dir, "logo", "logo.png").touch()
        messages = check_sanity()
        self.assertFalse(messages.has_warning)

    def test_ignore_ignorable_files(self) -> None:
        self.make_test_data()
        Path(self.dirs.media_dir, ".DS_Store").touch()
        Path(self.dirs.media_dir, "desktop.ini").touch()
        messages = check_sanity()
        self.assertFalse(messages.has_warning)

    def test_archive_filename_no_checksum(self) -> None:
        doc = self.make_test_data()
        doc.archive_checksum = None
        doc.save()
        self.assertSanityError(doc, "has an archive file, but its checksum is missing.")

    def test_archive_checksum_no_filename(self) -> None:
        doc = self.make_test_data()
        doc.archive_filename = None
        doc.save()
        self.assertSanityError(
            doc,
            "has an archive file checksum, but no archive filename.",
        )
