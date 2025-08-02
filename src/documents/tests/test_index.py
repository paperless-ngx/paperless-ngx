from datetime import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils.timezone import get_current_timezone
from django.utils.timezone import timezone

from documents import index
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestAutoComplete(DirectoriesMixin, TestCase):
    def test_auto_complete(self):
        doc1 = Document.objects.create(
            title="doc1",
            checksum="A",
            content="test test2 test3",
        )
        doc2 = Document.objects.create(title="doc2", checksum="B", content="test test2")
        doc3 = Document.objects.create(title="doc3", checksum="C", content="test2")

        index.add_or_update_document(doc1)
        index.add_or_update_document(doc2)
        index.add_or_update_document(doc3)

        ix = index.open_index()

        self.assertListEqual(
            index.autocomplete(ix, "tes"),
            [b"test2", b"test", b"test3"],
        )
        self.assertListEqual(
            index.autocomplete(ix, "tes", limit=3),
            [b"test2", b"test", b"test3"],
        )
        self.assertListEqual(index.autocomplete(ix, "tes", limit=1), [b"test2"])
        self.assertListEqual(index.autocomplete(ix, "tes", limit=0), [])

    def test_archive_serial_number_ranging(self):
        """
        GIVEN:
            - Document with an archive serial number above schema allowed size
        WHEN:
            - Document is provided to the index
        THEN:
            - Error is logged
            - Document ASN is reset to 0 for the index
        """
        doc1 = Document.objects.create(
            title="doc1",
            checksum="A",
            content="test test2 test3",
            # yes, this is allowed, unless full_clean is run
            # DRF does call the validators, this test won't
            archive_serial_number=Document.ARCHIVE_SERIAL_NUMBER_MAX + 1,
        )
        with self.assertLogs("paperless.index", level="ERROR") as cm:
            with mock.patch(
                "documents.index.AsyncWriter.update_document",
            ) as mocked_update_doc:
                index.add_or_update_document(doc1)

                mocked_update_doc.assert_called_once()
                _, kwargs = mocked_update_doc.call_args

                self.assertEqual(kwargs["asn"], 0)

                error_str = cm.output[0]
                expected_str = "ERROR:paperless.index:Not indexing Archive Serial Number 4294967296 of document 1"
                self.assertIn(expected_str, error_str)

    def test_archive_serial_number_is_none(self):
        """
        GIVEN:
            - Document with no archive serial number
        WHEN:
            - Document is provided to the index
        THEN:
            - ASN isn't touched
        """
        doc1 = Document.objects.create(
            title="doc1",
            checksum="A",
            content="test test2 test3",
        )
        with mock.patch(
            "documents.index.AsyncWriter.update_document",
        ) as mocked_update_doc:
            index.add_or_update_document(doc1)

            mocked_update_doc.assert_called_once()
            _, kwargs = mocked_update_doc.call_args

            self.assertIsNone(kwargs["asn"])

    @override_settings(TIME_ZONE="Pacific/Auckland")
    def test_added_today_respects_local_timezone_boundary(self):
        tz = get_current_timezone()
        fixed_now = datetime(2025, 7, 20, 15, 0, 0, tzinfo=tz)

        # Fake a time near the local boundary (1 AM NZT = 13:00 UTC on previous UTC day)
        local_dt = datetime(2025, 7, 20, 1, 0, 0).replace(tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)

        doc = Document.objects.create(
            title="Time zone",
            content="Testing added:today",
            checksum="edgecase123",
            added=utc_dt,
        )

        with index.open_index_writer() as writer:
            index.update_document(writer, doc)

        superuser = User.objects.create_superuser(username="testuser")
        self.client.force_login(superuser)

        with mock.patch("documents.index.now", return_value=fixed_now):
            response = self.client.get("/api/documents/?query=added:today")
            results = response.json()["results"]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], doc.id)

            response = self.client.get("/api/documents/?query=added:yesterday")
            results = response.json()["results"]
            self.assertEqual(len(results), 0)
