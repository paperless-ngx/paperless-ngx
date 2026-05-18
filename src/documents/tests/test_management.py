from __future__ import annotations

import filecmp
import shutil
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

from documents.file_handling import generate_filename
from documents.models import Document
from documents.tasks import update_document_content_maybe_archive_file
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin

sample_file: Path = Path(__file__).parent / "samples" / "simple.pdf"


@pytest.mark.management
@override_settings(
    FILENAME_FORMAT="{correspondent}/{title}",
    ARCHIVE_FILE_GENERATION="always",
)
class TestArchiver(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    def make_models(self):
        return Document.objects.create(
            checksum="A",
            title="A",
            content="first document",
            mime_type="application/pdf",
        )

    def test_archiver(self) -> None:
        doc = self.make_models()
        shutil.copy(sample_file, Path(self.dirs.originals_dir) / f"{doc.id:07}.pdf")

        call_command("document_archiver", "--processes", "1", skip_checks=True)

    def test_handle_document(self) -> None:
        doc = self.make_models()
        shutil.copy(sample_file, Path(self.dirs.originals_dir) / f"{doc.id:07}.pdf")

        update_document_content_maybe_archive_file(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNotNone(doc.archive_checksum)
        self.assertIsFile(doc.archive_path)
        self.assertIsFile(doc.source_path)
        self.assertTrue(filecmp.cmp(sample_file, doc.source_path))
        self.assertEqual(doc.archive_filename, "none/A.pdf")

    def test_unknown_mime_type(self) -> None:
        doc = self.make_models()
        doc.mime_type = "sdgfh"
        doc.save()
        shutil.copy(sample_file, doc.source_path)

        update_document_content_maybe_archive_file(doc.pk)

        doc = Document.objects.get(id=doc.id)

        self.assertIsNotNone(doc.checksum)
        self.assertIsNone(doc.archive_checksum)
        self.assertIsNone(doc.archive_filename)
        self.assertIsFile(doc.source_path)

    @override_settings(FILENAME_FORMAT="{title}")
    def test_naming_priorities(self) -> None:
        doc1 = Document.objects.create(
            checksum="A",
            title="document",
            content="first document",
            mime_type="application/pdf",
            filename="document.pdf",
        )
        doc2 = Document.objects.create(
            checksum="B",
            title="document",
            content="second document",
            mime_type="application/pdf",
            filename="document_01.pdf",
        )
        shutil.copy(sample_file, Path(self.dirs.originals_dir) / "document.pdf")
        shutil.copy(sample_file, Path(self.dirs.originals_dir) / "document_01.pdf")

        update_document_content_maybe_archive_file(doc2.pk)
        update_document_content_maybe_archive_file(doc1.pk)

        doc1 = Document.objects.get(id=doc1.id)
        doc2 = Document.objects.get(id=doc2.id)

        self.assertEqual(doc1.archive_filename, "document.pdf")
        self.assertEqual(doc2.archive_filename, "document_01.pdf")


@pytest.mark.management
@pytest.mark.django_db
class TestMakeIndex:
    def test_reindex(self, mocker: MockerFixture) -> None:
        """Reindex command must call the backend rebuild method to recreate the index."""
        mock_get_backend = mocker.patch(
            "documents.management.commands.document_index.get_backend",
        )
        call_command("document_index", "reindex", skip_checks=True)
        mock_get_backend.return_value.rebuild.assert_called_once()

    def test_optimize(self) -> None:
        """Optimize command must execute without error (Tantivy handles optimization automatically)."""
        call_command("document_index", "optimize", skip_checks=True)

    def test_reindex_recreate_wipes_index(self, mocker: MockerFixture) -> None:
        """Reindex with --recreate must wipe the index before rebuilding."""
        mock_wipe = mocker.patch(
            "documents.management.commands.document_index.wipe_index",
        )
        mock_get_backend = mocker.patch(
            "documents.management.commands.document_index.get_backend",
        )
        call_command("document_index", "reindex", recreate=True, skip_checks=True)
        mock_wipe.assert_called_once()
        mock_get_backend.return_value.rebuild.assert_called_once()

    def test_reindex_without_recreate_does_not_wipe_index(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Reindex without --recreate must not wipe the index."""
        mock_wipe = mocker.patch(
            "documents.management.commands.document_index.wipe_index",
        )
        mocker.patch(
            "documents.management.commands.document_index.get_backend",
        )
        call_command("document_index", "reindex", skip_checks=True)
        mock_wipe.assert_not_called()

    def test_reindex_if_needed_skips_when_up_to_date(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Conditional reindex must skip rebuild when schema version and language match."""
        mocker.patch(
            "documents.management.commands.document_index.needs_rebuild",
            return_value=False,
        )
        mock_get_backend = mocker.patch(
            "documents.management.commands.document_index.get_backend",
        )
        call_command("document_index", "reindex", if_needed=True, skip_checks=True)
        mock_get_backend.return_value.rebuild.assert_not_called()

    def test_reindex_if_needed_runs_when_rebuild_needed(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Conditional reindex must proceed with rebuild when schema version or language changed."""
        mocker.patch(
            "documents.management.commands.document_index.needs_rebuild",
            return_value=True,
        )
        mock_get_backend = mocker.patch(
            "documents.management.commands.document_index.get_backend",
        )
        call_command("document_index", "reindex", if_needed=True, skip_checks=True)
        mock_get_backend.return_value.rebuild.assert_called_once()


@pytest.mark.management
class TestRenamer(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @override_settings(FILENAME_FORMAT="")
    def test_rename(self) -> None:
        doc = Document.objects.create(title="test", mime_type="image/jpeg")
        doc.filename = generate_filename(doc)
        doc.archive_filename = generate_filename(doc, archive_filename=True)
        doc.save()

        Path(doc.source_path).touch()
        Path(doc.archive_path).touch()

        with override_settings(FILENAME_FORMAT="{correspondent}/{title}"):
            call_command("document_renamer", skip_checks=True)

        doc2 = Document.objects.get(id=doc.id)

        self.assertEqual(doc2.filename, "none/test.jpg")
        self.assertEqual(doc2.archive_filename, "none/test.pdf")
        self.assertIsNotFile(doc.source_path)
        self.assertIsNotFile(doc.archive_path)
        self.assertIsFile(doc2.source_path)
        self.assertIsFile(doc2.archive_path)


@pytest.mark.management
class TestCreateClassifier:
    def test_create_classifier(self, mocker: MockerFixture) -> None:
        m = mocker.patch(
            "documents.management.commands.document_create_classifier.train_classifier",
        )

        call_command("document_create_classifier", skip_checks=True)

        m.assert_called_once_with(status_callback=mocker.ANY)
        assert callable(m.call_args.kwargs["status_callback"])

    def test_create_classifier_callback_output(self, mocker: MockerFixture) -> None:
        """Callback passed to train_classifier writes each phase message to the console."""
        m = mocker.patch(
            "documents.management.commands.document_create_classifier.train_classifier",
        )

        def invoke_callback(**kwargs):
            kwargs["status_callback"]("Vectorizing document content...")

        m.side_effect = invoke_callback

        stdout = StringIO()
        call_command("document_create_classifier", skip_checks=True, stdout=stdout)

        assert "Vectorizing document content..." in stdout.getvalue()


@pytest.mark.management
class TestConvertMariaDBUUID(TestCase):
    @mock.patch("django.db.connection.schema_editor")
    def test_convert(self, m) -> None:
        m.alter_field.return_value = None

        stdout = StringIO()
        call_command("convert_mariadb_uuid", stdout=stdout, skip_checks=True)

        m.assert_called_once()

        self.assertIn("Successfully converted", stdout.getvalue())


@pytest.mark.management
class TestPruneAuditLogs(TestCase):
    def test_prune_audit_logs(self) -> None:
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Document),
            object_id=1,
            action=LogEntry.Action.CREATE,
        )
        call_command("prune_audit_logs", skip_checks=True)

        self.assertEqual(LogEntry.objects.count(), 0)
