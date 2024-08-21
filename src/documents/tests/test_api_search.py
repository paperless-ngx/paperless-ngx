import datetime
from datetime import timedelta
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase
from whoosh.writing import AsyncWriter

from documents import index
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
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestDocumentSearchApi(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_search(self):
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
        with AsyncWriter(index.open_index()) as writer:
            # Note to future self: there is a reason we dont use a model signal handler to update the index: some operations edit many documents at once
            # (retagger, renamer) and we don't want to open a writer for each of these, but rather perform the entire operation with one writer.
            # That's why we can't open the writer in a model on_save handler or something.
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)
        response = self.client.get("/api/documents/?query=bank")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(results), 3)
        self.assertCountEqual(response.data["all"], [d1.id, d2.id, d3.id])

        response = self.client.get("/api/documents/?query=september")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(results), 1)
        self.assertCountEqual(response.data["all"], [d3.id])
        self.assertEqual(results[0]["original_file_name"], "someepdf.pdf")

        response = self.client.get("/api/documents/?query=statement")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(results), 2)
        self.assertCountEqual(response.data["all"], [d2.id, d3.id])

        response = self.client.get("/api/documents/?query=sfegdfg")
        results = response.data["results"]
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(results), 0)
        self.assertCountEqual(response.data["all"], [])

    def test_search_multi_page(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(55):
                doc = Document.objects.create(
                    checksum=str(i),
                    pk=i + 1,
                    title=f"Document {i+1}",
                    content="content",
                )
                index.update_document(writer, doc)

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

    def test_search_invalid_page(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(15):
                doc = Document.objects.create(
                    checksum=str(i),
                    pk=i + 1,
                    title=f"Document {i+1}",
                    content="content",
                )
                index.update_document(writer, doc)

        response = self.client.get("/api/documents/?query=content&page=0&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get("/api/documents/?query=content&page=3&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(
        TIME_ZONE="UTC",
    )
    def test_search_added_in_last_week(self):
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
        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]
        # Expect 3 documents returned
        self.assertEqual(len(results), 3)

        for idx, subset in enumerate(
            [
                {"id": 1, "title": "invoice"},
                {"id": 2, "title": "bank statement 1"},
                {"id": 3, "title": "bank statement 3"},
            ],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    @override_settings(
        TIME_ZONE="America/Chicago",
    )
    def test_search_added_in_last_week_with_timezone_behind(self):
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
        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        for idx, subset in enumerate(
            [{"id": 1, "title": "invoice"}, {"id": 2, "title": "bank statement 1"}],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    @override_settings(
        TIME_ZONE="Europe/Sofia",
    )
    def test_search_added_in_last_week_with_timezone_ahead(self):
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
        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:[-1 week to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        for idx, subset in enumerate(
            [{"id": 1, "title": "invoice"}, {"id": 2, "title": "bank statement 1"}],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    def test_search_added_in_last_month(self):
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

        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:[-1 month to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        for idx, subset in enumerate(
            [{"id": 1, "title": "invoice"}, {"id": 3, "title": "bank statement 3"}],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    @override_settings(
        TIME_ZONE="America/Denver",
    )
    def test_search_added_in_last_month_timezone_behind(self):
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

        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:[-1 month to now]")
        results = response.data["results"]

        # Expect 2 documents returned
        self.assertEqual(len(results), 2)

        for idx, subset in enumerate(
            [{"id": 1, "title": "invoice"}, {"id": 3, "title": "bank statement 3"}],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    @override_settings(
        TIME_ZONE="Europe/Sofia",
    )
    def test_search_added_specific_date_with_timezone_ahead(self):
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

        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/documents/?query=added:20231201")
        results = response.data["results"]

        # Expect 1 document returned
        self.assertEqual(len(results), 1)

        for idx, subset in enumerate(
            [{"id": 3, "title": "bank statement 3"}],
        ):
            result = results[idx]
            # Assert subset in results
            self.assertDictEqual(result, {**result, **subset})

    def test_search_added_invalid_date(self):
        """
        GIVEN:
            - One document added right now
        WHEN:
            - Query with invalid added date
        THEN:
            - No documents returned
        """
        d1 = Document.objects.create(
            title="invoice",
            content="the thing i bought at a shop and paid with bank account",
            checksum="A",
            pk=1,
        )

        with index.open_index_writer() as writer:
            index.update_document(writer, d1)

        response = self.client.get("/api/documents/?query=added:invalid-date")
        results = response.data["results"]

        # Expect 0 document returned
        self.assertEqual(len(results), 0)

    @mock.patch("documents.index.autocomplete")
    def test_search_autocomplete_limits(self, m):
        """
        GIVEN:
            - No pre-conditions
        WHEN:
            - API request for autocomplete is made by user with various limit requests
        THEN:
            - Limit requests are validated
            - Limit requests are obeyed
        """

        m.side_effect = lambda ix, term, limit, user: [term for _ in range(limit)]

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

    def test_search_autocomplete_respect_permissions(self):
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

        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [b"apples", b"applebaum", b"appletini"])

        d3.owner = u2

        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [b"apples", b"applebaum"])

        assign_perm("view_document", u1, d3)

        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d3)

        response = self.client.get("/api/search/autocomplete/?term=app")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [b"apples", b"applebaum", b"appletini"])

    def test_search_autocomplete_field_name_match(self):
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

        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)

        response = self.client.get("/api/search/autocomplete/?term=created:2023")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_search_autocomplete_search_term(self):
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

        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)

        response = self.client.get("/api/search/autocomplete/?term=auto")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0], b"auto")

    @pytest.mark.skip(reason="Not implemented yet")
    def test_search_spelling_correction(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(55):
                doc = Document.objects.create(
                    checksum=str(i),
                    pk=i + 1,
                    title=f"Document {i+1}",
                    content=f"Things document {i+1}",
                )
                index.update_document(writer, doc)

        response = self.client.get("/api/search/?query=thing")
        correction = response.data["corrected_query"]

        self.assertEqual(correction, "things")

        response = self.client.get("/api/search/?query=things")
        correction = response.data["corrected_query"]

        self.assertEqual(correction, None)

    def test_search_more_like(self):
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
            title="Monty Python & the Holy Grail",
            content="And now for something completely different",
            pk=4,
            checksum="ABC",
        )
        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)
            index.update_document(writer, d4)

        response = self.client.get(f"/api/documents/?more_like_id={d2.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], d3.id)
        self.assertEqual(results[1]["id"], d1.id)

    def test_search_filtering(self):
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
            created=timezone.make_aware(datetime.datetime(2020, 7, 13)),
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

        with AsyncWriter(index.open_index()) as writer:
            for doc in Document.objects.all():
                index.update_document(writer, doc)

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

    def test_search_filtering_respect_owner(self):
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

        with AsyncWriter(index.open_index()) as writer:
            for doc in Document.objects.all():
                index.update_document(writer, doc)

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

    def test_search_filtering_with_object_perms(self):
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

        with AsyncWriter(index.open_index()) as writer:
            for doc in Document.objects.all():
                index.update_document(writer, doc)

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

        with AsyncWriter(index.open_index()) as writer:
            for doc in [d1, d2, d3]:
                index.update_document(writer, doc)

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

    def test_search_sorting(self):
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

        with AsyncWriter(index.open_index()) as writer:
            for doc in Document.objects.all():
                index.update_document(writer, doc)

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
        self.assertListEqual(
            search_query("&ordering=owner"),
            [d1.id, d2.id, d3.id],
        )
        self.assertListEqual(
            search_query("&ordering=-owner"),
            [d3.id, d2.id, d1.id],
        )

    @mock.patch("documents.bulk_edit.bulk_update_documents")
    def test_global_search(self, m):
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
        set_permissions([4, 5], set_permissions=[], owner=user2, merge=False)

        with index.open_index_writer() as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)
            index.update_document(writer, d4)
            index.update_document(writer, d5)

        correspondent1 = Correspondent.objects.create(name="bank correspondent 1")
        Correspondent.objects.create(name="correspondent 2")
        document_type1 = DocumentType.objects.create(name="bank invoice")
        DocumentType.objects.create(name="invoice")
        storage_path1 = StoragePath.objects.create(name="bank path 1", path="path1")
        StoragePath.objects.create(name="path 2", path="path2")
        tag1 = Tag.objects.create(name="bank tag1")
        Tag.objects.create(name="tag2")

        SavedView.objects.create(
            name="bank view",
            show_on_dashboard=True,
            show_in_sidebar=True,
            sort_field="",
            owner=user1,
        )
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

    def test_global_search_bad_request(self):
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
