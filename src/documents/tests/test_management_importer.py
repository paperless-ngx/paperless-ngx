import json
import tempfile
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from documents.management.commands.document_importer import Command
from documents.management.commands.document_importer import _deserialize_record
from documents.models import Document
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_FILE_NAME
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import SampleDirMixin


@pytest.mark.management
class TestCommandImport(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    TestCase,
):
    def test_check_manifest_exists(self) -> None:
        """
        GIVEN:
            - Source directory exists
            - No manifest.json file exists in the directory
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        with self.assertRaises(CommandError) as e:
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                skip_checks=True,
            )
        self.assertIn(
            "That directory doesn't appear to contain a manifest.json file.",
            str(e.exception),
        )

    def test_check_manifest_malformed(self) -> None:
        """
        GIVEN:
            - Source directory exists
            - manifest.json file exists in the directory
            - manifest.json is missing the documents exported name
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        manifest_file = self.dirs.scratch_dir / "manifest.json"
        with manifest_file.open("w") as outfile:
            json.dump([{"model": "documents.document"}], outfile)

        with self.assertRaises(CommandError) as e:
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                skip_checks=True,
            )
        self.assertIn(
            "The manifest file contains a record which does not refer to an actual document file.",
            str(e.exception),
        )

    def test_check_manifest_file_not_found(self) -> None:
        """
        GIVEN:
            - Source directory exists
            - manifest.json file exists in the directory
            - manifest.json refers to a file which doesn't exist
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        manifest_file = self.dirs.scratch_dir / "manifest.json"
        with manifest_file.open("w") as outfile:
            json.dump(
                [{"model": "documents.document", EXPORTER_FILE_NAME: "noexist.pdf"}],
                outfile,
            )

        with self.assertRaises(CommandError) as e:
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                skip_checks=True,
            )
        self.assertIn('The manifest file refers to "noexist.pdf"', str(e.exception))

    def test_import_permission_error(self) -> None:
        """
        GIVEN:
            - Original file which cannot be read from
            - Archive file which cannot be read from
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty files
            original_path = Path(temp_dir) / "original.pdf"
            archive_path = Path(temp_dir) / "archive.pdf"
            original_path.touch()
            archive_path.touch()

            # No read permissions
            original_path.chmod(0o222)

            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "model": "documents.document",
                            EXPORTER_FILE_NAME: "original.pdf",
                            EXPORTER_ARCHIVE_NAME: "archive.pdf",
                        },
                    ],
                ),
            )

            cmd = Command()
            cmd.source = Path(temp_dir)
            cmd.manifest_paths = [manifest_path]
            cmd.data_only = False
            with self.assertRaises(CommandError) as cm:
                cmd.check_manifest_validity()
            self.assertIn("Failed to read from original file", str(cm.exception))

            original_path.chmod(0o444)
            archive_path.chmod(0o222)

            with self.assertRaises(CommandError) as cm:
                cmd.check_manifest_validity()
            self.assertIn("Failed to read from archive file", str(cm.exception))

    def test_import_source_not_existing(self) -> None:
        """
        GIVEN:
            - Source given doesn't exist
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        with self.assertRaises(CommandError) as cm:
            call_command("document_importer", Path("/tmp/notapath"), skip_checks=True)
        self.assertIn("That path doesn't exist", str(cm.exception))

    def test_import_source_not_readable(self) -> None:
        """
        GIVEN:
            - Source given isn't readable
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            path.chmod(0o222)
            with self.assertRaises(CommandError) as cm:
                call_command("document_importer", path, skip_checks=True)
            self.assertIn(
                "That path doesn't appear to be readable",
                str(cm.exception),
            )

    def test_import_source_does_not_exist(self) -> None:
        """
        GIVEN:
            - Source directory does not exist
        WHEN:
            - Request to import documents from a directory
        THEN:
            - CommandError is raised indicating the folder doesn't exist
        """
        path = Path("/tmp/should-not-exist")

        self.assertIsNotFile(path)

        with self.assertRaises(CommandError) as e:
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(path),
                skip_checks=True,
            )
        self.assertIn("That path doesn't exist", str(e.exception))

    def test_import_files_exist(self) -> None:
        """
        GIVEN:
            - Source directory does exist
            - A file exists in the originals directory
        WHEN:
            - Request to import documents from a directory
        THEN:
            - CommandError is raised indicating the file exists
        """
        (self.dirs.originals_dir / "temp").mkdir()

        (self.dirs.originals_dir / "temp" / "file.pdf").touch()

        stdout = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        self.assertIn(
            "Found file temp/file.pdf, this might indicate a non-empty installation",
            str(stdout.read()),
        )

    def test_import_with_user_exists(self) -> None:
        """
        GIVEN:
            - Source directory does exist
            - At least 1 User exists in the database
        WHEN:
            - Request to import documents from a directory
        THEN:
            - A warning is output to stdout
        """
        stdout = StringIO()

        User.objects.create()

        # Not creating a manifest, etc, so it errors
        with self.assertRaises(CommandError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        self.assertIn(
            "Found existing user(s), this might indicate a non-empty installation",
            stdout.read(),
        )

    def test_import_with_documents_exists(self) -> None:
        """
        GIVEN:
            - Source directory does exist
            - At least 1 Document exists in the database
        WHEN:
            - Request to import documents from a directory
        THEN:
            - A warning is output to stdout
        """
        stdout = StringIO()

        Document.objects.create(
            content="Content",
            checksum="1093cf6e32adbd16b06969df09215d42c4a3a8938cc18b39455953f08d1ff2ab",
            archive_checksum="706124ecde3c31616992fa979caed17a726b1c9ccdba70e82a4ff796cea97ccf",
            title="wow1",
            filename="0000001.pdf",
            mime_type="application/pdf",
            archive_filename="0000001.pdf",
        )

        # Not creating a manifest, etc, so it errors
        with self.assertRaises(CommandError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        self.assertIn(
            "Found existing documents(s), this might indicate a non-empty installation",
            str(stdout.read()),
        )

    def test_import_no_metadata_or_version_file(self) -> None:
        """
        GIVEN:
            - A source directory with a manifest file only
        WHEN:
            - An import is attempted
        THEN:
            - Warning about the missing files is output
        """
        stdout = StringIO()

        (self.dirs.scratch_dir / "manifest.json").touch()

        # We're not building a manifest, so it fails, but this test doesn't care
        with self.assertRaises(CommandError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        stdout_str = str(stdout.read())

        self.assertIn("No version.json or metadata.json file located", stdout_str)

    def test_import_version_file(self) -> None:
        """
        GIVEN:
            - A source directory with a manifest file and version file
        WHEN:
            - An import is attempted
        THEN:
            - Warning about the the version mismatch is output
        """
        stdout = StringIO()

        (self.dirs.scratch_dir / "manifest.json").touch()
        (self.dirs.scratch_dir / "version.json").write_text(
            json.dumps({"version": "2.8.1"}),
        )

        # We're not building a manifest, so it fails, but this test doesn't care
        with self.assertRaises(CommandError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(self.dirs.scratch_dir),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        stdout_str = str(stdout.read())

        self.assertIn("Version mismatch:", stdout_str)
        self.assertIn("importing 2.8.1", stdout_str)

    def test_import_zipped_export(self) -> None:
        """
        GIVEN:
            - A zip file with correct content (manifest.json and version.json inside)
        WHEN:
            - An import is attempted using the zip file as the source
        THEN:
            - The command reads from the zip without warnings or errors
        """

        stdout = StringIO()
        zip_path = self.dirs.scratch_dir / "export.zip"

        # Create manifest.json and version.json in a temp dir
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            (temp_dir_path / "manifest.json").touch()
            (temp_dir_path / "version.json").touch()

            # Create the zip file
            with ZipFile(zip_path, "w") as zf:
                zf.write(temp_dir_path / "manifest.json", arcname="manifest.json")
                zf.write(temp_dir_path / "version.json", arcname="version.json")

        # Try to import from the zip file
        with self.assertRaises(json.decoder.JSONDecodeError):
            call_command(
                "document_importer",
                "--no-progress-bar",
                str(zip_path),
                stdout=stdout,
                skip_checks=True,
            )
        stdout.seek(0)
        stdout_str = str(stdout.read())

        # There should be no error or warnings. Therefore the output should be empty.
        self.assertEqual(stdout_str, "")

    def test_batch_size_argument_accepted(self) -> None:
        """
        GIVEN:
            - A valid source directory with an empty manifest
        WHEN:
            - Import is called with --batch-size 100
        THEN:
            - No argument parsing error is raised
        """
        manifest_file = self.dirs.scratch_dir / "manifest.json"
        manifest_file.write_text("[]")

        try:
            call_command(
                "document_importer",
                "--no-progress-bar",
                "--batch-size",
                "100",
                str(self.dirs.scratch_dir),
                skip_checks=True,
            )
        except CommandError:
            pass  # Expected: empty manifest or missing files, not an argument error
        except SystemExit as e:
            self.fail(f"--batch-size raised SystemExit (unrecognized argument?): {e}")

    def test_m2m_relations_restored_after_data_only_import(self) -> None:
        """
        GIVEN:
            - A manifest with a Tag (pk=100) and a Document (pk=100) with
              tags: [100] in the fields
        WHEN:
            - Data-only import is performed
        THEN:
            - Document.objects.get(pk=100).tags.count() == 1
            - The tag's name is preserved correctly
        """
        tag_record = {
            "model": "documents.tag",
            "pk": 100,
            "fields": {"name": "imported-tag"},
        }
        doc_record = {
            "model": "documents.document",
            "pk": 100,
            "fields": {
                "title": "Tagged Doc",
                "content": "test content",
                "checksum": "1093cf6e32adbd16b06969df09215d42c4a3a8938cc18b39455953f08d1ff2ab",
                "filename": "0001000.pdf",
                "mime_type": "application/pdf",
                "modified": "2024-01-01T00:00:00Z",
                "added": "2024-01-01T00:00:00Z",
                "tags": [100],
                "correspondent": None,
                "document_type": None,
                "storage_path": None,
            },
        }

        manifest_file = self.dirs.scratch_dir / "manifest.json"
        manifest_file.write_text(json.dumps([tag_record, doc_record]))

        call_command(
            "document_importer",
            "--no-progress-bar",
            "--data-only",
            str(self.dirs.scratch_dir),
            skip_checks=True,
        )

        doc = Document.objects.get(pk=100)
        self.assertEqual(doc.tags.count(), 1)
        self.assertEqual(doc.tags.first().name, "imported-tag")

    def test_mid_batch_flush_triggered_by_small_batch_size(self) -> None:
        """
        GIVEN:
            - A manifest with two records (Tag + Document)
            - --batch-size 1 so each record fills a batch immediately
        WHEN:
            - Import is performed
        THEN:
            - flush_model() fires mid-loop (before flush_all) and the import
              completes correctly with the M2M relation intact
        """
        tag_record = {
            "model": "documents.tag",
            "pk": 200,
            "fields": {"name": "batch-flush-tag"},
        }
        doc_record = {
            "model": "documents.document",
            "pk": 200,
            "fields": {
                "title": "Batch Flush Doc",
                "content": "test",
                "checksum": "2093cf6e32adbd16b06969df09215d42c4a3a8938cc18b39455953f08d1ff2ab",
                "filename": "0002000.pdf",
                "mime_type": "application/pdf",
                "modified": "2024-01-01T00:00:00Z",
                "added": "2024-01-01T00:00:00Z",
                "tags": [200],
                "correspondent": None,
                "document_type": None,
                "storage_path": None,
            },
        }

        manifest_file = self.dirs.scratch_dir / "manifest.json"
        manifest_file.write_text(json.dumps([tag_record, doc_record]))

        call_command(
            "document_importer",
            "--no-progress-bar",
            "--data-only",
            "--batch-size",
            "1",
            str(self.dirs.scratch_dir),
            skip_checks=True,
        )

        doc = Document.objects.get(pk=200)
        self.assertEqual(doc.tags.count(), 1)
        self.assertEqual(doc.tags.first().name, "batch-flush-tag")


@pytest.mark.management
@pytest.mark.django_db
class TestDeserializeRecord:
    def test_simple_model_no_relations(self) -> None:
        """
        GIVEN:
            - A manifest record for a Correspondent (no M2M fields)
        WHEN:
            - _deserialize_record is called
        THEN:
            - Returns the correct model class, a Correspondent instance with
              correct field values, and an empty m2m_data dict
        """
        record = {
            "model": "documents.correspondent",
            "pk": 42,
            "fields": {
                "name": "ACME Corp",
                "match": "",
                "matching_algorithm": 1,
                "is_insensitive": False,
                "owner": None,
            },
        }
        model, instance, m2m_data = _deserialize_record(record)
        assert model.__name__ == "Correspondent"
        assert instance.pk == 42
        assert instance.name == "ACME Corp"
        assert m2m_data == {}

    def test_fk_field_stored_on_attname(self) -> None:
        """
        GIVEN:
            - A manifest record for a Document with a FK to a Correspondent
        WHEN:
            - _deserialize_record is called
        THEN:
            - The FK integer is stored on field.attname (correspondent_id),
              not the descriptor attribute (correspondent)
        """
        record = {
            "model": "documents.document",
            "pk": 1,
            "fields": {
                "title": "Test Doc",
                "correspondent": 42,
                "content": "",
                "checksum": "abc123abc123abc123abc123abc123ab",
                "filename": "0000001.pdf",
                "mime_type": "application/pdf",
            },
        }
        _, instance, _ = _deserialize_record(record)
        assert instance.correspondent_id == 42

    def test_m2m_field_collected_in_m2m_data(self) -> None:
        """
        GIVEN:
            - A manifest record for a Document with a tags M2M list
        WHEN:
            - _deserialize_record is called
        THEN:
            - M2M PKs are returned in m2m_data under the field name
        """
        record = {
            "model": "documents.document",
            "pk": 1,
            "fields": {
                "title": "Test",
                "tags": [1, 3, 7],
                "content": "",
                "checksum": "abc123abc123abc123abc123abc123ab",
                "filename": "0000001.pdf",
                "mime_type": "application/pdf",
            },
        }
        _, _, m2m_data = _deserialize_record(record)
        assert m2m_data["tags"] == [1, 3, 7]

    def test_null_fk_stored_as_none(self) -> None:
        """
        GIVEN:
            - A manifest record with a nullable FK set to null
        WHEN:
            - _deserialize_record is called
        THEN:
            - The FK attname is None, not 0 or a string
        """
        record = {
            "model": "documents.document",
            "pk": 2,
            "fields": {
                "title": "Test",
                "correspondent": None,
                "content": "",
                "checksum": "def456def456def456def456def456de",
                "filename": "0000002.pdf",
                "mime_type": "application/pdf",
            },
        }
        _, instance, _ = _deserialize_record(record)
        assert instance.correspondent_id is None

    def test_unknown_model_raises_deserialization_error(self) -> None:
        """
        GIVEN:
            - A manifest record with a model label that does not exist
        WHEN:
            - _deserialize_record is called
        THEN:
            - DeserializationError is raised
        """
        from django.core.serializers.base import DeserializationError

        record = {"model": "documents.doesnotexist", "pk": 1, "fields": {}}
        with pytest.raises(DeserializationError):
            _deserialize_record(record)

    def test_invalid_pk_raises_deserialization_error(self) -> None:
        """
        GIVEN:
            - A manifest record whose pk value cannot be coerced to the field type
        WHEN:
            - _deserialize_record is called
        THEN:
            - DeserializationError is raised mentioning the bad pk value
        """
        from django.core.serializers.base import DeserializationError

        record = {"model": "documents.correspondent", "pk": "not-an-int", "fields": {}}
        with pytest.raises(
            DeserializationError,
            match="Could not coerce pk=not-an-int",
        ):
            _deserialize_record(record)

    def test_invalid_scalar_field_value_raises_deserialization_error(self) -> None:
        """
        GIVEN:
            - A manifest record with a scalar field whose value cannot be coerced
        WHEN:
            - _deserialize_record is called
        THEN:
            - DeserializationError is raised mentioning the field and bad value
        """
        from django.core.serializers.base import DeserializationError

        record = {
            "model": "documents.correspondent",
            "pk": 1,
            "fields": {"matching_algorithm": "not-an-int"},
        }
        with pytest.raises(
            DeserializationError,
            match="Could not coerce matching_algorithm=",
        ):
            _deserialize_record(record)

    def test_unknown_field_name_raises_field_does_not_exist(self) -> None:
        """
        GIVEN:
            - A manifest record with a field name that does not exist on the model
        WHEN:
            - _deserialize_record is called
        THEN:
            - FieldDoesNotExist is raised
        """
        from django.core.exceptions import FieldDoesNotExist

        record = {
            "model": "documents.correspondent",
            "pk": 1,
            "fields": {"no_such_field_on_correspondent": "value"},
        }
        with pytest.raises(FieldDoesNotExist):
            _deserialize_record(record)
