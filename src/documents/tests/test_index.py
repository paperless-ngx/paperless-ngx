from datetime import datetime
from unittest import mock

from django.conf import settings
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
    def test_auto_complete(self) -> None:
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

    def test_archive_serial_number_ranging(self) -> None:
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

    def test_archive_serial_number_is_none(self) -> None:
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
    def test_added_today_respects_local_timezone_boundary(self) -> None:
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


@override_settings(TIME_ZONE="UTC")
class TestRewriteNaturalDateKeywords(SimpleTestCase):
    """
    Unit tests for rewrite_natural_date_keywords function.
    """

    def _rewrite_with_now(self, query: str, now_dt: datetime) -> str:
        with mock.patch("documents.index.now", return_value=now_dt):
            return index.rewrite_natural_date_keywords(query)

    def _assert_rewrite_contains(
        self,
        query: str,
        now_dt: datetime,
        *expected_fragments: str,
    ) -> str:
        result = self._rewrite_with_now(query, now_dt)
        for fragment in expected_fragments:
            self.assertIn(fragment, result)
        return result

    def test_range_keywords(self) -> None:
        """
        Test various different range keywords
        """
        cases = [
            (
                "added:today",
                datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc),
                ("added:[20250720", "TO 20250720"),
            ),
            (
                "added:yesterday",
                datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc),
                ("added:[20250719", "TO 20250719"),
            ),
            (
                "added:this month",
                datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20250701", "TO 20250731"),
            ),
            (
                "added:previous month",
                datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20250601", "TO 20250630"),
            ),
            (
                "added:this year",
                datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20250101", "TO 20251231"),
            ),
            (
                "added:previous year",
                datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20240101", "TO 20241231"),
            ),
            # Previous quarter from July 15, 2025 is April-June.
            (
                "added:previous quarter",
                datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20250401", "TO 20250630"),
            ),
            # July 20, 2025 is a Sunday (weekday 6) so previous week is July 7-13.
            (
                "added:previous week",
                datetime(2025, 7, 20, 12, 0, 0, tzinfo=timezone.utc),
                ("added:[20250707", "TO 20250713"),
            ),
        ]

        for query, now_dt, fragments in cases:
            with self.subTest(query=query):
                self._assert_rewrite_contains(query, now_dt, *fragments)

    def test_additional_fields(self) -> None:
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)
        # created
        self._assert_rewrite_contains("created:today", fixed_now, "created:[20250720")
        # modified
        self._assert_rewrite_contains("modified:today", fixed_now, "modified:[20250720")

    def test_basic_syntax_variants(self) -> None:
        """
        Test that quoting, casing, and multi-clause queries are parsed.
        """
        fixed_now = datetime(2025, 7, 20, 15, 30, 45, tzinfo=timezone.utc)

        # quoted keywords
        result1 = self._rewrite_with_now('added:"today"', fixed_now)
        result2 = self._rewrite_with_now("added:'today'", fixed_now)
        self.assertIn("added:[20250720", result1)
        self.assertIn("added:[20250720", result2)

        # case insensitivity
        for query in ("added:TODAY", "added:Today", "added:ToDaY"):
            with self.subTest(case_variant=query):
                self._assert_rewrite_contains(query, fixed_now, "added:[20250720")

        # multiple clauses
        result = self._rewrite_with_now("added:today created:yesterday", fixed_now)
        self.assertIn("added:[20250720", result)
        self.assertIn("created:[20250719", result)

    def test_no_match(self) -> None:
        """
        Test that queries without keywords are unchanged.
        """
        query = "title:test content:example"
        result = index.rewrite_natural_date_keywords(query)
        self.assertEqual(query, result)

    @override_settings(TIME_ZONE="Pacific/Auckland")
    def test_timezone_awareness(self) -> None:
        """
        Test timezone conversion.
        """
        # July 20, 2025 1:00 AM NZST = July 19, 2025 13:00 UTC
        fixed_now = datetime(2025, 7, 20, 1, 0, 0, tzinfo=get_current_timezone())
        result = self._rewrite_with_now("added:today", fixed_now)
        # Should convert to UTC properly
        self.assertIn("added:[20250719", result)


class TestIndexResilience(DirectoriesMixin, SimpleTestCase):
    def _assert_recreate_called(self, mock_create_in) -> None:
        mock_create_in.assert_called_once()
        path_arg, schema_arg = mock_create_in.call_args.args
        self.assertEqual(path_arg, settings.INDEX_DIR)
        self.assertEqual(schema_arg.__class__.__name__, "Schema")

    def test_transient_missing_segment_does_not_force_recreate(self) -> None:
        """
        GIVEN:
            - Index directory exists
        WHEN:
            - open_index is called
            - Opening the index raises FileNotFoundError once due to a
              transient missing segment
        THEN:
            - Index is opened successfully on retry
            - Index is not recreated
        """
        file_marker = settings.INDEX_DIR / "file_marker.txt"
        file_marker.write_text("keep")
        expected_index = object()

        with (
            mock.patch("documents.index.exists_in", return_value=True),
            mock.patch(
                "documents.index.open_dir",
                side_effect=[FileNotFoundError("missing"), expected_index],
            ) as mock_open_dir,
            mock.patch(
                "documents.index.create_in",
            ) as mock_create_in,
            mock.patch(
                "documents.index.rmtree",
            ) as mock_rmtree,
        ):
            ix = index.open_index()

        self.assertIs(ix, expected_index)
        self.assertGreaterEqual(mock_open_dir.call_count, 2)
        mock_rmtree.assert_not_called()
        mock_create_in.assert_not_called()
        self.assertEqual(file_marker.read_text(), "keep")

    def test_transient_errors_exhaust_retries_and_recreate(self) -> None:
        """
        GIVEN:
            - Index directory exists
        WHEN:
            - open_index is called
            - Opening the index raises FileNotFoundError multiple times due to
              transient missing segments
        THEN:
            - Index is recreated after retries are exhausted
        """
        recreated_index = object()

        with (
            self.assertLogs("paperless.index", level="ERROR") as cm,
            mock.patch("documents.index.exists_in", return_value=True),
            mock.patch(
                "documents.index.open_dir",
                side_effect=FileNotFoundError("missing"),
            ) as mock_open_dir,
            mock.patch("documents.index.rmtree") as mock_rmtree,
            mock.patch(
                "documents.index.create_in",
                return_value=recreated_index,
            ) as mock_create_in,
        ):
            ix = index.open_index()

        self.assertIs(ix, recreated_index)
        self.assertEqual(mock_open_dir.call_count, 4)
        mock_rmtree.assert_called_once_with(settings.INDEX_DIR)
        self._assert_recreate_called(mock_create_in)
        self.assertIn(
            "Error while opening the index after retries, recreating.",
            cm.output[0],
        )

    def test_non_transient_error_recreates_index(self) -> None:
        """
        GIVEN:
            - Index directory exists
        WHEN:
            - open_index is called
            - Opening the index raises a "non-transient" error
        THEN:
            - Index is recreated
        """
        recreated_index = object()

        with (
            self.assertLogs("paperless.index", level="ERROR") as cm,
            mock.patch("documents.index.exists_in", return_value=True),
            mock.patch(
                "documents.index.open_dir",
                side_effect=RuntimeError("boom"),
            ),
            mock.patch("documents.index.rmtree") as mock_rmtree,
            mock.patch(
                "documents.index.create_in",
                return_value=recreated_index,
            ) as mock_create_in,
        ):
            ix = index.open_index()

        self.assertIs(ix, recreated_index)
        mock_rmtree.assert_called_once_with(settings.INDEX_DIR)
        self._assert_recreate_called(mock_create_in)
        self.assertIn(
            "Error while opening the index, recreating.",
            cm.output[0],
        )
