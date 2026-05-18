import datetime
from datetime import timedelta
from unittest import mock

import pytest
import time_machine
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bulk_edit import set_permissions
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import SavedView
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.search import get_backend
from documents.search import reset_backend
from documents.tests.factories import DocumentFactory
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule

pytestmark = pytest.mark.search


class TestDocumentSearchApi(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        reset_backend()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def tearDown(self) -> None:
        reset_backend()
        super().tearDown()

    def test_search(self) -> None:
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            original_filename="someepdf.pdf",
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=bank")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(results), 3)

        response = self.client.get("/api/documents/?query=september")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["original_file_name"], "someepdf.pdf")

        response = self.client.get("/api/documents/?query=statement")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(results), 2)

        response = self.client.get("/api/documents/?query=sfegdfg")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(results), 0)

    def test_simple_text_search(self) -> None:
        tagged = Tag.objects.create(name="invoice")
        matching_doc = Document.objects.create(
            title="Quarterly summary",
            content="Monthly bank report",
            checksum="T1",
            pk=11,
        )
        matching_doc.tags.add(tagged)

        metadata_only_doc = Document.objects.create(
            title="Completely unrelated",
            content="No matching terms here",
            checksum="T2",
            pk=12,
        )
        metadata_only_doc.tags.add(tagged)

        backend = get_backend()
        backend.add_or_update(matching_doc)
        backend.add_or_update(metadata_only_doc)

        response = self.client.get("/api/documents/?text=monthly")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matching_doc.id)

        response = self.client.get("/api/documents/?text=tag:invoice")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_simple_text_search_matches_substrings(self) -> None:
        matching_doc = Document.objects.create(
            title="Quarterly summary",
            content="Password reset instructions",
            checksum="T5",
            pk=15,
        )

        backend = get_backend()
        backend.add_or_update(matching_doc)

        response = self.client.get("/api/documents/?text=pass")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matching_doc.id)

        response = self.client.get("/api/documents/?text=sswo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matching_doc.id)

        response = self.client.get("/api/documents/?text=sswo re")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matching_doc.id)

    def test_simple_text_search_does_not_match_on_partial_term_overlap(self) -> None:
        non_matching_doc = Document.objects.create(
            title="Adobe Acrobat PDF Files",
            content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            checksum="T7",
            pk=17,
        )

        backend = get_backend()
        backend.add_or_update(non_matching_doc)

        response = self.client.get("/api/documents/?text=raptor")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_simple_title_search(self) -> None:
        title_match = Document.objects.create(
            title="Quarterly summary",
            content="No matching content here",
            checksum="T3",
            pk=13,
        )
        content_only = Document.objects.create(
            title="Completely unrelated",
            content="Quarterly summary appears only in content",
            checksum="T4",
            pk=14,
        )

        backend = get_backend()
        backend.add_or_update(title_match)
        backend.add_or_update(content_only)

        response = self.client.get("/api/documents/?title_search=quarterly")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], title_match.id)

    def test_simple_title_search_matches_substrings(self) -> None:
        title_match = Document.objects.create(
            title="Password handbook",
            content="No matching content here",
            checksum="T6",
            pk=16,
        )

        backend = get_backend()
        backend.add_or_update(title_match)

        response = self.client.get("/api/documents/?title_search=pass")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], title_match.id)

        response = self.client.get("/api/documents/?title_search=sswo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], title_match.id)

        response = self.client.get("/api/documents/?title_search=sswo hand")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], title_match.id)

    def test_search_rejects_multiple_search_modes(self) -> None:
        response = self.client.get("/api/documents/?text=bank&query=bank")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Specify only one of text, title_search, query, or more_like_id.",
        )

    def test_search_returns_all_for_api_version_9(self) -> None:
        d1 = Document.objects.create(
            title="invoice",
            content="bank payment",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement",
            content="bank transfer",
            checksum="B",
            pk=2,
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)

        response = self.client.get(
            "/api/documents/?query=bank",
            headers={"Accept": "application/json; version=9"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("all", response.data)
        self.assertCountEqual(response.data["all"], [d1.id, d2.id])

    def test_search_with_include_selection_data(self) -> None:
        correspondent = Correspondent.objects.create(name="c1")
        doc_type = DocumentType.objects.create(name="dt1")
        storage_path = StoragePath.objects.create(name="sp1")
        tag = Tag.objects.create(name="tag")

        matching_doc = Document.objects.create(
            title="bank statement",
            content="bank content",
            checksum="A",
            correspondent=correspondent,
            document_type=doc_type,
            storage_path=storage_path,
        )
        matching_doc.tags.add(tag)

        get_backend().add_or_update(matching_doc)

        response = self.client.get(
            "/api/documents/?query=bank&include_selection_data=true",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("selection_data", response.data)

        selected_correspondent = next(
            item
            for item in response.data["selection_data"]["selected_correspondents"]
            if item["id"] == correspondent.id
        )
        selected_tag = next(
            item
            for item in response.data["selection_data"]["selected_tags"]
            if item["id"] == tag.id
        )

        self.assertEqual(selected_correspondent["document_count"], 1)
        self.assertEqual(selected_tag["document_count"], 1)

    def test_search_custom_field_ordering(self) -> None:
        custom_field = CustomField.objects.create(
            name="Sortable field",
            data_type=CustomField.FieldDataType.INT,
        )
        d1 = Document.objects.create(
            title="first",
            content="match",
            checksum="A1",
        )
        d2 = Document.objects.create(
            title="second",
            content="match",
            checksum="B2",
        )
        d3 = Document.objects.create(
            title="third",
            content="match",
            checksum="C3",
        )
        CustomFieldInstance.objects.create(
            document=d1,
            field=custom_field,
            value_int=30,
        )
        CustomFieldInstance.objects.create(
            document=d2,
            field=custom_field,
            value_int=10,
        )
        CustomFieldInstance.objects.create(
            document=d3,
            field=custom_field,
            value_int=20,
        )

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get(
            f"/api/documents/?query=match&ordering=custom_field_{custom_field.pk}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [doc["id"] for doc in response.data["results"]],
            [d2.id, d3.id, d1.id],
        )

        response = self.client.get(
            f"/api/documents/?query=match&ordering=-custom_field_{custom_field.pk}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [doc["id"] for doc in response.data["results"]],
            [d1.id, d3.id, d2.id],
        )

    def test_search_multi_page(self) -> None:
        backend = get_backend()
        for i in range(55):
            doc = Document.objects.create(
                checksum=str(i),
                pk=i + 1,
                title=f"Document {i + 1}",
                content="content",
            )
            backend.add_or_update(doc)

        # This is here so that we test that no document gets returned twice (might happen if the paging is not working)
        seen_ids = []

        for i in range(1, 6):
            response = self.client.get(
                f"/api/documents/?query=content&page={i}&page_size=10",
            )
            results = response.data["results"]
            self.assertEqual(response.data["count"], 55)
            self.assertEqual(len(results), 10)

            for result in results:
                self.assertNotIn(result["id"], seen_ids)
                seen_ids.append(result["id"])

        response = self.client.get("/api/documents/?query=content&page=6&page_size=10")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 55)
        self.assertEqual(len(results), 5)

        for result in results:
            self.assertNotIn(result["id"], seen_ids)
            seen_ids.append(result["id"])

    def test_search_invalid_page(self) -> None:
        backend = get_backend()
        for i in range(15):
            doc = Document.objects.create(
                checksum=str(i),
                pk=i + 1,
                title=f"Document {i + 1}",
                content="content",
            )
            backend.add_or_update(doc)

        response = self.client.get("/api/documents/?query=content&page=0&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get("/api/documents/?query=content&page=3&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(
        TIME_ZONE="UTC",
    )
    def test_search_added_in_last_week(self) -> None:
        """
        GIVEN:
            - Three documents added right now
            - The timezone is UTC time
        WHEN:
            - Query for documents added in the last 7 days
        THEN:
            - All three recent documents are returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]
        # Expect 3 documents returned
        self.assertEqual(len(results), 3)

        result_map = {r["id"]: r for r in results}
        self.assertEqual(set(result_map.keys()), {1, 2, 3})
        for subset in [
            {"id": 1, "title": "invoice"},
            {"id": 2, "title": "bank statement 1"},
            {"id": 3, "title": "bank statement 3"},
        ]:
            r = result_map[subset["id"]]
            self.assertDictEqual(r, {**r, **subset})

    @override_settings(
        TIME_ZONE="America/Chicago",
    )
    def test_search_added_in_last_week_with_timezone_behind(self) -> None:
        """
        GIVEN:
            - Two documents added right now
            - One document added over a week ago
            - The timezone is behind UTC time (-6)
        WHEN:
            - Query for documents added in the last 7 days
        THEN:
            - The two recent documents are returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            # 7 days, 1 hour and 1 minute ago
            added=timezone.now() - timedelta(days=7, hours=1, minutes=1),
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        result_map = {r["id"]: r for r in results}
        self.assertEqual(set(result_map.keys()), {1, 2})
        for subset in [
            {"id": 1, "title": "invoice"},
            {"id": 2, "title": "bank statement 1"},
        ]:
            r = result_map[subset["id"]]
            self.assertDictEqual(r, {**r, **subset})

    @override_settings(
        TIME_ZONE="Europe/Sofia",
    )
    def test_search_added_in_last_week_with_timezone_ahead(self) -> None:
        """
        GIVEN:
            - Two documents added right now
            - One document added over a week ago
            - The timezone is behind UTC time (+2)
        WHEN:
            - Query for documents added in the last 7 days
        THEN:
            - The two recent documents are returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            # 7 days, 1 hour and 1 minute ago
            added=timezone.now() - timedelta(days=7, hours=1, minutes=1),
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        result_map = {r["id"]: r for r in results}
        self.assertEqual(set(result_map.keys()), {1, 2})
        for subset in [
            {"id": 1, "title": "invoice"},
            {"id": 2, "title": "bank statement 1"},
        ]:
            r = result_map[subset["id"]]
            self.assertDictEqual(r, {**r, **subset})

    def test_search_added_in_last_month(self) -> None:
        """
        GIVEN:
            - One document added right now
            - One documents added about a week ago
            - One document added over 1 month
        WHEN:
            - Query for documents added in the last month
        THEN:
            - The two recent documents are returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
            # 1 month, 1 day ago
            added=timezone.now() - relativedelta(months=1, days=1),
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            # 7 days, 1 hour and 1 minute ago
            added=timezone.now() - timedelta(days=7, hours=1, minutes=1),
        )

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:[-1 month to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        result_map = {r["id"]: r for r in results}
        self.assertEqual(set(result_map.keys()), {1, 3})
        for subset in [
            {"id": 1, "title": "invoice"},
            {"id": 3, "title": "bank statement 3"},
        ]:
            r = result_map[subset["id"]]
            self.assertDictEqual(r, {**r, **subset})

    @override_settings(
        TIME_ZONE="America/Denver",
    )
    def test_search_added_in_last_month_timezone_behind(self) -> None:
        """
        GIVEN:
            - One document added right now
            - One documents added about a week ago
            - One document added over 1 month
            - The timezone is behind UTC time (-6 or -7)
        WHEN:
            - Query for documents added in the last month
        THEN:
            - The two recent documents are returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
            # 1 month, 1 day ago
            added=timezone.now() - relativedelta(months=1, days=1),
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            # 7 days, 1 hour and 1 minute ago
            added=timezone.now() - timedelta(days=7, hours=1, minutes=1),
        )

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:[-1 month to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        result_map = {r["id"]: r for r in results}
        self.assertEqual(set(result_map.keys()), {1, 3})
        for subset in [
            {"id": 1, "title": "invoice"},
            {"id": 3, "title": "bank statement 3"},
        ]:
            r = result_map[subset["id"]]
            self.assertDictEqual(r, {**r, **subset})

    @override_settings(
        TIME_ZONE="Europe/Sofia",
    )
    def test_search_added_specific_date_with_timezone_ahead(self) -> None:
        """
        GIVEN:
            - Two documents added right now
            - One document added on a specific date
            - The timezone is behind UTC time (+2)
        WHEN:
            - Query for documents added on a specific date
        THEN:
            - The one document is returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
            # specific time zone aware date
            added=timezone.make_aware(datetime.datetime(2023, 12, 1)),
        )
        # refresh doc instance to ensure we operate on date objects that Django uses
        # Django converts dates to UTC
        d3.refresh_from_db()

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/documents/?query=added:20231201")
        results = response.data["results"]

        # Expect 1 document returned
        self.assertEqual(len(results), 1)

        self.assertEqual(results[0]["id"], 3)
        self.assertEqual(results[0]["title"], "bank statement 3")

    def test_search_added_invalid_date(self) -> None:
        """
        GIVEN:
            - One document added right now
        WHEN:
            - Query with invalid added date
        THEN:
            - 400 Bad Request returned (Tantivy rejects invalid date field syntax)
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )

        get_backend().add_or_update(d1)

        response = self.client.get("/api/documents/?query=added:invalid-date")

        # Tantivy rejects unparsable field queries with a 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        TIME_ZONE="UTC",
    )
    @time_machine.travel(
        datetime.datetime(2026, 7, 15, 12, 0, tzinfo=datetime.UTC),
        tick=False,
    )
    def test_search_added_previous_quarter(self) -> None:
        """
        GIVEN:
            - Documents inside and outside the previous quarter
        WHEN:
            - Query with the legacy natural-language phrase used by the UI
        THEN:
            - Previous-quarter documents are returned
        """
        d1 = DocumentFactory.create(
            title="quarterly statement april",
            content="bank statement",
            added=datetime.datetime(2026, 4, 10, 12, 0, tzinfo=datetime.UTC),
        )
        d2 = DocumentFactory.create(
            title="quarterly statement june",
            content="bank statement",
            added=datetime.datetime(2026, 6, 20, 12, 0, tzinfo=datetime.UTC),
        )
        d3 = DocumentFactory.create(
            title="quarterly statement july",
            content="bank statement",
            added=datetime.datetime(2026, 7, 10, 12, 0, tzinfo=datetime.UTC),
        )

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get('/api/documents/?query=added:"previous quarter"')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]
        self.assertEqual({r["id"] for r in results}, {1, 2})

    @mock.patch("documents.search._backend.TantivyBackend.autocomplete")
    def test_search_autocomplete_limits(self, m) -> None:
        """
        GIVEN:
            - No pre-conditions
        WHEN:
            - API request for autocomplete is made by user with various limit requests
        THEN:
            - Limit requests are validated
            - Limit requests are obeyed
        """

        m.side_effect = lambda term, limit, user=None: [term for _ in range(limit)]

        response = self.client.get("/api/search/autocomplete/?term=test")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

        response = self.client.get("/api/search/autocomplete/?term=test&limit=20")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 20)

        response = self.client.get("/api/search/autocomplete/?term=test&limit=-1")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get("/api/search/autocomplete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get("/api/search/autocomplete/?term=")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

    def test_search_autocomplete_respect_permissions(self) -> None:
        """
        GIVEN:
            - Multiple users and documents with & without permissions
        WHEN:
            - API request for autocomplete is made by user with or without permissions
        THEN:
            - Terms only within docs user has access to are returned
        """
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")

        self.client.force_authenticate(user=u1)

        d1 = Document.objects.create(
            title="doc1",
            content="apples",
            checksum="1",
            owner=u1,
        )
        d2 = Document.objects.create(
            title="doc2",
            content="applebaum",
            checksum="2",
            owner=u1,
        )
        d3 = Document.objects.create(
            title="doc3",
            content="appletini",
            checksum="3",
            owner=u1,
        )

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, ["applebaum", "apples", "appletini"])

        d3.owner = u2
        d3.save()
        backend.add_or_update(d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, ["applebaum", "apples"])

        assign_perm("view_document", u1, d3)
        backend.add_or_update(d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, ["applebaum", "apples", "appletini"])

    def test_search_autocomplete_field_name_match(self) -> None:
        """
        GIVEN:
            - One document exists in index (must be one document to experience the crash)
        WHEN:
            - API request for autocomplete is made with a query which looks like a schema field
        THEN:
            - No autocomplete terms returns
            - No UnicodeDecodeError due to weird binary data returned from index
        """
        d1 = Document.objects.create(
            title="doc1",
            content="my really neat document",
            checksum="1",
        )

        get_backend().add_or_update(d1)

        response = self.client.get("/api/search/autocomplete/?term=created:2023")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_search_autocomplete_search_term(self) -> None:
        """
        GIVEN:
            - Search results for autocomplete include the exact search term
        WHEN:
            - API request for autocomplete
        THEN:
            - The search term is returned first in the autocomplete results
        """
        d1 = Document.objects.create(
            title="doc1",
            content="automobile automatic autobots automobile auto",
            checksum="1",
        )

        get_backend().add_or_update(d1)

        response = self.client.get("/api/search/autocomplete/?term=auto")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0], "auto")

    def test_search_no_spelling_suggestion(self) -> None:
        """
        GIVEN:
            - Documents exist with various terms
        WHEN:
            - Query for documents with any term
        THEN:
            - corrected_query is always None (Tantivy has no spell correction)
        """
        backend = get_backend()
        for i in range(5):
            doc = Document.objects.create(
                checksum=str(i),
                pk=i + 1,
                title=f"Document {i + 1}",
                content=f"Things document {i + 1}",
            )
            backend.add_or_update(doc)

        response = self.client.get("/api/documents/?query=thing")
        self.assertIsNone(response.data["corrected_query"])

        response = self.client.get("/api/documents/?query=things")
        self.assertIsNone(response.data["corrected_query"])

    def test_search_spelling_suggestion_suppressed_for_private_terms(self) -> None:
        owner = User.objects.create_user("owner")
        attacker = User.objects.create_user("attacker")
        attacker.user_permissions.add(
            Permission.objects.get(codename="view_document"),
        )

        backend = get_backend()
        for i in range(5):
            private_doc = Document.objects.create(
                checksum=f"p{i}",
                pk=100 + i,
                title=f"Private Document {i + 1}",
                content=f"treasury document {i + 1}",
                owner=owner,
            )
            visible_doc = Document.objects.create(
                checksum=f"v{i}",
                pk=200 + i,
                title=f"Visible Document {i + 1}",
                content=f"public ledger {i + 1}",
                owner=attacker,
            )
            backend.add_or_update(private_doc)
            backend.add_or_update(visible_doc)

        self.client.force_authenticate(user=attacker)

        response = self.client.get("/api/documents/?query=treasurx")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertIsNone(response.data["corrected_query"])

    def test_search_more_like(self) -> None:
        """
        GIVEN:
            - Documents exist which have similar content
            - At least 1 document exists which is not similar in content
        WHEN:
            - API request for more like a given document
        THEN:
            - The similar documents are returned from the API request
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement 1",
            content="things i paid for in august",
            pk=2,
            checksum="B",
        )
        d3 = Document.objects.create(
            title="bank statement 3",
            content="things i paid for in september",
            pk=3,
            checksum="C",
        )
        d4 = Document.objects.create(
            title="Quarterly Report",
            content="quarterly revenue profit margin earnings growth",
            pk=4,
            checksum="ABC",
        )
        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)
        backend.add_or_update(d4)

        response = self.client.get(f"/api/documents/?more_like_id={d2.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertGreaterEqual(len(results), 1)
        result_ids = [r["id"] for r in results]
        self.assertIn(d3.id, result_ids)
        self.assertNotIn(d4.id, result_ids)

    def test_more_like_requires_id_of_existing_document(self) -> None:
        """
        GIVEN:
            - No document with the given ID exists
        WHEN:
            - API request for more like a given document is made with a non-existent document ID
        THEN:
            - 403 Forbidden is returned with an appropriate error message
        """
        response = self.client.get("/api/documents/?more_like_id=9999")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Invalid more_like_id")

    def test_search_more_like_requires_view_permission_on_seed_document(
        self,
    ) -> None:
        """
        GIVEN:
            - A user can search documents they own
            - Another user's private document exists with similar content
        WHEN:
            - The user requests more-like-this for the private seed document
        THEN:
            - The request is rejected
        """
        owner = User.objects.create_user("owner")
        attacker = User.objects.create_user("attacker")
        attacker.user_permissions.add(
            Permission.objects.get(codename="view_document"),
        )

        private_seed = Document.objects.create(
            title="private bank statement",
            content="quarterly treasury bank statement wire transfer",
            checksum="seed",
            owner=owner,
            pk=10,
        )
        visible_doc = Document.objects.create(
            title="attacker-visible match",
            content="quarterly treasury bank statement wire transfer summary",
            checksum="visible",
            owner=attacker,
            pk=11,
        )
        other_doc = Document.objects.create(
            title="unrelated",
            content="completely different topic",
            checksum="other",
            owner=attacker,
            pk=12,
        )

        backend = get_backend()
        backend.add_or_update(private_seed)
        backend.add_or_update(visible_doc)
        backend.add_or_update(other_doc)

        self.client.force_authenticate(user=attacker)

        response = self.client.get(
            f"/api/documents/?more_like_id={private_seed.id}",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions.")

    def test_search_filtering(self) -> None:
        t = Tag.objects.create(name="tag")
        t2 = Tag.objects.create(name="tag2")
        c = Correspondent.objects.create(name="correspondent")
        c2 = Correspondent.objects.create(name="correspondent2")
        dt = DocumentType.objects.create(name="type")
        dt2 = DocumentType.objects.create(name="type2")
        sp = StoragePath.objects.create(name="path")
        sp2 = StoragePath.objects.create(name="path2")
        cf1 = CustomField.objects.create(
            name="string field",
            data_type=CustomField.FieldDataType.STRING,
        )
        cf2 = CustomField.objects.create(
            name="number field",
            data_type=CustomField.FieldDataType.INT,
        )

        d1 = Document.objects.create(checksum="1", correspondent=c, content="test")
        d2 = Document.objects.create(checksum="2", document_type=dt, content="test")
        d3 = Document.objects.create(checksum="3", content="test")

        d3.tags.add(t)
        d3.tags.add(t2)
        d4 = Document.objects.create(
            checksum="4",
            created=datetime.date(2020, 7, 13),
            content="test",
            original_filename="doc4.pdf",
        )
        d4.tags.add(t2)
        d5 = Document.objects.create(
            checksum="5",
            added=timezone.make_aware(datetime.datetime(2020, 7, 13)),
            content="test",
            original_filename="doc5.pdf",
        )
        Document.objects.create(checksum="6", content="test2")
        d7 = Document.objects.create(checksum="7", storage_path=sp, content="test")
        d8 = Document.objects.create(
            checksum="foo",
            correspondent=c2,
            document_type=dt2,
            storage_path=sp2,
            content="test",
        )

        cf1_d1 = CustomFieldInstance.objects.create(
            document=d1,
            field=cf1,
            value_text="foobard1",
        )
        cf2_d1 = CustomFieldInstance.objects.create(
            document=d1,
            field=cf2,
            value_int=999,
        )
        cf1_d4 = CustomFieldInstance.objects.create(
            document=d4,
            field=cf1,
            value_text="foobard4",
        )

        backend = get_backend()
        for doc in Document.objects.all():
            backend.add_or_update(doc)

        def search_query(q):
            r = self.client.get("/api/documents/?query=test" + q)
            self.assertEqual(r.status_code, status.HTTP_200_OK)
            return [hit["id"] for hit in r.data["results"]]

        self.assertCountEqual(
            search_query(""),
            [d1.id, d2.id, d3.id, d4.id, d5.id, d7.id, d8.id],
        )
        self.assertCountEqual(search_query("&is_tagged=true"), [d3.id, d4.id])
        self.assertCountEqual(
            search_query("&is_tagged=false"),
            [d1.id, d2.id, d5.id, d7.id, d8.id],
        )
        self.assertCountEqual(search_query("&correspondent__id=" + str(c.id)), [d1.id])
        self.assertCountEqual(
            search_query(f"&correspondent__id__in={c.id},{c2.id}"),
            [d1.id, d8.id],
        )
        self.assertCountEqual(
            search_query("&correspondent__id__none=" + str(c.id)),
            [d2.id, d3.id, d4.id, d5.id, d7.id, d8.id],
        )
        self.assertCountEqual(search_query("&document_type__id=" + str(dt.id)), [d2.id])
        self.assertCountEqual(
            search_query(f"&document_type__id__in={dt.id},{dt2.id}"),
            [d2.id, d8.id],
        )
        self.assertCountEqual(
            search_query("&document_type__id__none=" + str(dt.id)),
            [d1.id, d3.id, d4.id, d5.id, d7.id, d8.id],
        )
        self.assertCountEqual(search_query("&storage_path__id=" + str(sp.id)), [d7.id])
        self.assertCountEqual(
            search_query(f"&storage_path__id__in={sp.id},{sp2.id}"),
            [d7.id, d8.id],
        )
        self.assertCountEqual(
            search_query("&storage_path__id__none=" + str(sp.id)),
            [d1.id, d2.id, d3.id, d4.id, d5.id, d8.id],
        )

        self.assertCountEqual(
            search_query("&storage_path__isnull=true"),
            [d1.id, d2.id, d3.id, d4.id, d5.id],
        )
        self.assertCountEqual(
            search_query("&correspondent__isnull=true"),
            [d2.id, d3.id, d4.id, d5.id, d7.id],
        )
        self.assertCountEqual(
            search_query("&document_type__isnull=true"),
            [d1.id, d3.id, d4.id, d5.id, d7.id],
        )
        self.assertCountEqual(
            search_query("&tags__id__all=" + str(t.id) + "," + str(t2.id)),
            [d3.id],
        )
        self.assertCountEqual(search_query("&tags__id__all=" + str(t.id)), [d3.id])
        self.assertCountEqual(
            search_query("&tags__id__all=" + str(t2.id)),
            [d3.id, d4.id],
        )
        self.assertCountEqual(
            search_query(f"&tags__id__in={t.id},{t2.id}"),
            [d3.id, d4.id],
        )
        self.assertCountEqual(
            search_query(f"&tags__id__none={t.id},{t2.id}"),
            [d1.id, d2.id, d5.id, d7.id, d8.id],
        )

        self.assertIn(
            d4.id,
            search_query(
                "&created__date__lt="
                + datetime.datetime(2020, 9, 2).strftime("%Y-%m-%d"),
            ),
        )
        self.assertNotIn(
            d4.id,
            search_query(
                "&created__date__gt="
                + datetime.datetime(2020, 9, 2).strftime("%Y-%m-%d"),
            ),
        )

        self.assertNotIn(
            d4.id,
            search_query(
                "&created__date__lt="
                + datetime.datetime(2020, 1, 2).strftime("%Y-%m-%d"),
            ),
        )
        self.assertIn(
            d4.id,
            search_query(
                "&created__date__gt="
                + datetime.datetime(2020, 1, 2).strftime("%Y-%m-%d"),
            ),
        )

        self.assertIn(
            d5.id,
            search_query(
                "&added__date__lt="
                + datetime.datetime(2020, 9, 2).strftime("%Y-%m-%d"),
            ),
        )
        self.assertNotIn(
            d5.id,
            search_query(
                "&added__date__gt="
                + datetime.datetime(2020, 9, 2).strftime("%Y-%m-%d"),
            ),
        )

        self.assertNotIn(
            d5.id,
            search_query(
                "&added__date__lt="
                + datetime.datetime(2020, 1, 2).strftime("%Y-%m-%d"),
            ),
        )

        self.assertIn(
            d5.id,
            search_query(
                "&added__date__gt="
                + datetime.datetime(2020, 1, 2).strftime("%Y-%m-%d"),
            ),
        )

        self.assertEqual(
            search_query("&checksum__icontains=foo"),
            [d8.id],
        )

        self.assertCountEqual(
            search_query("&original_filename__istartswith=doc"),
            [d4.id, d5.id],
        )

        self.assertIn(
            d1.id,
            search_query(
                "&custom_fields__icontains=" + cf1_d1.value,
            ),
        )

        self.assertIn(
            d1.id,
            search_query(
                "&custom_fields__icontains=" + str(cf2_d1.value),
            ),
        )

        self.assertIn(
            d4.id,
            search_query(
                "&custom_fields__icontains=" + cf1_d4.value,
            ),
        )

        self.assertIn(
            d4.id,
            search_query(
                "&has_custom_fields=1",
            ),
        )

        self.assertIn(
            d4.id,
            search_query(
                "&custom_fields__id__in=" + str(cf1.id),
            ),
        )

        self.assertIn(
            d4.id,
            search_query(
                "&custom_fields__id__all=" + str(cf1.id),
            ),
        )

        self.assertNotIn(
            d4.id,
            search_query(
                "&custom_fields__id__none=" + str(cf1.id),
            ),
        )

    def test_search_filtering_respect_owner(self) -> None:
        """
        GIVEN:
            - Documents with owners set & without
        WHEN:
            - API request for advanced query (search) is made by non-superuser
            - API request for advanced query (search) is made by superuser
        THEN:
            - Only owned docs are returned for regular users
            - All docs are returned for superuser
        """
        superuser = User.objects.create_superuser("superuser")
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")
        u1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        u2.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        Document.objects.create(checksum="1", content="test 1", owner=u1)
        Document.objects.create(checksum="2", content="test 2", owner=u2)
        Document.objects.create(checksum="3", content="test 3", owner=u2)
        Document.objects.create(checksum="4", content="test 4")

        backend = get_backend()
        for doc in Document.objects.all():
            backend.add_or_update(doc)

        self.client.force_authenticate(user=u1)
        r = self.client.get("/api/documents/?query=test")
        self.assertEqual(r.data["count"], 2)
        r = self.client.get("/api/documents/?query=test&document_type__id__none=1")
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(f"/api/documents/?query=test&owner__id__none={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/documents/?query=test&owner__id__in={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(
            f"/api/documents/?query=test&owner__id__none={u1.id}&owner__isnull=true",
        )
        self.assertEqual(r.data["count"], 1)

        self.client.force_authenticate(user=u2)
        r = self.client.get("/api/documents/?query=test")
        self.assertEqual(r.data["count"], 3)
        r = self.client.get("/api/documents/?query=test&document_type__id__none=1")
        self.assertEqual(r.data["count"], 3)
        r = self.client.get(f"/api/documents/?query=test&owner__id__none={u2.id}")
        self.assertEqual(r.data["count"], 1)

        self.client.force_authenticate(user=superuser)
        r = self.client.get("/api/documents/?query=test")
        self.assertEqual(r.data["count"], 4)
        r = self.client.get("/api/documents/?query=test&document_type__id__none=1")
        self.assertEqual(r.data["count"], 4)
        r = self.client.get(f"/api/documents/?query=test&owner__id__none={u1.id}")
        self.assertEqual(r.data["count"], 3)

    def test_search_filtering_with_object_perms(self) -> None:
        """
        GIVEN:
            - Documents with granted view permissions to others
        WHEN:
            - API request for advanced query (search) is made by user
        THEN:
            - Only docs with granted view permissions are returned
        """
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")
        u1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        u2.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        d1 = Document.objects.create(checksum="1", content="test 1", owner=u1)
        d2 = Document.objects.create(checksum="2", content="test 2", owner=u2)
        d3 = Document.objects.create(checksum="3", content="test 3", owner=u2)
        Document.objects.create(checksum="4", content="test 4")

        backend = get_backend()
        for doc in Document.objects.all():
            backend.add_or_update(doc)

        self.client.force_authenticate(user=u1)
        r = self.client.get("/api/documents/?query=test")
        self.assertEqual(r.data["count"], 2)
        r = self.client.get("/api/documents/?query=test&document_type__id__none=1")
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(f"/api/documents/?query=test&owner__id__none={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/documents/?query=test&owner__id={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/documents/?query=test&owner__id__in={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get("/api/documents/?query=test&owner__isnull=true")
        self.assertEqual(r.data["count"], 1)

        assign_perm("view_document", u1, d2)
        assign_perm("view_document", u1, d3)
        assign_perm("view_document", u2, d1)

        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)

        self.client.force_authenticate(user=u1)
        r = self.client.get("/api/documents/?query=test")
        self.assertEqual(r.data["count"], 4)
        r = self.client.get("/api/documents/?query=test&document_type__id__none=1")
        self.assertEqual(r.data["count"], 4)
        r = self.client.get(f"/api/documents/?query=test&owner__id__none={u1.id}")
        self.assertEqual(r.data["count"], 3)
        r = self.client.get(f"/api/documents/?query=test&owner__id={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/documents/?query=test&owner__id__in={u1.id}")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get("/api/documents/?query=test&owner__isnull=true")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/documents/?query=test&shared_by__id={u1.id}")
        self.assertEqual(r.data["count"], 1)

    def test_search_sorting(self) -> None:
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")
        c1 = Correspondent.objects.create(name="corres Ax")
        c2 = Correspondent.objects.create(name="corres Cx")
        c3 = Correspondent.objects.create(name="corres Bx")
        d1 = Document.objects.create(
            checksum="1",
            correspondent=c1,
            content="test",
            archive_serial_number=2,
            title="3",
            owner=u1,
        )
        d2 = Document.objects.create(
            checksum="2",
            correspondent=c2,
            content="test",
            archive_serial_number=3,
            title="2",
            owner=u2,
        )
        d3 = Document.objects.create(
            checksum="3",
            correspondent=c3,
            content="test",
            archive_serial_number=1,
            title="1",
        )
        Note.objects.create(
            note="This is a note.",
            document=d1,
            user=u1,
        )
        Note.objects.create(
            note="This is a note.",
            document=d1,
            user=u1,
        )
        Note.objects.create(
            note="This is a note.",
            document=d3,
            user=u1,
        )

        backend = get_backend()
        for doc in Document.objects.all():
            backend.add_or_update(doc)

        def search_query(q):
            r = self.client.get("/api/documents/?query=test" + q)
            self.assertEqual(r.status_code, status.HTTP_200_OK)
            return [hit["id"] for hit in r.data["results"]]

        self.assertListEqual(
            search_query("&ordering=archive_serial_number"),
            [d3.id, d1.id, d2.id],
        )
        self.assertListEqual(
            search_query("&ordering=-archive_serial_number"),
            [d2.id, d1.id, d3.id],
        )
        self.assertListEqual(search_query("&ordering=title"), [d3.id, d2.id, d1.id])
        self.assertListEqual(search_query("&ordering=-title"), [d1.id, d2.id, d3.id])
        self.assertListEqual(
            search_query("&ordering=correspondent__name"),
            [d1.id, d3.id, d2.id],
        )
        self.assertListEqual(
            search_query("&ordering=-correspondent__name"),
            [d2.id, d3.id, d1.id],
        )
        self.assertListEqual(
            search_query("&ordering=num_notes"),
            [d2.id, d3.id, d1.id],
        )
        self.assertListEqual(
            search_query("&ordering=-num_notes"),
            [d1.id, d3.id, d2.id],
        )
        # owner sort: ORM orders by owner_id (integer); NULLs first in SQLite ASC
        self.assertListEqual(
            search_query("&ordering=owner"),
            [d3.id, d1.id, d2.id],
        )
        self.assertListEqual(
            search_query("&ordering=-owner"),
            [d2.id, d1.id, d3.id],
        )

    def test_search_ordering_by_score(self) -> None:
        """ordering=-score must return results in descending relevance order (best first)."""
        backend = get_backend()
        # doc_high has more occurrences of the search term → higher BM25 score
        doc_low = Document.objects.create(
            title="score sort low",
            content="apple",
            checksum="SCL1",
        )
        doc_high = Document.objects.create(
            title="score sort high",
            content="apple apple apple apple apple",
            checksum="SCH1",
        )
        backend.add_or_update(doc_low)
        backend.add_or_update(doc_high)

        # -score = descending = best first (highest score)
        response = self.client.get("/api/documents/?query=apple&ordering=-score")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(
            ids[0],
            doc_high.id,
            "Most relevant doc should be first for -score",
        )

        # score = ascending = worst first (lowest score)
        response = self.client.get("/api/documents/?query=apple&ordering=score")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(
            ids[0],
            doc_low.id,
            "Least relevant doc should be first for +score",
        )

    def test_search_with_tantivy_native_sort(self) -> None:
        """When ordering by a Tantivy-sortable field, results must be correctly sorted."""
        backend = get_backend()
        for i, asn in enumerate([30, 10, 20]):
            doc = Document.objects.create(
                title=f"sortable doc {i}",
                content="searchable content",
                checksum=f"TNS{i}",
                archive_serial_number=asn,
            )
            backend.add_or_update(doc)

        response = self.client.get(
            "/api/documents/?query=searchable&ordering=archive_serial_number",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asns = [doc["archive_serial_number"] for doc in response.data["results"]]
        self.assertEqual(asns, [10, 20, 30])

        response = self.client.get(
            "/api/documents/?query=searchable&ordering=-archive_serial_number",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asns = [doc["archive_serial_number"] for doc in response.data["results"]]
        self.assertEqual(asns, [30, 20, 10])

    def test_search_page_2_returns_correct_slice(self) -> None:
        """Page 2 must return the second slice, not overlap with page 1."""
        backend = get_backend()
        for i in range(10):
            doc = Document.objects.create(
                title=f"doc {i}",
                content="paginated content",
                checksum=f"PG2{i}",
                archive_serial_number=i + 1,
            )
            backend.add_or_update(doc)

        response = self.client.get(
            "/api/documents/?query=paginated&ordering=archive_serial_number&page=1&page_size=3",
        )
        page1_ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(len(page1_ids), 3)

        response = self.client.get(
            "/api/documents/?query=paginated&ordering=archive_serial_number&page=2&page_size=3",
        )
        page2_ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(len(page2_ids), 3)

        # No overlap between pages
        self.assertEqual(set(page1_ids) & set(page2_ids), set())
        # Page 2 ASNs are higher than page 1
        page1_asns = [
            Document.objects.get(pk=pk).archive_serial_number for pk in page1_ids
        ]
        page2_asns = [
            Document.objects.get(pk=pk).archive_serial_number for pk in page2_ids
        ]
        self.assertTrue(max(page1_asns) < min(page2_asns))

    def test_search_all_field_contains_all_ids_when_paginated(self) -> None:
        """The 'all' field must contain every matching ID, even when paginated."""
        backend = get_backend()
        doc_ids = []
        for i in range(10):
            doc = Document.objects.create(
                title=f"all field doc {i}",
                content="allfield content",
                checksum=f"AF{i}",
            )
            backend.add_or_update(doc)
            doc_ids.append(doc.pk)

        response = self.client.get(
            "/api/documents/?query=allfield&page=1&page_size=3",
            headers={"Accept": "application/json; version=9"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        # "all" must contain ALL 10 matching IDs
        self.assertCountEqual(response.data["all"], doc_ids)

    @mock.patch("documents.bulk_edit.bulk_update_documents")
    def test_global_search(self, m) -> None:
        """
        GIVEN:
            - Multiple documents and objects
        WHEN:
            - Global search query is made
        THEN:
            - Appropriately filtered results are returned
        """
        d1 = Document.objects.create(
            title="invoice doc1",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )
        d2 = Document.objects.create(
            title="bank statement doc2",
            content="things i paid for in august",
            checksum="B",
            pk=2,
        )
        d3 = Document.objects.create(
            title="tax bill doc3",
            content="no b word",
            checksum="C",
            pk=3,
        )
        # The below two documents are owned by user2 and shouldn't show up in results!
        d4 = Document.objects.create(
            title="doc 4 owned by user2",
            content="bank bank bank bank 4",
            checksum="D",
            pk=4,
        )
        d5 = Document.objects.create(
            title="doc 5 owned by user2",
            content="bank bank bank bank 5",
            checksum="E",
            pk=5,
        )

        user1 = User.objects.create_user("bank user1")
        user2 = User.objects.create_superuser("user2")
        group1 = Group.objects.create(name="bank group1")
        Group.objects.create(name="group2")

        user1.user_permissions.add(
            *Permission.objects.filter(codename__startswith="view_").exclude(
                content_type__app_label="admin",
            ),
        )
        set_permissions([4, 5], set_permissions={}, owner=user2, merge=False)

        backend = get_backend()
        backend.add_or_update(d1)
        backend.add_or_update(d2)
        backend.add_or_update(d3)
        backend.add_or_update(d4)
        backend.add_or_update(d5)

        correspondent1 = Correspondent.objects.create(name="bank correspondent 1")
        Correspondent.objects.create(name="correspondent 2")
        document_type1 = DocumentType.objects.create(name="bank invoice")
        DocumentType.objects.create(name="invoice")
        storage_path1 = StoragePath.objects.create(name="bank path 1", path="path1")
        StoragePath.objects.create(name="path 2", path="path2")
        tag1 = Tag.objects.create(name="bank tag1")
        Tag.objects.create(name="tag2")

        shared_view = SavedView.objects.create(
            name="bank view",
            sort_field="",
            owner=user2,
        )
        assign_perm("view_savedview", user1, shared_view)
        mail_account1 = MailAccount.objects.create(name="bank mail account 1")
        mail_account2 = MailAccount.objects.create(name="mail account 2")
        mail_rule1 = MailRule.objects.create(
            name="bank mail rule 1",
            account=mail_account1,
            action=MailRule.MailAction.MOVE,
        )
        MailRule.objects.create(
            name="mail rule 2",
            account=mail_account2,
            action=MailRule.MailAction.MOVE,
        )
        custom_field1 = CustomField.objects.create(
            name="bank custom field 1",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomField.objects.create(
            name="custom field 2",
            data_type=CustomField.FieldDataType.INT,
        )
        workflow1 = Workflow.objects.create(name="bank workflow 1")
        Workflow.objects.create(name="workflow 2")

        self.client.force_authenticate(user1)

        response = self.client.get("/api/search/?query=bank")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data
        self.assertEqual(len(results["documents"]), 2)
        self.assertEqual(len(results["saved_views"]), 1)
        self.assertNotEqual(results["documents"][0]["id"], d3.id)
        self.assertNotEqual(results["documents"][1]["id"], d3.id)
        self.assertEqual(results["correspondents"][0]["id"], correspondent1.id)
        self.assertEqual(results["document_types"][0]["id"], document_type1.id)
        self.assertEqual(results["storage_paths"][0]["id"], storage_path1.id)
        self.assertEqual(results["tags"][0]["id"], tag1.id)
        self.assertEqual(results["users"][0]["id"], user1.id)
        self.assertEqual(results["groups"][0]["id"], group1.id)
        self.assertEqual(results["mail_accounts"][0]["id"], mail_account1.id)
        self.assertEqual(results["mail_rules"][0]["id"], mail_rule1.id)
        self.assertEqual(results["custom_fields"][0]["id"], custom_field1.id)
        self.assertEqual(results["workflows"][0]["id"], workflow1.id)

    def test_global_search_db_only_limits_documents_to_title_matches(self) -> None:
        title_match = Document.objects.create(
            title="bank statement",
            content="no additional terms",
            checksum="GS1",
            pk=21,
        )
        content_only = Document.objects.create(
            title="not a title match",
            content="bank appears only in content",
            checksum="GS2",
            pk=22,
        )

        backend = get_backend()
        backend.add_or_update(title_match)
        backend.add_or_update(content_only)

        self.client.force_authenticate(self.user)

        response = self.client.get("/api/search/?query=bank&db_only=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["documents"]), 1)
        self.assertEqual(response.data["documents"][0]["id"], title_match.id)

    def test_global_search_filters_owned_mail_objects(self) -> None:
        user1 = User.objects.create_user("mail-search-user")
        user2 = User.objects.create_user("other-mail-search-user")
        user1.user_permissions.add(
            Permission.objects.get(codename="view_mailaccount"),
            Permission.objects.get(codename="view_mailrule"),
        )

        own_account = MailAccount.objects.create(
            name="bank owned account",
            username="owner@example.com",
            password="secret",
            imap_server="imap.owner.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
            owner=user1,
        )
        other_account = MailAccount.objects.create(
            name="bank other account",
            username="other@example.com",
            password="secret",
            imap_server="imap.other.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
            owner=user2,
        )
        unowned_account = MailAccount.objects.create(
            name="bank shared account",
            username="shared@example.com",
            password="secret",
            imap_server="imap.shared.example.com",
            imap_port=993,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        own_rule = MailRule.objects.create(
            name="bank owned rule",
            account=own_account,
            action=MailRule.MailAction.MOVE,
            owner=user1,
        )
        other_rule = MailRule.objects.create(
            name="bank other rule",
            account=other_account,
            action=MailRule.MailAction.MOVE,
            owner=user2,
        )
        unowned_rule = MailRule.objects.create(
            name="bank shared rule",
            account=unowned_account,
            action=MailRule.MailAction.MOVE,
        )

        self.client.force_authenticate(user1)

        response = self.client.get("/api/search/?query=bank")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(
            [account["id"] for account in response.data["mail_accounts"]],
            [own_account.id, unowned_account.id],
        )
        self.assertCountEqual(
            [rule["id"] for rule in response.data["mail_rules"]],
            [own_rule.id, unowned_rule.id],
        )
        self.assertNotIn(
            other_account.id,
            [account["id"] for account in response.data["mail_accounts"]],
        )
        self.assertNotIn(
            other_rule.id,
            [rule["id"] for rule in response.data["mail_rules"]],
        )

    def test_global_search_bad_request(self) -> None:
        """
        WHEN:
            - Global search query is made without or with query < 3 characters
        THEN:
            - Error is returned
        """
        response = self.client.get("/api/search/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get("/api/search/?query=no")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
