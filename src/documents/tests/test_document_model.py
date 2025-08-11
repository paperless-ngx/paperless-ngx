import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import pytest
from django.test import TestCase
from django.test import override_settings

from documents.models import Correspondent
from documents.models import Document
from documents.tasks import empty_trash


class TestDocument(TestCase):
    def setUp(self) -> None:
        self.originals_dir = tempfile.mkdtemp()
        self.thumb_dir = tempfile.mkdtemp()

        override_settings(
            ORIGINALS_DIR=self.originals_dir,
            THUMBNAIL_DIR=self.thumb_dir,
        ).enable()

    def tearDown(self) -> None:
        shutil.rmtree(self.originals_dir)
        shutil.rmtree(self.thumb_dir)

    def test_file_deletion(self):
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

    def test_document_soft_delete(self):
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

    def test_file_name(self):
        doc = Document(
            mime_type="application/pdf",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.pdf")

    def test_file_name_jpg(self):
        doc = Document(
            mime_type="image/jpeg",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.jpg")

    def test_file_name_unknown(self):
        doc = Document(
            mime_type="application/zip",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.zip")

    def test_file_name_invalid_type(self):
        doc = Document(
            mime_type="image/jpegasd",
            title="test",
            created=date(2020, 12, 25),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test")


@pytest.mark.parametrize(
    ("content_limit", "expected_content"),
    [
        (10, "This is  e."),
        (20, "This is the docu ate."),
    ],
)
def test_suggestion_content(content_limit, expected_content):
    long_content = """This is the document content. It is quite long, so we ought to crop it when computing suggestions and parsing the date."""
    other_long_content = (
        "Another document content, used to test property cache invalidation."
    )
    short_content = "test"
    with override_settings(
        SUGGESTION_CONTENT_LENGTH_LIMIT=content_limit,
    ):
        doc = Document(
            title="test",
            created=date(2025, 6, 1),
            content=other_long_content,
        )
        # call the property once to cache it
        assert doc.suggestion_content

        # Test property cache invalidation and limit
        doc.content = long_content
        assert doc.suggestion_content == expected_content

        # Test with content shorter than the limit
        doc.content = short_content
        assert doc.suggestion_content == short_content
