import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings
from faker import Faker

from documents.models import Correspondent
from documents.models import Document
from documents.tasks import empty_trash


class TestDocument(TestCase):
    def setUp(self) -> None:
        self.originals_dir = tempfile.mkdtemp()
        self.thumb_dir = tempfile.mkdtemp()

        self.overrides = override_settings(
            ORIGINALS_DIR=self.originals_dir,
            THUMBNAIL_DIR=self.thumb_dir,
        )

        self.overrides.enable()

    def tearDown(self) -> None:
        shutil.rmtree(self.originals_dir)
        shutil.rmtree(self.thumb_dir)
        self.overrides.disable()

    def test_file_deletion(self) -> None:
        document = Document.objects.create(
            correspondent=Correspondent.objects.create(name="Test0"),
            title="Title",
            content="content",
            checksum="checksum",
            mime_type="application/pdf",
        )

        file_path = document.source_path
        thumb_path = document.thumbnail_path

        Path(file_path).touch()
        Path(thumb_path).touch()

        with mock.patch("documents.signals.handlers.Path.unlink") as mock_unlink:
            document.delete()
            empty_trash([document.pk])
            self.assertEqual(mock_unlink.call_count, 2)

    def test_document_soft_delete(self) -> None:
        document = Document.objects.create(
            correspondent=Correspondent.objects.create(name="Test0"),
            title="Title",
            content="content",
            checksum="checksum",
            mime_type="application/pdf",
        )

        file_path = document.source_path
        thumb_path = document.thumbnail_path

        Path(file_path).touch()
        Path(thumb_path).touch()

        with mock.patch("documents.signals.handlers.Path.unlink") as mock_unlink:
            document.delete()
            self.assertEqual(mock_unlink.call_count, 0)

            self.assertEqual(Document.objects.count(), 0)

            document.restore(strict=False)
            self.assertEqual(Document.objects.count(), 1)

            document.delete()
            empty_trash([document.pk])
            self.assertEqual(mock_unlink.call_count, 2)

    def test_file_name(self) -> None:
        doc = Document(
            mime_type="application/pdf",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.pdf")

    def test_file_name_jpg(self) -> None:
        doc = Document(
            mime_type="image/jpeg",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.jpg")

    def test_file_name_unknown(self) -> None:
        doc = Document(
            mime_type="application/zip",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.zip")

    def test_file_name_invalid_type(self) -> None:
        doc = Document(
            mime_type="image/jpegasd",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test")


def test_suggestion_content() -> None:
    """
    Check that the document for suggestion is cropped, only if it exceeds the length limit.
    """
    fake_text = Faker().text(max_nb_chars=1201000)

    # Do not crop content under 1.2M chars
    content_under_limit = fake_text[:1200000]
    doc = Document(
        title="test",
        created=date(2025, 6, 1),
        content=content_under_limit,
    )
    assert doc.suggestion_content == content_under_limit

    # If over the limit, crop to 1M char (800K from the beginning, 200K from the end)
    content_over_limit = fake_text[:1200001]
    expected_cropped_content = (
        content_over_limit[:800000] + " " + content_over_limit[-200000:]
    )
    doc.content = content_over_limit
    assert doc.suggestion_content == expected_cropped_content
