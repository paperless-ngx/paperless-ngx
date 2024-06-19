import shutil
import tempfile
import zoneinfo
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

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

        with mock.patch("documents.signals.handlers.os.unlink") as mock_unlink:
            document.delete()
            empty_trash([document.pk])
            mock_unlink.assert_any_call(file_path)
            mock_unlink.assert_any_call(thumb_path)
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

        with mock.patch("documents.signals.handlers.os.unlink") as mock_unlink:
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
            created=timezone.datetime(2020, 12, 25, tzinfo=zoneinfo.ZoneInfo("UTC")),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.pdf")

    @override_settings(
        TIME_ZONE="Europe/Berlin",
    )
    def test_file_name_with_timezone(self):
        # See https://docs.djangoproject.com/en/4.0/ref/utils/#django.utils.timezone.now
        # The default for created is an aware datetime in UTC
        # This does that, just manually, with a fixed date
        local_create_date = timezone.datetime(
            2020,
            12,
            25,
            tzinfo=zoneinfo.ZoneInfo("Europe/Berlin"),
        )

        utc_create_date = local_create_date.astimezone(zoneinfo.ZoneInfo("UTC"))

        doc = Document(
            mime_type="application/pdf",
            title="test",
            created=utc_create_date,
        )

        # Ensure the create date would cause an off by 1 if not properly created above
        self.assertEqual(utc_create_date.date().day, 24)
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.pdf")

        local_create_date = timezone.datetime(
            2020,
            1,
            1,
            tzinfo=zoneinfo.ZoneInfo("Europe/Berlin"),
        )

        utc_create_date = local_create_date.astimezone(zoneinfo.ZoneInfo("UTC"))

        doc = Document(
            mime_type="application/pdf",
            title="test",
            created=utc_create_date,
        )

        # Ensure the create date would cause an off by 1 in the year if not properly created above
        self.assertEqual(utc_create_date.date().year, 2019)
        self.assertEqual(doc.get_public_filename(), "2020-01-01 test.pdf")

    def test_file_name_jpg(self):
        doc = Document(
            mime_type="image/jpeg",
            title="test",
            created=timezone.datetime(2020, 12, 25, tzinfo=zoneinfo.ZoneInfo("UTC")),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.jpg")

    def test_file_name_unknown(self):
        doc = Document(
            mime_type="application/zip",
            title="test",
            created=timezone.datetime(2020, 12, 25, tzinfo=zoneinfo.ZoneInfo("UTC")),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test.zip")

    def test_file_name_invalid_type(self):
        doc = Document(
            mime_type="image/jpegasd",
            title="test",
            created=timezone.datetime(2020, 12, 25, tzinfo=zoneinfo.ZoneInfo("UTC")),
        )
        self.assertEqual(doc.get_public_filename(), "2020-12-25 test")
