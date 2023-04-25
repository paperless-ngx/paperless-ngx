import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from documents.management.commands.document_importer import Command
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_FILE_NAME


class TestImporter(TestCase):
    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)

    def test_check_manifest_exists(self):
        cmd = Command()
        self.assertRaises(
            CommandError,
            cmd._check_manifest_exists,
            Path("/tmp/manifest.json"),
        )

    def test_check_manifest(self):
        cmd = Command()
        cmd.source = Path("/tmp")

        cmd.manifest = [{"model": "documents.document"}]
        with self.assertRaises(CommandError) as cm:
            cmd._check_manifest_valid()
        self.assertIn("The manifest file contains a record", str(cm.exception))

        cmd.manifest = [
            {"model": "documents.document", EXPORTER_FILE_NAME: "noexist.pdf"},
        ]
        # self.assertRaises(CommandError, cmd._check_manifest)
        with self.assertRaises(CommandError) as cm:
            cmd._check_manifest_valid()
        self.assertIn(
            'The manifest file refers to "noexist.pdf"',
            str(cm.exception),
        )

    def test_import_permission_error(self):
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

            cmd = Command()
            cmd.source = Path(temp_dir)
            cmd.manifest = [
                {
                    "model": "documents.document",
                    EXPORTER_FILE_NAME: "original.pdf",
                    EXPORTER_ARCHIVE_NAME: "archive.pdf",
                },
            ]
            with self.assertRaises(CommandError) as cm:
                cmd._check_manifest_valid()
                self.assertInt("Failed to read from original file", str(cm.exception))

            original_path.chmod(0o444)
            archive_path.chmod(0o222)

            with self.assertRaises(CommandError) as cm:
                cmd._check_manifest_valid()
                self.assertInt("Failed to read from archive file", str(cm.exception))

    def test_import_source_not_existing(self):
        """
        GIVEN:
            - Source given doesn't exist
        WHEN:
            - Import is attempted
        THEN:
            - CommandError is raised indicating the issue
        """
        with self.assertRaises(CommandError) as cm:
            call_command("document_importer", Path("/tmp/notapath"))
            self.assertInt("That path doesn't exist", str(cm.exception))

    def test_import_source_not_readable(self):
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
                call_command("document_importer", path)
                self.assertInt(
                    "That path doesn't appear to be readable",
                    str(cm.exception),
                )
