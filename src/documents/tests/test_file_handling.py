import os
import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import TestCase, override_settings

from ..file_handling import generate_filename, create_source_path_directory, delete_empty_directories
from ..models import Document, Correspondent
from ..signals.handlers import update_filename_and_move_files


class TestDate(TestCase):
    deletion_list = []

    def add_to_deletion_list(self, dirname):
        self.deletion_list.append(dirname)

    def setUp(self):
        folder = "/tmp/paperless-tests-{}".format(str(uuid4())[:8])
        os.makedirs(folder + "/documents/originals")
        override_settings(MEDIA_ROOT=folder).enable()
        override_settings(ORIGINALS_DIR=folder + "/documents/originals").enable()
        self.add_to_deletion_list(folder)

    def tearDown(self):
        for dirname in self.deletion_list:
            shutil.rmtree(dirname, ignore_errors=True)

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
        self.assertEqual(document.filename, "none/none-{:07d}.pdf".format(document.pk))

        # Enable encryption and check again
        document.storage_type = Document.STORAGE_TYPE_GPG
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none-{:07d}.pdf.gpg".format(document.pk))

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
        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/test/test-{:07d}.pdf.gpg".format(document.pk)), True)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_file_renaming_missing_permissions(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none-{:07d}.pdf".format(document.pk))
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Test source_path
        self.assertEqual(document.source_path, settings.ORIGINALS_DIR + "/none/none-{:07d}.pdf".format(document.pk))

        # Make the folder read- and execute-only (no writing and no renaming)
        os.chmod(settings.ORIGINALS_DIR + "/none", 0o555)

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/originals/none/none-{:07d}.pdf".format(document.pk)), True)
        self.assertEqual(document.filename, "none/none-{:07d}.pdf".format(document.pk))

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
                         "none/none-{:07d}.pdf".format(document.pk))
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Test source_path
        self.assertTrue(os.path.isfile(document.source_path))

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(
            name="test")[0]

        # This will cause save() to fail.
        document.checksum = document1.checksum

        # Assume saving the document initially works, this gets called.
        # After renaming, an error occurs, and filename is not saved:
        # document should still be available at document.filename.
        update_filename_and_move_files(None, document)

        # Check proper handling of files
        self.assertTrue(os.path.isfile(document.source_path))
        self.assertEqual(os.path.isfile(settings.MEDIA_ROOT + "/documents/originals/none/none-{:07d}.pdf".format(document.pk)), True)
        self.assertEqual(document.filename, "none/none-{:07d}.pdf".format(document.pk))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}")
    def test_document_delete(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename,
                         "none/none-{:07d}.pdf".format(document.pk))

        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Ensure file deletion after delete
        pk = document.pk
        document.delete()
        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none-{:07d}.pdf".format(pk)), False)
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
                         "none/none-{:07d}.pdf".format(document.pk))

        create_source_path_directory(document.source_path)

        Path(document.source_path).touch()
        important_file = document.source_path + "test"
        Path(important_file).touch()

        # Set a correspondent and save the document
        document.correspondent = Correspondent.objects.get_or_create(name="test")[0]
        document.save()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT + "/documents/originals/test"), True)
        self.assertEqual(os.path.isdir(settings.MEDIA_ROOT + "/documents/originals/none"), True)
        self.assertTrue(os.path.isfile(important_file))

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
                         "demo-{:07d}.pdf".format(document.pk))

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
                         "demo-{:07d}.pdf".format(document.pk))

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
                         "none-{:07d}.pdf".format(document.pk))

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
                         "demo-{:07d}.pdf".format(document.pk))

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
                         "none-{:07d}.pdf".format(document.pk))

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{correspondent}/{correspondent}")
    def test_nested_directory_cleanup(self):
        document = Document()
        document.mime_type = "application/pdf"
        document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        document.save()

        # Ensure that filename is properly generated
        document.filename = generate_filename(document)
        self.assertEqual(document.filename, "none/none/none-{:07d}.pdf".format(document.pk))
        create_source_path_directory(document.source_path)
        Path(document.source_path).touch()

        # Check proper handling of files
        self.assertEqual(os.path.isdir(settings.ORIGINALS_DIR + "/none/none"), True)

        pk = document.pk
        document.delete()

        self.assertEqual(os.path.isfile(settings.ORIGINALS_DIR + "/none/none/none-{:07d}.pdf".format(pk)), False)
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
        self.add_to_deletion_list(tmp)

        os.makedirs(os.path.join(tmp, "notempty"))
        Path(os.path.join(tmp, "notempty", "file")).touch()
        os.makedirs(os.path.join(tmp, "notempty", "empty"))

        delete_empty_directories(os.path.join(tmp, "notempty", "empty"))
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
