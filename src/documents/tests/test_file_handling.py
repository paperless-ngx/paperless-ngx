import datetime
import os
import shutil
from unittest import mock
from uuid import uuid4
from pathlib import Path
from shutil import rmtree

from dateutil import tz
from django.test import TestCase, override_settings

from django.utils.text import slugify
from ..models import Tag, Document, Correspondent
from django.conf import settings


class TestDate(TestCase):
    deletion_list = []

    def add_to_deletion_list(self, dirname):
        self.deletion_list.append(dirname)

    def tearDown(self):
        for dirname in self.deletion_list:
            shutil.rmtree(dirname, ignore_errors=True)

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
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
    def test_file_renaming_missing_permissions(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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

        # Make the folder read- and execute-only (no writing and no renaming)
        os.chmod(settings.MEDIA_ROOT + "/documents/originals/none", 0o555)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(
                name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/none/none-0000001.pdf"), True)
        self.assertEqual(document.source_filename,
                         "none/none-0000001.pdf")

        os.chmod(settings.MEDIA_ROOT + "/documents/originals/none", 0o777)

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_delete(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_delete_nofile(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_directory_not_empty(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_with_underscore(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_with_dash(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[type]}")
    def test_tags_malformed(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
                         "none-0000001.pdf")
        document.create_source_directory()
        Path(document.source_path).touch()

        document.delete()

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[0]}")
    def test_tags_all(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
    @override_settings(PAPERLESS_FILENAME_FORMAT="{tags[99]}")
    def test_tags_out_of_bounds_99(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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
                         "/documents/originals"), True)

    @override_settings(PAPERLESS_FILENAME_FORMAT=None)
    def test_format_none(self):
        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        self.assertEqual(document.generate_source_filename(), "0000001.pdf")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_renamed(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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

        # Rename the document "illegaly"
        os.makedirs(settings.MEDIA_ROOT + "/documents/originals/test")
        os.rename(settings.MEDIA_ROOT + "/documents/originals/" +
                                        "none/none-0000001.pdf",
                  settings.MEDIA_ROOT + "/documents/originals/" +
                                        "test/test-0000001.pdf")
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/test/test-0000001.pdf"), True)
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/none/none-0000001.pdf"), False)

        # Set new correspondent and expect document to be saved properly
        document.correspondent = Correspondent.objects.get_or_create(
                name="foo")[0]
        document.save()
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/foo/foo-0000001.pdf"), True)

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/foo"), True)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/test"), False)
        self.assertEqual(document.generate_source_filename(),
                         "foo/foo-0000001.pdf")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_renamed_encrypted(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

        document = Document()
        document.file_type = "pdf"
        document.storage_type = Document.STORAGE_TYPE_GPG
        document.save()

        # Ensure that filename is properly generated
        tmp = document.source_filename
        self.assertEqual(document.generate_source_filename(),
                         "none/none-0000001.pdf.gpg")
        document.create_source_directory()
        Path(document.source_path).touch()

        # Test source_path
        self.assertEqual(document.source_path, settings.MEDIA_ROOT +
                         "/documents/originals/none/none-0000001.pdf.gpg")

        # Rename the document "illegaly"
        os.makedirs(settings.MEDIA_ROOT + "/documents/originals/test")
        os.rename(settings.MEDIA_ROOT + "/documents/originals/" +
                                        "none/none-0000001.pdf.gpg",
                  settings.MEDIA_ROOT + "/documents/originals/" +
                                        "test/test-0000001.pdf.gpg")
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/test/test-0000001.pdf.gpg"), True)
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/none/none-0000001.pdf"), False)

        # Set new correspondent and expect document to be saved properly
        document.correspondent = Correspondent.objects.get_or_create(
                name="foo")[0]
        document.save()
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/" +
                         "originals/foo/foo-0000001.pdf.gpg"), True)

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/foo"), True)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), False)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/test"), False)
        self.assertEqual(document.generate_source_filename(),
                         "foo/foo-0000001.pdf.gpg")

    def test_delete_all_empty_subdirectories(self):
        # Create our working directory
        tmp = "/tmp/paperless-tests-{}".format(str(uuid4())[:8])
        os.makedirs(tmp)
        self.add_to_deletion_list(tmp)

        os.makedirs(os.path.join(tmp, "empty"))
        os.makedirs(os.path.join(tmp, "empty", "subdirectory"))

        os.makedirs(os.path.join(tmp, "notempty"))
        Path(os.path.join(tmp, "notempty", "file")).touch()

        Document.delete_all_empty_subdirectories(tmp)

        self.assertEqual(os.path.isdir(os.path.join(tmp, "notempty")), True)
        self.assertEqual(os.path.isdir(os.path.join(tmp, "empty")), False)
        self.assertEqual(os.path.isfile(
            os.path.join(tmp, "notempty", "file")), True)

    def test_try_delete_empty_directories(self):
        # Create our working directory
        tmp = "/tmp/paperless-tests-{}".format(str(uuid4())[:8])
        os.makedirs(tmp)
        self.add_to_deletion_list(tmp)

        os.makedirs(os.path.join(tmp, "notempty"))
        Path(os.path.join(tmp, "notempty", "file")).touch()
        os.makedirs(os.path.join(tmp, "notempty", "empty"))

        Document.try_delete_empty_directories(
                os.path.join(tmp, "notempty", "empty"))
        self.assertEqual(os.path.isdir(os.path.join(tmp, "notempty")), True)
        self.assertEqual(os.path.isfile(
            os.path.join(tmp, "notempty", "file")), True)
        self.assertEqual(os.path.isdir(
            os.path.join(tmp, "notempty", "empty")), False)

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_document_accidentally_deleted(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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

        # Delete the document "illegaly"
        os.remove(settings.MEDIA_ROOT + "/documents/originals/" +
                                        "none/none-0000001.pdf")

        # Set new correspondent and expect document to be saved properly
        document.correspondent = Correspondent.objects.get_or_create(
                name="foo")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT +
                         "/documents/originals/none"), True)
        self.assertEqual(document.source_filename,
                         "none/none-0000001.pdf")

    @override_settings(MEDIA_ROOT="/tmp/paperless-tests-{}".
                       format(str(uuid4())[:8]))
    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/" +
                       "{correspondent}")
    def test_set_filename(self):
        self.add_to_deletion_list(settings.MEDIA_ROOT)

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

        # Set existing filename
        document.set_filename(tmp)
        self.assertEqual(document.source_filename, "none/none-0000001.pdf")

        # Set non-existing filename
        document.set_filename("doesnotexist")
        self.assertEqual(document.source_filename, "none/none-0000001.pdf")
