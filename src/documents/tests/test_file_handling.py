import datetime
import logging
import os
import tempfile
from pathlib import Path
from unittest import mock

from auditlog.context import disable_auditlog
from django.conf import settings
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from documents.file_handling import create_source_path_directory
from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.tasks import empty_trash
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin


class TestFileHandling(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @override_settings(FILENAME_FORMAT="")
    def test_generate_source_filename(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(generate_filename(document), f"{document.pk:07d}.pdf")

        document.storage_type = Document.STORAGE_TYPE_GPG
        self.assertEqual(
            generate_filename(document),
            f"{document.pk:07d}.pdf.gpg",
        )

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Test default source_path
        self.assertEqual(
            document.source_path,
            settings.ORIGINALS_DIR / f"{document.pk:07d}.pdf",
        )

        document.filename = generate_filename(document)

        # Ensure that filename is properly generated
        self.assertEqual(document.filename, "none/none.pdf")

        # Enable encryption and check again
        document.storage_type = Document.STORAGE_TYPE_GPG
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none.pdf.gpg")

        document.save()

        # test that creating dirs for the source_path creates the correct directory
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()
        self.assertIsDir(os.path.join(settings.ORIGINALS_DIR, "none"))

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertIsDir(
            settings.ORIGINALS_DIR / "test",
        )
        self.assertIsNotDir(
            settings.ORIGINALS_DIR / "none",
        )
        self.assertIsFile(
            settings.ORIGINALS_DIR / "test" / "test.pdf.gpg",
        )

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming_missing_permissions(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none.pdf")
        create_source_path_directory(document.source_path)
        document.source_path.touch()

        # Test source_path
        self.assertEqual(
            document.source_path,
            settings.ORIGINALS_DIR / "none" / "none.pdf",
        )

        # Make the folder read- and execute-only (no writing and no renaming)
        os.chmod(os.path.join(settings.ORIGINALS_DIR, "none"), 0o555)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertIsFile(
            settings.ORIGINALS_DIR / "none" / "none.pdf",
        )
        self.assertEqual(document.filename, "none/none.pdf")

        os.chmod(os.path.join(settings.ORIGINALS_DIR, "none"), 0o777)

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming_database_error(self):
        Document.objects.create(
            mime_type="application/pdf",
            storage_type=Document.STORAGE_TYPE_UNENCRYPTED,
            checksum="AAAAA",
        )

        document = Document()
        document.mime_type = "application/pdf"
        document.checksum = "BBBBB"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none.pdf")
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Test source_path
        self.assertIsFile(document.source_path)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]

        with (
            mock.patch(
                "documents.signals.handlers.Document.global_objects.filter",
            ) as m,
            disable_auditlog(),
        ):
            m.side_effect = DatabaseError()
            document.save()

            # Check proper handling of files
            self.assertIsFile(document.source_path)
            self.assertIsFile(
                os.path.join(settings.ORIGINALS_DIR, "none/none.pdf"),
            )
            self.assertEqual(document.filename, "none/none.pdf")

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_document_delete(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        document.save()
        self.assertEqual(document.filename, "none/none.pdf")

        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Ensure file deletion after delete
        document.delete()
        empty_trash([document.pk])
        self.assertIsNotFile(
            os.path.join(settings.ORIGINALS_DIR, "none", "none.pdf"),
        )
        self.assertIsNotDir(os.path.join(settings.ORIGINALS_DIR, "none"))

    @override_settings(
        FILENAME_FORMAT="{correspondent}/{correspondent}",
        EMPTY_TRASH_DIR=tempfile.mkdtemp(),
    )
    def test_document_delete_trash_dir(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        document.save()
        self.assertEqual(document.filename, "none/none.pdf")

        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Ensure file was moved to trash after delete
        self.assertIsNotFile(os.path.join(settings.EMPTY_TRASH_DIR, "none", "none.pdf"))
        document.delete()
        empty_trash([document.pk])
        self.assertIsNotFile(
            os.path.join(settings.ORIGINALS_DIR, "none", "none.pdf"),
        )
        self.assertIsNotDir(os.path.join(settings.ORIGINALS_DIR, "none"))
        self.assertIsFile(os.path.join(settings.EMPTY_TRASH_DIR, "none.pdf"))
        self.assertIsNotFile(os.path.join(settings.EMPTY_TRASH_DIR, "none_01.pdf"))

        # Create an identical document and ensure it is trashed under a new name
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()
        document.filename = generate_filename(document)
        document.save()
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()
        document.delete()
        empty_trash([document.pk])
        self.assertIsFile(os.path.join(settings.EMPTY_TRASH_DIR, "none_01.pdf"))

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_document_delete_nofile(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        document.delete()
        empty_trash([document.pk])

    @override_settings(FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_directory_not_empty(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none.pdf")

        create_source_path_directory(document.source_path)

        document.source_path.touch()
        important_file = document.source_path.with_suffix(".test")
        important_file.touch()

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertIsDir(os.path.join(settings.ORIGINALS_DIR, "test"))
        self.assertIsDir(os.path.join(settings.ORIGINALS_DIR, "none"))
        self.assertIsFile(important_file)

    @override_settings(FILENAME_FORMAT="{document_type} - {title}")
    def test_document_type(self):
        dt = DocumentType.objects.create(name="my_doc_type")
        d = Document.objects.create(title="the_doc", mime_type="application/pdf")

        self.assertEqual(generate_filename(d), "none - the_doc.pdf")

        d.document_type = dt

        self.assertEqual(generate_filename(d), "my_doc_type - the_doc.pdf")

    @override_settings(FILENAME_FORMAT="{asn} - {title}")
    def test_asn(self):
        d1 = Document.objects.create(
            title="the_doc",
            mime_type="application/pdf",
            archive_serial_number=652,
            checksum="A",
        )
        d2 = Document.objects.create(
            title="the_doc",
            mime_type="application/pdf",
            archive_serial_number=None,
            checksum="B",
        )
        self.assertEqual(generate_filename(d1), "652 - the_doc.pdf")
        self.assertEqual(generate_filename(d2), "none - the_doc.pdf")

    @override_settings(FILENAME_FORMAT="{title} {tag_list}")
    def test_tag_list(self):
        doc = Document.objects.create(title="doc1", mime_type="application/pdf")
        doc.tags.create(name="tag2")
        doc.tags.create(name="tag1")

        self.assertEqual(generate_filename(doc), "doc1 tag1,tag2.pdf")

        doc = Document.objects.create(
            title="doc2",
            checksum="B",
            mime_type="application/pdf",
        )

        self.assertEqual(generate_filename(doc), "doc2.pdf")

    @override_settings(FILENAME_FORMAT="//etc/something/{title}")
    def test_filename_relative(self):
        doc = Document.objects.create(title="doc1", mime_type="application/pdf")
        doc.filename = generate_filename(doc)
        doc.save()

        self.assertEqual(
            doc.source_path,
            settings.ORIGINALS_DIR / "etc" / "something" / "doc1.pdf",
        )

    @override_settings(
        FILENAME_FORMAT="{created_year}-{created_month}-{created_day}",
    )
    def test_created_year_month_day(self):
        d1 = timezone.make_aware(datetime.datetime(2020, 3, 6, 1, 1, 1))
        doc1 = Document.objects.create(
            title="doc1",
            mime_type="application/pdf",
            created=d1,
        )

        self.assertEqual(generate_filename(doc1), "2020-03-06.pdf")

        doc1.created = timezone.make_aware(datetime.datetime(2020, 11, 16, 1, 1, 1))

        self.assertEqual(generate_filename(doc1), "2020-11-16.pdf")

    @override_settings(
        FILENAME_FORMAT="{added_year}-{added_month}-{added_day}",
    )
    def test_added_year_month_day(self):
        d1 = timezone.make_aware(datetime.datetime(232, 1, 9, 1, 1, 1))
        doc1 = Document.objects.create(
            title="doc1",
            mime_type="application/pdf",
            added=d1,
        )

        self.assertEqual(generate_filename(doc1), "232-01-09.pdf")

        doc1.added = timezone.make_aware(datetime.datetime(2020, 11, 16, 1, 1, 1))

        self.assertEqual(generate_filename(doc1), "2020-11-16.pdf")

    @override_settings(
        FILENAME_FORMAT="{correspondent}/{correspondent}/{correspondent}",
    )
    def test_nested_directory_cleanup(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        document.save()
        self.assertEqual(document.filename, "none/none/none.pdf")
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Check proper handling of files
        self.assertIsDir(os.path.join(settings.ORIGINALS_DIR, "none/none"))

        document.delete()
        empty_trash([document.pk])

        self.assertIsNotFile(
            os.path.join(settings.ORIGINALS_DIR, "none/none/none.pdf"),
        )
        self.assertIsNotDir(os.path.join(settings.ORIGINALS_DIR, "none/none"))
        self.assertIsNotDir(os.path.join(settings.ORIGINALS_DIR, "none"))
        self.assertIsDir(settings.ORIGINALS_DIR)

    @override_settings(FILENAME_FORMAT="{doc_pk}")
    def test_format_doc_pk(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

        document.pk = 13579

        self.assertEqual(generate_filename(document), "0013579.pdf")

    @override_settings(FILENAME_FORMAT=None)
    def test_format_none(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    def test_try_delete_empty_directories(self):
        # Create our working directory
        tmp: Path = settings.ORIGINALS_DIR / "test_delete_empty"
        tmp.mkdir(exist_ok=True, parents=True)

        (tmp / "notempty").mkdir(exist_ok=True, parents=True)
        (tmp / "notempty" / "file").touch()
        (tmp / "notempty" / "empty").mkdir(exist_ok=True, parents=True)

        delete_empty_directories(
            os.path.join(tmp, "notempty", "empty"),
            root=settings.ORIGINALS_DIR,
        )
        self.assertIsDir(os.path.join(tmp, "notempty"))
        self.assertIsFile(os.path.join(tmp, "notempty", "file"))
        self.assertIsNotDir(os.path.join(tmp, "notempty", "empty"))

    @override_settings(FILENAME_FORMAT="{% if x is None %}/{title]")
    def test_invalid_format(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    @override_settings(FILENAME_FORMAT="{created__year}")
    def test_invalid_format_key(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    @override_settings(FILENAME_FORMAT="{title}")
    def test_duplicates(self):
        document = Document.objects.create(
            mime_type="application/pdf",
            title="qwe",
            checksum="A",
            pk=1,
        )
        document2 = Document.objects.create(
            mime_type="application/pdf",
            title="qwe",
            checksum="B",
            pk=2,
        )
        Path(document.source_path).touch()
        Path(document2.source_path).touch()
        document.filename = "0000001.pdf"
        document.save()

        self.assertIsFile(document.source_path)
        self.assertEqual(document.filename, "qwe.pdf")

        document2.filename = "0000002.pdf"
        document2.save()

        self.assertIsFile(document.source_path)
        self.assertEqual(document2.filename, "qwe_01.pdf")

        # saving should not change the file names.

        document.save()

        self.assertIsFile(document.source_path)
        self.assertEqual(document.filename, "qwe.pdf")

        document2.save()

        self.assertIsFile(document.source_path)
        self.assertEqual(document2.filename, "qwe_01.pdf")

        document.delete()
        empty_trash([document.pk])

        self.assertIsNotFile(document.source_path)

        # filename free, should remove _01 suffix

        document2.save()

        self.assertIsFile(document.source_path)
        self.assertEqual(document2.filename, "qwe.pdf")

    @override_settings(FILENAME_FORMAT="{title}")
    @mock.patch("documents.signals.handlers.Document.objects.filter")
    @mock.patch("documents.signals.handlers.shutil.move")
    def test_no_move_only_save(self, mock_move, mock_filter):
        """
        GIVEN:
            - A document with a filename
            - The document is saved
            - The filename is not changed
        WHEN:
            - The document is saved
        THEN:
            - The document modified date is updated
            - The document is not moved
        """
        with disable_auditlog():
            doc = Document.objects.create(
                title="document",
                filename="document.pdf",
                archive_filename="document.pdf",
                checksum="A",
                archive_checksum="B",
                mime_type="application/pdf",
            )
            original_modified = doc.modified
            Path(doc.source_path).touch()
            Path(doc.archive_path).touch()

            doc.save()
            doc.refresh_from_db()

            mock_filter.assert_called()
            self.assertNotEqual(original_modified, doc.modified)
            mock_move.assert_not_called()

    @override_settings(
        FILENAME_FORMAT="{{title}}_{{custom_fields|get_cf_value('test')}}",
    )
    @mock.patch("documents.signals.handlers.update_filename_and_move_files")
    def test_select_cf_updated(self, m):
        """
        GIVEN:
            - A document with a select type custom field
        WHEN:
            - The custom field select options are updated
        THEN:
            - The update_filename_and_move_files handler is called and the document filename is updated
        """
        cf = CustomField.objects.create(
            name="test",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={
                "select_options": [
                    {"label": "apple", "id": "abc123"},
                    {"label": "banana", "id": "def456"},
                    {"label": "cherry", "id": "ghi789"},
                ],
            },
        )
        doc = Document.objects.create(
            title="document",
            filename="document.pdf",
            archive_filename="document.pdf",
            checksum="A",
            archive_checksum="B",
            mime_type="application/pdf",
        )
        CustomFieldInstance.objects.create(
            field=cf,
            document=doc,
            value_select="abc123",
        )

        self.assertEqual(generate_filename(doc), "document_apple.pdf")

        # handler should not have been called
        self.assertEqual(m.call_count, 0)
        cf.extra_data = {
            "select_options": [
                {"label": "aubergine", "id": "abc123"},
                {"label": "banana", "id": "def456"},
                {"label": "cherry", "id": "ghi789"},
            ],
        }
        cf.save()
        self.assertEqual(generate_filename(doc), "document_aubergine.pdf")
        # handler should have been called
        self.assertEqual(m.call_count, 1)


class TestFileHandlingWithArchive(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @override_settings(FILENAME_FORMAT=None)
    def test_create_no_format(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            filename="0000001.pdf",
            checksum="A",
            archive_filename="0000001.pdf",
            archive_checksum="B",
        )

        self.assertIsFile(original)
        self.assertIsFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_create_with_format(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )

        self.assertIsNotFile(original)
        self.assertIsNotFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)
        self.assertEqual(
            doc.source_path,
            settings.ORIGINALS_DIR / "none" / "my_doc.pdf",
        )
        self.assertEqual(
            doc.archive_path,
            settings.ARCHIVE_DIR / "none" / "my_doc.pdf",
        )

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_archive_gone(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )

        self.assertIsFile(original)
        self.assertIsNotFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsNotFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_archive_exists(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        existing_archive_file = os.path.join(settings.ARCHIVE_DIR, "none", "my_doc.pdf")
        Path(original).touch()
        Path(archive).touch()
        (settings.ARCHIVE_DIR / "none").mkdir(parents=True, exist_ok=True)
        Path(existing_archive_file).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )

        self.assertIsNotFile(original)
        self.assertIsNotFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)
        self.assertIsFile(existing_archive_file)
        self.assertEqual(doc.archive_filename, "none/my_doc_01.pdf")

    @override_settings(FILENAME_FORMAT="{title}")
    def test_move_original_only(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document_01.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "document.pdf")
        Path(original).touch()
        Path(archive).touch()

        doc = Document.objects.create(
            mime_type="application/pdf",
            title="document",
            filename="document_01.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="document.pdf",
        )

        self.assertEqual(doc.filename, "document.pdf")
        self.assertEqual(doc.archive_filename, "document.pdf")

        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{title}")
    def test_move_archive_only(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "document_01.pdf")
        Path(original).touch()
        Path(archive).touch()

        doc = Document.objects.create(
            mime_type="application/pdf",
            title="document",
            filename="document.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="document_01.pdf",
        )

        self.assertEqual(doc.filename, "document.pdf")
        self.assertEqual(doc.archive_filename, "document.pdf")

        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    @mock.patch("documents.signals.handlers.shutil.move")
    def test_move_archive_error(self, m):
        def fake_rename(src, dst):
            if "archive" in str(src):
                raise OSError
            else:
                os.remove(src)
                Path(dst).touch()

        m.side_effect = fake_rename

        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )

        m.assert_called()
        self.assertIsFile(original)
        self.assertIsFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_file_gone(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        # Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            archive_filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
        )

        self.assertIsNotFile(original)
        self.assertIsFile(archive)
        self.assertIsNotFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    @mock.patch("documents.signals.handlers.shutil.move")
    def test_move_file_error(self, m):
        def fake_rename(src, dst):
            if "original" in str(src):
                raise OSError
            else:
                os.remove(src)
                Path(dst).touch()

        m.side_effect = fake_rename

        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            archive_filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
        )

        m.assert_called()
        self.assertIsFile(original)
        self.assertIsFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="")
    def test_archive_deleted(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )

        self.assertIsFile(original)
        self.assertIsFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)

        doc.delete()
        empty_trash([doc.pk])

        self.assertIsNotFile(original)
        self.assertIsNotFile(archive)
        self.assertIsNotFile(doc.source_path)
        self.assertIsNotFile(doc.archive_path)

    @override_settings(FILENAME_FORMAT="{title}")
    def test_archive_deleted2(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document.webp")
        original2 = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(original2).touch()
        Path(archive).touch()

        doc1 = Document.objects.create(
            mime_type="image/webp",
            title="document",
            filename="document.webp",
            checksum="A",
            archive_checksum="B",
            archive_filename="0000001.pdf",
        )
        doc2 = Document.objects.create(
            mime_type="application/pdf",
            title="0000001",
            filename="0000001.pdf",
            checksum="C",
        )

        self.assertIsFile(doc1.source_path)
        self.assertIsFile(doc1.archive_path)
        self.assertIsFile(doc2.source_path)

        doc2.delete()
        empty_trash([doc2.pk])

        self.assertIsFile(doc1.source_path)
        self.assertIsFile(doc1.archive_path)
        self.assertIsNotFile(doc2.source_path)

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_database_error(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document(
            mime_type="application/pdf",
            title="my_doc",
            filename="0000001.pdf",
            checksum="A",
            archive_filename="0000001.pdf",
            archive_checksum="B",
        )
        with mock.patch(
            "documents.signals.handlers.Document.global_objects.filter",
        ) as m:
            m.side_effect = DatabaseError()
            doc.save()

        self.assertIsFile(original)
        self.assertIsFile(archive)
        self.assertIsFile(doc.source_path)
        self.assertIsFile(doc.archive_path)


class TestFilenameGeneration(DirectoriesMixin, TestCase):
    @override_settings(FILENAME_FORMAT="{title}")
    def test_invalid_characters(self):
        doc = Document.objects.create(
            title="This. is the title.",
            mime_type="application/pdf",
            pk=1,
            checksum="1",
        )
        self.assertEqual(generate_filename(doc), "This. is the title.pdf")

        doc = Document.objects.create(
            title="my\\invalid/../title:yay",
            mime_type="application/pdf",
            pk=2,
            checksum="2",
        )
        self.assertEqual(generate_filename(doc), "my-invalid-..-title-yay.pdf")

    @override_settings(FILENAME_FORMAT="{created}")
    def test_date(self):
        doc = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 5, 21, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
        )
        self.assertEqual(generate_filename(doc), "2020-05-21.pdf")

    def test_dynamic_path(self):
        """
        GIVEN:
            - A document with a defined storage path
        WHEN:
            - the filename is generated for the document
        THEN:
            - the generated filename uses the defined storage path for the document
        """
        doc = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            storage_path=StoragePath.objects.create(path="TestFolder/{{created}}"),
        )
        self.assertEqual(generate_filename(doc), "TestFolder/2020-06-25.pdf")

    def test_dynamic_path_with_none(self):
        """
        GIVEN:
            - A document with a defined storage path
            - The defined storage path uses an undefined field for the document
        WHEN:
            - the filename is generated for the document
        THEN:
            - the generated filename uses the defined storage path for the document
            - the generated filename includes "none" in the place undefined field
        """
        doc = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            storage_path=StoragePath.objects.create(path="{{asn}} - {{created}}"),
        )
        self.assertEqual(generate_filename(doc), "none - 2020-06-25.pdf")

    @override_settings(
        FILENAME_FORMAT_REMOVE_NONE=True,
    )
    def test_dynamic_path_remove_none(self):
        """
        GIVEN:
            - A document with a defined storage path
            - The defined storage path uses an undefined field for the document
            - The setting for removing undefined fields is enabled
        WHEN:
            - the filename is generated for the document
        THEN:
            - the generated filename uses the defined storage path for the document
            - the generated filename does not include "none" in the place undefined field
        """
        sp = StoragePath.objects.create(
            path="TestFolder/{{asn}}/{{created}}",
        )
        doc = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            storage_path=sp,
        )
        self.assertEqual(generate_filename(doc), "TestFolder/2020-06-25.pdf")

        # Special case, undefined variable, then defined at the start of the template
        # This could lead to an absolute path after we remove the leading -none-, but leave the leading /
        # -none-/2020/ -> /2020/
        sp.path = (
            "{{ owner_username }}/{{ created_year }}/{{ correspondent }}/{{ title }}"
        )
        sp.save()
        self.assertEqual(generate_filename(doc), "2020/does not matter.pdf")

    def test_multiple_doc_paths(self):
        """
        GIVEN:
            - Two documents, each with different storage paths
        WHEN:
            - the filename is generated for the documents
        THEN:
            - Each document generated filename uses its storage path
        """
        doc_a = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=4,
            storage_path=StoragePath.objects.create(
                name="sp1",
                path="ThisIsAFolder/{{asn}}/{{created}}",
            ),
        )
        doc_b = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 7, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=5,
            checksum="abcde",
            storage_path=StoragePath.objects.create(
                name="sp2",
                path="SomeImportantNone/{{created}}",
            ),
        )

        self.assertEqual(generate_filename(doc_a), "ThisIsAFolder/4/2020-06-25.pdf")
        self.assertEqual(generate_filename(doc_b), "SomeImportantNone/2020-07-25.pdf")

    @override_settings(
        FILENAME_FORMAT=None,
    )
    def test_no_path_fallback(self):
        """
        GIVEN:
            - Two documents, one with defined storage path, the other not
        WHEN:
            - the filename is generated for the documents
        THEN:
            - Document with defined path uses its format
            - Document without defined path uses the default path
        """
        doc_a = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=4,
        )
        doc_b = Document.objects.create(
            title="does not matter",
            created=timezone.make_aware(datetime.datetime(2020, 7, 25, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=5,
            checksum="abcde",
            storage_path=StoragePath.objects.create(
                name="sp2",
                path="SomeImportantNone/{{created}}",
            ),
        )

        self.assertEqual(generate_filename(doc_a), "0000002.pdf")
        self.assertEqual(generate_filename(doc_b), "SomeImportantNone/2020-07-25.pdf")

    @override_settings(
        FILENAME_FORMAT="{created_year_short}/{created_month_name_short}/{created_month_name}/{title}",
    )
    def test_short_names_created(self):
        doc = Document.objects.create(
            title="The Title",
            created=timezone.make_aware(
                datetime.datetime(1989, 12, 21, 7, 36, 51, 153),
            ),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
        )
        self.assertEqual(generate_filename(doc), "89/Dec/December/The Title.pdf")

    @override_settings(
        FILENAME_FORMAT="{added_year_short}/{added_month_name}/{added_month_name_short}/{title}",
    )
    def test_short_names_added(self):
        doc = Document.objects.create(
            title="The Title",
            added=timezone.make_aware(datetime.datetime(1984, 8, 21, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
        )
        self.assertEqual(generate_filename(doc), "84/August/Aug/The Title.pdf")

    @override_settings(
        FILENAME_FORMAT="{owner_username}/{title}",
    )
    def test_document_owner_string(self):
        """
        GIVEN:
            - Document with an other
            - Document without an owner
            - Filename format string includes owner
        WHEN:
            - Filename is generated for each document
        THEN:
            - Owned document includes username
            - Document without owner returns "none"
        """

        u1 = User.objects.create_user("user1")

        owned_doc = Document.objects.create(
            title="The Title",
            mime_type="application/pdf",
            checksum="2",
            owner=u1,
        )

        no_owner_doc = Document.objects.create(
            title="does matter",
            mime_type="application/pdf",
            checksum="3",
        )

        self.assertEqual(generate_filename(owned_doc), "user1/The Title.pdf")
        self.assertEqual(generate_filename(no_owner_doc), "none/does matter.pdf")

    @override_settings(
        FILENAME_FORMAT="{original_name}",
    )
    def test_document_original_filename(self):
        """
        GIVEN:
            - Document with an original filename
            - Document without an original filename
            - Document which was plain text document
            - Filename format string includes original filename
        WHEN:
            - Filename is generated for each document
        THEN:
            - Document with original name uses it, dropping suffix
            - Document without original name returns "none"
            - Text document returns extension of .txt
            - Text document archive returns extension of .pdf
            - No extensions are doubled
        """
        doc_with_original = Document.objects.create(
            title="does matter",
            mime_type="application/pdf",
            checksum="3",
            original_filename="someepdf.pdf",
        )
        tricky_with_original = Document.objects.create(
            title="does matter",
            mime_type="application/pdf",
            checksum="1",
            original_filename="some pdf with spaces and stuff.pdf",
        )
        no_original = Document.objects.create(
            title="does matter",
            mime_type="application/pdf",
            checksum="2",
        )

        text_doc = Document.objects.create(
            title="does matter",
            mime_type="text/plain",
            checksum="4",
            original_filename="logs.txt",
        )

        self.assertEqual(generate_filename(doc_with_original), "someepdf.pdf")

        self.assertEqual(
            generate_filename(tricky_with_original),
            "some pdf with spaces and stuff.pdf",
        )

        self.assertEqual(generate_filename(no_original), "none.pdf")

        self.assertEqual(generate_filename(text_doc), "logs.txt")
        self.assertEqual(generate_filename(text_doc, archive_filename=True), "logs.pdf")

    @override_settings(
        FILENAME_FORMAT="XX{correspondent}/{title}",
        FILENAME_FORMAT_REMOVE_NONE=True,
    )
    def test_remove_none_not_dir(self):
        """
        GIVEN:
            - A document with & filename format that includes correspondent as part of directory name
            - FILENAME_FORMAT_REMOVE_NONE is True
        WHEN:
            - the filename is generated for the document
        THEN:
            - the missing correspondent is removed but directory structure retained
        """
        document = Document.objects.create(
            title="doc1",
            mime_type="application/pdf",
        )
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "XX/doc1.pdf")

    def test_complex_template_strings(self):
        """
        GIVEN:
            - Storage paths with complex conditionals and logic
        WHEN:
            - Filepath for a document with this storage path is called
        THEN:
            - The filepath is rendered without error
            - The filepath is rendered as a single line string
        """
        sp = StoragePath.objects.create(
            name="sp1",
            path="""
                 somepath/
                 {% if document.checksum == '2' %}
                   some where/{{created}}
                 {% else %}
                   {{added}}
                 {% endif %}
                 /{{ title }}
                 """,
        )

        doc_a = Document.objects.create(
            title="Does Matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
            storage_path=sp,
        )

        self.assertEqual(
            generate_filename(doc_a),
            "somepath/some where/2020-06-25/Does Matter.pdf",
        )
        doc_a.checksum = "5"

        self.assertEqual(
            generate_filename(doc_a),
            "somepath/2024-10-01/Does Matter.pdf",
        )

        sp.path = "{{ document.title|lower }}{{ document.archive_serial_number - 2 }}"
        sp.save()

        self.assertEqual(generate_filename(doc_a), "does matter23.pdf")

        sp.path = """
                 somepath/
                 {% if document.archive_serial_number >= 0 and document.archive_serial_number <= 200 %}
                   asn-000-200/{{title}}
                 {% elif document.archive_serial_number >= 201 and document.archive_serial_number <= 400 %}
                   asn-201-400
                   {% if document.archive_serial_number >= 201 and document.archive_serial_number < 300 %}
                     /asn-2xx
                   {% elif document.archive_serial_number >= 300 and document.archive_serial_number < 400 %}
                     /asn-3xx
                   {% endif %}
                 {% endif %}
                 /{{ title }}
                 """
        sp.save()
        self.assertEqual(
            generate_filename(doc_a),
            "somepath/asn-000-200/Does Matter/Does Matter.pdf",
        )
        doc_a.archive_serial_number = 301
        doc_a.save()
        self.assertEqual(
            generate_filename(doc_a),
            "somepath/asn-201-400/asn-3xx/Does Matter.pdf",
        )

    @override_settings(
        FILENAME_FORMAT="{{creation_date}}/{{ title_name_str }}",
    )
    def test_template_with_undefined_var(self):
        """
        GIVEN:
            - Filename format with one or more undefined variables
        WHEN:
            - Filepath for a document with this format is called
        THEN:
            - The first undefined variable is logged
            - The default format is used
        """
        doc_a = Document.objects.create(
            title="Does Matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
        )

        with self.assertLogs(level=logging.WARNING) as capture:
            self.assertEqual(
                generate_filename(doc_a),
                "0000002.pdf",
            )

            self.assertEqual(len(capture.output), 1)
            self.assertEqual(
                capture.output[0],
                "WARNING:paperless.templating:Template variable warning: 'creation_date' is undefined",
            )

    @override_settings(
        FILENAME_FORMAT="{{created}}/{{ document.save() }}",
    )
    def test_template_with_security(self):
        """
        GIVEN:
            - Filename format with one or more undefined variables
        WHEN:
            - Filepath for a document with this format is called
        THEN:
            - The first undefined variable is logged
            - The default format is used
        """
        doc_a = Document.objects.create(
            title="Does Matter",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
        )

        with self.assertLogs(level=logging.WARNING) as capture:
            self.assertEqual(
                generate_filename(doc_a),
                "0000002.pdf",
            )

            self.assertEqual(len(capture.output), 1)
            self.assertEqual(
                capture.output[0],
                "WARNING:paperless.templating:Template attempted restricted operation: <bound method Model.save of <Document: 2020-06-25 Does Matter>> is not safely callable",
            )

    def test_template_with_custom_fields(self):
        """
        GIVEN:
            - Filename format which accesses custom field data
        WHEN:
            - Filepath for a document with this format is called
        THEN:
            - The custom field data is rendered
            - If the field name is not defined, the default value is rendered, if any
        """
        doc_a = Document.objects.create(
            title="Some Title",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
        )

        cf = CustomField.objects.create(
            name="Invoice",
            data_type=CustomField.FieldDataType.INT,
        )

        cf2 = CustomField.objects.create(
            name="Select Field",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={
                "select_options": [
                    {"label": "ChoiceOne", "id": "abc=123"},
                    {"label": "ChoiceTwo", "id": "def-456"},
                ],
            },
        )

        cfi1 = CustomFieldInstance.objects.create(
            document=doc_a,
            field=cf2,
            value_select="abc=123",
        )

        cfi = CustomFieldInstance.objects.create(
            document=doc_a,
            field=cf,
            value_int=1234,
        )

        with override_settings(
            FILENAME_FORMAT="""
                 {% if "Invoice" in custom_fields %}
                   invoices/{{ custom_fields | get_cf_value('Invoice') }}
                 {% else %}
                   not-invoices/{{ title }}
                 {% endif %}
                 """,
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "invoices/1234.pdf",
            )

        with override_settings(
            FILENAME_FORMAT="""
                 {% if "Select Field" in custom_fields %}
                   {{ title }}_{{ custom_fields | get_cf_value('Select Field', 'Default Value') }}
                 {% else %}
                   {{ title }}
                 {% endif %}
                 """,
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "Some Title_ChoiceOne.pdf",
            )

            # Check for handling Nones well
            cfi1.value_select = None
            cfi1.save()

            self.assertEqual(
                generate_filename(doc_a),
                "Some Title_Default Value.pdf",
            )

        cf.name = "Invoice Number"
        cfi.value_int = 4567
        cfi.save()
        cf.save()

        with override_settings(
            FILENAME_FORMAT="invoices/{{ custom_fields | get_cf_value('Invoice Number') }}",
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "invoices/4567.pdf",
            )

        with override_settings(
            FILENAME_FORMAT="invoices/{{ custom_fields | get_cf_value('Ince Number', 0) }}",
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "invoices/0.pdf",
            )

    def test_datetime_filter(self):
        """
        GIVEN:
            - Filename format with datetime filter
        WHEN:
            - Filepath for a document with this format is called
        THEN:
            - The datetime filter is rendered
        """
        doc_a = Document.objects.create(
            title="Some Title",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
        )

        CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        CustomFieldInstance.objects.create(
            document=doc_a,
            field=CustomField.objects.get(name="Invoice Date"),
            value_date=timezone.make_aware(
                datetime.datetime(2024, 10, 1, 7, 36, 51, 153),
            ),
        )

        with override_settings(
            FILENAME_FORMAT="{{ created | datetime('%Y') }}/{{ title }}",
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "2020/Some Title.pdf",
            )

        with override_settings(
            FILENAME_FORMAT="{{ created | datetime('%Y-%m-%d') }}/{{ title }}",
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "2020-06-25/Some Title.pdf",
            )

        with override_settings(
            FILENAME_FORMAT="{{ custom_fields | get_cf_value('Invoice Date') | datetime('%Y-%m-%d') }}/{{ title }}",
        ):
            self.assertEqual(
                generate_filename(doc_a),
                "2024-10-01/Some Title.pdf",
            )

    def test_slugify_filter(self):
        """
        GIVEN:
            - Filename format with slugify filter
        WHEN:
            - Filepath for a document with this format is called
        THEN:
            - The slugify filter properly converts strings to URL-friendly slugs
        """
        doc = Document.objects.create(
            title="Some Title! With @ Special # Characters",
            created=timezone.make_aware(datetime.datetime(2020, 6, 25, 7, 36, 51, 153)),
            added=timezone.make_aware(datetime.datetime(2024, 10, 1, 7, 36, 51, 153)),
            mime_type="application/pdf",
            pk=2,
            checksum="2",
            archive_serial_number=25,
        )

        with override_settings(
            FILENAME_FORMAT="{{ title | slugify }}",
        ):
            self.assertEqual(
                generate_filename(doc),
                "some-title-with-special-characters.pdf",
            )

        # Test with correspondent name containing spaces and special chars
        doc.correspondent = Correspondent.objects.create(
            name="John's @ Office / Workplace",
        )
        doc.save()

        with override_settings(
            FILENAME_FORMAT="{{ correspondent | slugify }}/{{ title | slugify }}",
        ):
            self.assertEqual(
                generate_filename(doc),
                "johns-office-workplace/some-title-with-special-characters.pdf",
            )

        # Test with custom fields
        cf = CustomField.objects.create(
            name="Location",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=cf,
            value_text="Brussels @ Belgium!",
        )

        with override_settings(
            FILENAME_FORMAT="{{ custom_fields | get_cf_value('Location') | slugify }}/{{ title | slugify }}",
        ):
            self.assertEqual(
                generate_filename(doc),
                "brussels-belgium/some-title-with-special-characters.pdf",
            )
