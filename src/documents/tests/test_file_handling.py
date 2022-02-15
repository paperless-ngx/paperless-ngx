import datetime
import hashlib
import os
import random
import uuid
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from .utils import DirectoriesMixin
from ..file_handling import generate_filename, create_source_path_directory, delete_empty_directories, \
    generate_unique_filename
from ..models import Document, Correspondent, Tag, DocumentType


class TestFileHandling(DirectoriesMixin, TestCase):

    @override_settings(PAPERLESS_FILENAME_FORMAT="")
    def test_generate_source_filename(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(generate_filename(document), "{:07d}.pdf".format(document.pk))

        document.storage_type = Document.STORAGE_TYPE_GPG
        self.assertEqual(generate_filename(document),
                         "{:07d}.pdf.gpg".format(document.pk))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Test default source_path
        self.assertEqual(document.source_path, settings.ORIGINALS_DIR + "/{:07d}.pdf".format(document.pk))

        document.filename = generate_filename(document)

        # Ensure that filename is properly generated
        self.assertEqual(document.filename, "none/none.pdf")

        # Enable encryption and check again
        document.storage_type = Document.STORAGE_TYPE_GPG
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none.pdf.gpg")

        document.save()

        # test that creating dirs for the source_path creates the correct directory
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none"), True)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/test"), True)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none"), False)
        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/test/test.pdf.gpg"), True)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming_missing_permissions(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none.pdf")
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Test source_path
        self.assertEqual(document.source_path, settings.ORIGINALS_DIR + "/none/none.pdf")

        # Make the folder read- and execute-only (no writing and no renaming)
        os.chmod(settings.ORIGINALS_DIR + "/none", 0o555)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none.pdf"), True)
        self.assertEqual(document.filename, "none/none.pdf")

        os.chmod(settings.ORIGINALS_DIR + "/none", 0o777)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming_database_error(self):

        document1 = Document.objects.create(mime_type="application/pdf", storage_type=Document.STORAGE_TYPE_UNENCRYPTED, checksum="AAAAA")

        document = Document()
        document.mime_type = "application/pdf"
        document.checksum = "BBBBB"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none.pdf")
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Test source_path
        self.assertTrue(os.path.isfile(document.source_path))

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(
            name="test")[0]

        with mock.patch("documents.signals.handlers.Document.objects.filter") as m:
            m.side_effect = DatabaseError()
            document.save()

            # Check proper handling of files
            self.assertTrue(os.path.isfile(document.source_path))
            self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none.pdf"), True)
            self.assertEqual(document.filename, "none/none.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_document_delete(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none.pdf")

        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Ensure file deletion after delete
        pk = document.pk
        document.delete()
        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none.pdf"), False)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none"), False)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_document_delete_nofile(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        document.delete()

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_directory_not_empty(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none.pdf")

        create_source_path_directory(document.source_path)

        Path(document.source_path).touch()
        important_file = document.source_path + "test"
        Path(important_file).touch()

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/test"), True)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none"), True)
        self.assertTrue(os.path.isfile(important_file))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{document_type} - {title}")
    def test_document_type(self):
        dt = DocumentType.objects.create(name="my_doc_type")
        d = Document.objects.create(title="the_doc", mime_type="application/pdf")

        self.assertEqual(generate_filename(d), "none - the_doc.pdf")

        d.document_type = dt

        self.assertEqual(generate_filename(d), "my_doc_type - the_doc.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{asn} - {title}")
    def test_asn(self):
        d1 = Document.objects.create(title="the_doc", mime_type="application/pdf", archive_serial_number=652, checksum="A")
        d2 = Document.objects.create(title="the_doc", mime_type="application/pdf", archive_serial_number=None, checksum="B")
        self.assertEqual(generate_filename(d1), "652 - the_doc.pdf")
        self.assertEqual(generate_filename(d2), "none - the_doc.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_with_underscore(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type_demo")
        document.tags.create(name="foo_bar")
        document.save()

        # Ensure that filename is properly generated
        self.assertEqual(generate_filename(document),
                         "demo.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_with_dash(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type-demo")
        document.tags.create(name="foo-bar")
        document.save()

        # Ensure that filename is properly generated
        self.assertEqual(generate_filename(document),
                         "demo.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_malformed(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type:demo")
        document.tags.create(name="foo:bar")
        document.save()

        # Ensure that filename is properly generated
        self.assertEqual(generate_filename(document),
                         "none.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[0]}")
    def test_tags_all(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="demo")
        document.save()

        # Ensure that filename is properly generated
        self.assertEqual(generate_filename(document),
                         "demo.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[1]}")
    def test_tags_out_of_bounds(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="demo")
        document.save()

        # Ensure that filename is properly generated
        self.assertEqual(generate_filename(document),
                         "none.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags}")
    def test_tags_without_args(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(generate_filename(document), f"{document.pk:07}.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title} {tag_list}")
    def test_tag_list(self):
        doc = Document.objects.create(title="doc1", mime_type="application/pdf")
        doc.tags.create(name="tag2")
        doc.tags.create(name="tag1")

        self.assertEqual(generate_filename(doc), "doc1 tag1,tag2.pdf")

        doc = Document.objects.create(title="doc2", checksum="B", mime_type="application/pdf")

        self.assertEqual(generate_filename(doc), "doc2.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="//etc/something/{title}")
    def test_filename_relative(self):
        doc = Document.objects.create(title="doc1", mime_type="application/pdf")
        doc.filename = generate_filename(doc)
        doc.save()

        self.assertEqual(doc.source_path, os.path.join(settings.ORIGINALS_DIR, "etc", "something", "doc1.pdf"))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{created_year}-{created_month}-{created_day}")
    def test_created_year_month_day(self):
        d1 = timezone.make_aware(datetime.datetime(2020, 3, 6, 1, 1, 1))
        doc1 = Document.objects.create(title="doc1", mime_type="application/pdf", created=d1)

        self.assertEqual(generate_filename(doc1), "2020-03-06.pdf")

        doc1.created = timezone.make_aware(datetime.datetime(2020, 11, 16, 1, 1, 1))

        self.assertEqual(generate_filename(doc1), "2020-11-16.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{added_year}-{added_month}-{added_day}")
    def test_added_year_month_day(self):
        d1 = timezone.make_aware(datetime.datetime(232, 1, 9, 1, 1, 1))
        doc1 = Document.objects.create(title="doc1", mime_type="application/pdf", added=d1)

        self.assertEqual(generate_filename(doc1), "232-01-09.pdf")

        doc1.added = timezone.make_aware(datetime.datetime(2020, 11, 16, 1, 1, 1))

        self.assertEqual(generate_filename(doc1), "2020-11-16.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}/{correspondent}")
    def test_nested_directory_cleanup(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none/none.pdf")
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none/none"), True)

        pk = document.pk
        document.delete()

        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none/none.pdf"), False)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none/none"), False)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none"), False)
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR), True)

    @override_settings(PAPERLESS_FILENAME_FORMAT=None)
    def test_format_none(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    def test_try_delete_empty_directories(self):
        # Create our working directory
        tmp = os.path.join(settings.ORIGINALS_DIR, "test_delete_empty")
        os.makedirs(tmp)

        os.makedirs(os.path.join(tmp, "notempty"))
        Path(os.path.join(tmp, "notempty", "file")).touch()
        os.makedirs(os.path.join(tmp, "notempty", "empty"))

        delete_empty_directories(os.path.join(tmp, "notempty", "empty"), root=settings.ORIGINALS_DIR)
        self.assertEqual(os.path.isdir(os.path.join(tmp, "notempty")), True)
        self.assertEqual(os.path.isfile(
            os.path.join(tmp, "notempty", "file")), True)
        self.assertEqual(os.path.isdir(
            os.path.join(tmp, "notempty", "empty")), False)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{created/[title]")
    def test_invalid_format(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{created__year}")
    def test_invalid_format_key(self):
        document = Document()
        document.pk = 1
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        self.assertEqual(generate_filename(document), "0000001.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    def test_duplicates(self):
        document = Document.objects.create(mime_type="application/pdf", title="qwe", checksum="A", pk=1)
        document2 = Document.objects.create(mime_type="application/pdf", title="qwe", checksum="B", pk=2)
        Path(document.source_path).touch()
        Path(document2.source_path).touch()
        document.filename = "0000001.pdf"
        document.save()

        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(document.filename, "qwe.pdf")

        document2.filename = "0000002.pdf"
        document2.save()

        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(document2.filename, "qwe_01.pdf")

        # saving should not change the file names.

        document.save()

        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(document.filename, "qwe.pdf")

        document2.save()

        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(document2.filename, "qwe_01.pdf")

        document.delete()

        self.assertFalse(os.path.isfile(document.source_path))

        # filename free, should remove _01 suffix

        document2.save()

        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(document2.filename, "qwe.pdf")


    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    @mock.patch("documents.signals.handlers.Document.objects.filter")
    def test_no_update_without_change(self, m):
        doc = Document.objects.create(title="document", filename="document.pdf", archive_filename="document.pdf", checksum="A", archive_checksum="B", mime_type="application/pdf")
        Path(doc.source_path).touch()
        Path(doc.archive_path).touch()

        doc.save()

        m.assert_not_called()



class TestFileHandlingWithArchive(DirectoriesMixin, TestCase):

    @override_settings(PAPERLESS_FILENAME_FORMAT=None)
    def test_create_no_format(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", filename="0000001.pdf", checksum="A", archive_filename="0000001.pdf", archive_checksum="B")

        self.assertTrue(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def test_create_with_format(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")

        self.assertFalse(os.path.isfile(original))
        self.assertFalse(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))
        self.assertEqual(doc.source_path, os.path.join(settings.ORIGINALS_DIR, "none", "my_doc.pdf"))
        self.assertEqual(doc.archive_path, os.path.join(settings.ARCHIVE_DIR, "none", "my_doc.pdf"))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_archive_gone(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")

        self.assertTrue(os.path.isfile(original))
        self.assertFalse(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertFalse(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_archive_exists(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        existing_archive_file = os.path.join(settings.ARCHIVE_DIR, "none", "my_doc.pdf")
        Path(original).touch()
        Path(archive).touch()
        os.makedirs(os.path.join(settings.ARCHIVE_DIR, "none"))
        Path(existing_archive_file).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")

        self.assertFalse(os.path.isfile(original))
        self.assertFalse(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))
        self.assertTrue(os.path.isfile(existing_archive_file))
        self.assertEqual(doc.archive_filename, "none/my_doc_01.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    def test_move_original_only(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document_01.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "document.pdf")
        Path(original).touch()
        Path(archive).touch()

        doc = Document.objects.create(mime_type="application/pdf", title="document", filename="document_01.pdf", checksum="A",
                                      archive_checksum="B", archive_filename="document.pdf")

        self.assertEqual(doc.filename, "document.pdf")
        self.assertEqual(doc.archive_filename, "document.pdf")

        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    def test_move_archive_only(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "document_01.pdf")
        Path(original).touch()
        Path(archive).touch()

        doc = Document.objects.create(mime_type="application/pdf", title="document", filename="document.pdf", checksum="A",
                                      archive_checksum="B", archive_filename="document_01.pdf")

        self.assertEqual(doc.filename, "document.pdf")
        self.assertEqual(doc.archive_filename, "document.pdf")

        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    @mock.patch("documents.signals.handlers.os.rename")
    def test_move_archive_error(self, m):

        def fake_rename(src, dst):
            if "archive" in src:
                raise OSError()
            else:
                os.remove(src)
                Path(dst).touch()

        m.side_effect = fake_rename

        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")

        m.assert_called()
        self.assertTrue(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def test_move_file_gone(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        #Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", archive_filename="0000001.pdf", checksum="A", archive_checksum="B")

        self.assertFalse(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertFalse(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    @mock.patch("documents.signals.handlers.os.rename")
    def test_move_file_error(self, m):

        def fake_rename(src, dst):
            if "original" in src:
                raise OSError()
            else:
                os.remove(src)
                Path(dst).touch()

        m.side_effect = fake_rename

        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", archive_filename="0000001.pdf", checksum="A", archive_checksum="B")

        m.assert_called()
        self.assertTrue(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="")
    def test_archive_deleted(self):
        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document.objects.create(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")

        self.assertTrue(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))

        doc.delete()

        self.assertFalse(os.path.isfile(original))
        self.assertFalse(os.path.isfile(archive))
        self.assertFalse(os.path.isfile(doc.source_path))
        self.assertFalse(os.path.isfile(doc.archive_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{title}")
    def test_archive_deleted2(self):
        original = os.path.join(settings.ORIGINALS_DIR, "document.png")
        original2 = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(original2).touch()
        Path(archive).touch()

        doc1 = Document.objects.create(mime_type="image/png", title="document", filename="document.png", checksum="A", archive_checksum="B", archive_filename="0000001.pdf")
        doc2 = Document.objects.create(mime_type="application/pdf", title="0000001", filename="0000001.pdf", checksum="C")

        self.assertTrue(os.path.isfile(doc1.source_path))
        self.assertTrue(os.path.isfile(doc1.archive_path))
        self.assertTrue(os.path.isfile(doc2.source_path))

        doc2.delete()

        self.assertTrue(os.path.isfile(doc1.source_path))
        self.assertTrue(os.path.isfile(doc1.archive_path))
        self.assertFalse(os.path.isfile(doc2.source_path))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def test_database_error(self):

        original = os.path.join(settings.ORIGINALS_DIR, "0000001.pdf")
        archive = os.path.join(settings.ARCHIVE_DIR, "0000001.pdf")
        Path(original).touch()
        Path(archive).touch()
        doc = Document(mime_type="application/pdf", title="my_doc", filename="0000001.pdf", checksum="A", archive_filename="0000001.pdf", archive_checksum="B")
        with mock.patch("documents.signals.handlers.Document.objects.filter") as m:
            m.side_effect = DatabaseError()
            doc.save()

        self.assertTrue(os.path.isfile(original))
        self.assertTrue(os.path.isfile(archive))
        self.assertTrue(os.path.isfile(doc.source_path))
        self.assertTrue(os.path.isfile(doc.archive_path))


class TestFilenameGeneration(TestCase):

    @override_settings(
        PAPERLESS_FILENAME_FORMAT="{title}"
    )
    def test_invalid_characters(self):

        doc = Document.objects.create(title="This. is the title.", mime_type="application/pdf", pk=1, checksum="1")
        self.assertEqual(generate_filename(doc), "This. is the title.pdf")

        doc = Document.objects.create(title="my\\invalid/../title:yay", mime_type="application/pdf", pk=2, checksum="2")
        self.assertEqual(generate_filename(doc), "my-invalid-..-title-yay.pdf")

    @override_settings(
        PAPERLESS_FILENAME_FORMAT="{created}"
    )
    def test_date(self):
        doc = Document.objects.create(title="does not matter", created=timezone.make_aware(datetime.datetime(2020,5,21, 7,36,51, 153)), mime_type="application/pdf", pk=2, checksum="2")
        self.assertEqual(generate_filename(doc), "2020-05-21.pdf")


def run():
    doc = Document.objects.create(checksum=str(uuid.uuid4()), title=str(uuid.uuid4()), content="wow")
    doc.filename = generate_unique_filename(doc)
    Path(doc.thumbnail_path).touch()
    with open(doc.source_path, "w") as f:
        f.write(str(uuid.uuid4()))
    with open(doc.source_path, "rb") as f:
        doc.checksum = hashlib.md5(f.read()).hexdigest()

    with open(doc.archive_path, "w") as f:
        f.write(str(uuid.uuid4()))
    with open(doc.archive_path, "rb") as f:
        doc.archive_checksum = hashlib.md5(f.read()).hexdigest()

    doc.save()

    for i in range(30):
        doc.title = str(random.randrange(1, 5))
        doc.save()
