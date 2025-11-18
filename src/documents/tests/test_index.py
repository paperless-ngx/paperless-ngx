from datetime import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase
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


class TestRewriteNaturalDateKeywords(SimpleTestCase):
    """
    Unit tests for rewrite_natural_date_keywords function.
    Uses SimpleTestCase (no database required) since the function only uses
    Django timezone utilities and standard library modules.
    """

    @override_settings(TIME_ZONE="UTC")
    def test_today_keyword(self):
        """Test that 'today' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:today")
            # Should match: added:[20250720000000 TO 20250720235959]
            self.assertIn("added:[20250720", result)
            self.assertIn("TO 20250720", result)

    @override_settings(TIME_ZONE="UTC")
    def test_yesterday_keyword(self):
        """Test that 'yesterday' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:yesterday")
            # Should match: added:[20250719000000 TO 20250719235959]
            self.assertIn("added:[20250719", result)
            self.assertIn("TO 20250719", result)

    @override_settings(TIME_ZONE="UTC")
    def test_this_month_keyword(self):
        """Test that 'this month' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:this month")
            # Should match: added:[20250701000000 TO 20250731235959]
            self.assertIn("added:[20250701", result)
            self.assertIn("TO 20250731", result)

    @override_settings(TIME_ZONE="UTC")
    def test_previous_month_keyword(self):
        """Test that 'previous month' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:previous month")
            # Should match: added:[20250601000000 TO 20250630235959]
            self.assertIn("added:[20250601", result)
            self.assertIn("TO 20250630", result)

    @override_settings(TIME_ZONE="UTC")
    def test_this_year_keyword(self):
        """Test that 'this year' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:this year")
            # Should match: added:[20250101000000 TO 20250715235959]
            self.assertIn("added:[20250101", result)
            self.assertIn("TO 20250715", result)

    @override_settings(TIME_ZONE="UTC")
    def test_previous_year_keyword(self):
        """Test that 'previous year' keyword is correctly rewritten."""
        fixed_now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:previous year")
            # Should match: added:[20240101000000 TO 20241231235959]
            self.assertIn("added:[20240101", result)
            self.assertIn("TO 20241231", result)

    @override_settings(TIME_ZONE="UTC")
    def test_previous_week_keyword(self):
        """Test that 'previous week' keyword is correctly rewritten."""
        # July 20, 2025 is a Sunday (weekday 6)
        fixed_now = datetime(2025, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:previous week")
            # Previous week would be July 7-13, 2025
            self.assertIn("added:[20250707", result)
            self.assertIn("TO 20250713", result)

    @override_settings(TIME_ZONE="UTC")
    def test_previous_quarter_keyword(self):
        """Test that 'previous quarter' keyword is correctly rewritten."""
        # July is Q3, so previous quarter is Q2 (April-June)
        fixed_now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:previous quarter")
            # Should match: added:[20250401000000 TO 20250630235959]
            self.assertIn("added:[20250401", result)
            self.assertIn("TO 20250630", result)

    @override_settings(TIME_ZONE="UTC")
    def test_created_field(self):
        """Test that 'created' field works in addition to 'added'."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("created:today")
            self.assertIn("created:[20250720", result)

    @override_settings(TIME_ZONE="UTC")
    def test_quoted_keywords(self):
        """Test that quoted keywords work."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result1 = index.rewrite_natural_date_keywords('added:"today"')
            result2 = index.rewrite_natural_date_keywords("added:'today'")
            self.assertIn("added:[20250720", result1)
            self.assertIn("added:[20250720", result2)

    @override_settings(TIME_ZONE="UTC")
    def test_case_insensitive(self):
        """Test that keywords are case-insensitive."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result1 = index.rewrite_natural_date_keywords("added:TODAY")
            result2 = index.rewrite_natural_date_keywords("added:Today")
            result3 = index.rewrite_natural_date_keywords("added:ToDaY")
            self.assertIn("added:[20250720", result1)
            self.assertIn("added:[20250720", result2)
            self.assertIn("added:[20250720", result3)

    @override_settings(TIME_ZONE="UTC")
    def test_multiple_keywords(self):
        """Test that multiple keywords in one query work."""
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords(
                "added:today created:yesterday",
            )
            self.assertIn("added:[20250720", result)
            self.assertIn("created:[20250719", result)

    @override_settings(TIME_ZONE="UTC")
    def test_no_match(self):
        """Test that queries without keywords are unchanged."""
        query = "title:test content:example"
        result = index.rewrite_natural_date_keywords(query)
        self.assertEqual(query, result)

    @override_settings(TIME_ZONE="Pacific/Auckland")
    def test_timezone_awareness(self):
        """Test that timezone conversion works correctly."""
        # July 20, 2025 1:00 AM NZST = July 19, 2025 13:00 UTC
        fixed_now = datetime(2025, 7, 20, 1, 0, 0, tzinfo=get_current_timezone())
        with mock.patch("documents.index.now", return_value=fixed_now):
            result = index.rewrite_natural_date_keywords("added:today")
            # Should convert to UTC properly
            self.assertIn("added:[", result)
            self.assertIn("TO ", result)
