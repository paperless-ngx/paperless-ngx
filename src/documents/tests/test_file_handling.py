import datetime
import os
import shutil
from unittest import mock
from uuid import uuid4
from pathlib import Path

from dateutil import tz
from django.test import TestCase, override_settings

from django.utils.text import slugify
from ..models import Tag, Document, Correspondent
from django.conf import settings


class TestDate(TestCase):
    @override_settings(PAPERLESS_FILENAME_FORMAT="")
    def test_source_filename(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(document.source_filename, "0000001.pdf")

        document.filename = "test.pdf"
        self.assertEqual(document.source_filename, "test.pdf")

    @override_settings(PAPERLESS_FILENAME_FORMAT="")
    def test_generate_source_filename(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(document.generate_source_filename(), "0000001.pdf")

        document.storage_type = Document.STORAGE_TYPE_GPG
        self.assertEqual(document.generate_source_filename(),
                         "0000001.pdf.gpg")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_file_renaming(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        # Test source_path
        self.assertEqual(document.source_path, settings.MEDIA_ROOT +
                         "/documents/originals/none/none-0000001.pdf")

        # Enable encryption and check again
        document.storage_type = Document.STORAGE_TYPE_GPG
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none-0000001.pdf.gpg")
        document.save()

        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), True)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(
                name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/test"), True)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), False)
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/test/test-0000001.pdf.gpg"), True)
        self.assertEqual(document.generate_source_filename(),
                         "test/test-0000001.pdf.gpg")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_delete(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        # Ensure file deletion after delete
        document.delete()
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT +
                         "/documents/originals/none/none-0000001.pdf"), False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), False)

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_directory_not_empty(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()
        Path(document.source_path + "test").touch()

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(
                name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/test"), True)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), True)

        # Cleanup
        os.remove(settings.MEDIA_ROOT +
                  "/documents/originals/none/none-0000001.pdftest")
        os.rmdir(settings.MEDIA_ROOT + "/documents/originals/none")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tag[type]}")
    def test_tags_with_underscore(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type_demo")
        document.tags.create(name="foo_bar")
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "demo-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tag[type]}")
    def test_tags_with_dash(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type-demo")
        document.tags.create(name="foo-bar")
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "demo-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tag[type]}")
    def test_tags_malformed(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="type:demo")
        document.tags.create(name="foo:bar")
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[0]}")
    def test_tags_all(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Add tag to document
        document.tags.create(name="demo")
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "demo-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[0]}")
    def test_tags_out_of_bounds_0(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[10000000]}")
    def test_tags_out_of_bounds_10000000(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[99]}")
    def test_tags_out_of_bounds_99(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}/{correspondent}")
    def test_nested_directory_cleanup(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none/none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none/none"), True)

        document.delete()

        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT +
                         "/documents/originals/none/none/none-0000001.pdf"),
                         False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none/none"), False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals"), False)

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT=None)
    def test_format_none(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(document.generate_source_filename(), "0000001.pdf")
