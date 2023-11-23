import datetime
import io
import json
import os
import shutil
import tempfile
import urllib.request
import uuid
import zipfile
import zoneinfo
from datetime import timedelta
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import celery
import pytest
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_perms
from guardian.shortcuts import get_users_with_perms
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from whoosh.writing import AsyncWriter

from documents import bulk_edit
from documents import index
from documents.data_models import DocumentSource
from documents.models import ConsumptionTemplate
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import Note
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DocumentConsumeDelayMixin
from paperless import version
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestDocumentApi(DirectoriesMixin, DocumentConsumeDelayMixin, APITestCase):
    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def testDocuments(self):
        response = self.client.get("/api/documents/").data

        self.assertEqual(response["count"], 0)

        c = Correspondent.objects.create(name="c", pk=41)
        dt = DocumentType.objects.create(name="dt", pk=63)
        tag = Tag.objects.create(name="t", pk=85)

        doc = Document.objects.create(
            title="WOW",
            content="the content",
            correspondent=c,
            document_type=dt,
            checksum="123",
            mime_type="application/pdf",
        )

        doc.tags.add(tag)

        response = self.client.get("/api/documents/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        returned_doc = response.data["results"][0]
        self.assertEqual(returned_doc["id"], doc.id)
        self.assertEqual(returned_doc["title"], doc.title)
        self.assertEqual(returned_doc["correspondent"], c.id)
        self.assertEqual(returned_doc["document_type"], dt.id)
        self.assertListEqual(returned_doc["tags"], [tag.id])

        c2 = Correspondent.objects.create(name="c2")

        returned_doc["correspondent"] = c2.pk
        returned_doc["title"] = "the new title"

        response = self.client.put(
            f"/api/documents/{doc.pk}/",
            returned_doc,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        doc_after_save = Document.objects.get(id=doc.id)

        self.assertEqual(doc_after_save.correspondent, c2)
        self.assertEqual(doc_after_save.title, "the new title")

        self.client.delete(f"/api/documents/{doc_after_save.pk}/")

        self.assertEqual(len(Document.objects.all()), 0)

    def test_document_fields(self):
        c = Correspondent.objects.create(name="c", pk=41)
        dt = DocumentType.objects.create(name="dt", pk=63)
        Tag.objects.create(name="t", pk=85)
        storage_path = StoragePath.objects.create(name="sp", pk=77, path="p")
        Document.objects.create(
            title="WOW",
            content="the content",
            correspondent=c,
            document_type=dt,
            checksum="123",
            mime_type="application/pdf",
            storage_path=storage_path,
        )

        response = self.client.get("/api/documents/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results_full = response.data["results"]
        self.assertIn("content", results_full[0])
        self.assertIn("id", results_full[0])

        response = self.client.get("/api/documents/?fields=id", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertFalse("content" in results[0])
        self.assertIn("id", results[0])
        self.assertEqual(len(results[0]), 1)

        response = self.client.get("/api/documents/?fields=content", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertIn("content", results[0])
        self.assertFalse("id" in results[0])
        self.assertEqual(len(results[0]), 1)

        response = self.client.get("/api/documents/?fields=id,content", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertIn("content", results[0])
        self.assertIn("id", results[0])
        self.assertEqual(len(results[0]), 2)

        response = self.client.get(
            "/api/documents/?fields=id,conteasdnt",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertFalse("content" in results[0])
        self.assertIn("id", results[0])
        self.assertEqual(len(results[0]), 1)

        response = self.client.get("/api/documents/?fields=", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results_full[0]), len(results[0]))

        response = self.client.get("/api/documents/?fields=dgfhs", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results[0]), 0)

    def test_document_actions(self):
        _, filename = tempfile.mkstemp(dir=self.dirs.originals_dir)

        content = b"This is a test"
        content_thumbnail = b"thumbnail content"

        with open(filename, "wb") as f:
            f.write(content)

        doc = Document.objects.create(
            title="none",
            filename=os.path.basename(filename),
            mime_type="application/pdf",
        )

        with open(
            os.path.join(self.dirs.thumbnail_dir, f"{doc.pk:07d}.webp"),
            "wb",
        ) as f:
            f.write(content_thumbnail)

        response = self.client.get(f"/api/documents/{doc.pk}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content)

        response = self.client.get(f"/api/documents/{doc.pk}/preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content)

        response = self.client.get(f"/api/documents/{doc.pk}/thumb/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content_thumbnail)

    def test_document_actions_with_perms(self):
        """
        GIVEN:
            - Document with owner and without granted permissions
            - User is then granted permissions
        WHEN:
            - User tries to load preview, thumbnail
        THEN:
            - Initially, HTTP 403 Forbidden
            - With permissions, HTTP 200 OK
        """
        _, filename = tempfile.mkstemp(dir=self.dirs.originals_dir)

        content = b"This is a test"
        content_thumbnail = b"thumbnail content"

        with open(filename, "wb") as f:
            f.write(content)

        user1 = User.objects.create_user(username="test1")
        user2 = User.objects.create_user(username="test2")
        user1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        user2.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        self.client.force_authenticate(user2)

        doc = Document.objects.create(
            title="none",
            filename=os.path.basename(filename),
            mime_type="application/pdf",
            owner=user1,
        )

        with open(
            os.path.join(self.dirs.thumbnail_dir, f"{doc.pk:07d}.webp"),
            "wb",
        ) as f:
            f.write(content_thumbnail)

        response = self.client.get(f"/api/documents/{doc.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(f"/api/documents/{doc.pk}/preview/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(f"/api/documents/{doc.pk}/thumb/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        assign_perm("view_document", user2, doc)

        response = self.client.get(f"/api/documents/{doc.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f"/api/documents/{doc.pk}/preview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f"/api/documents/{doc.pk}/thumb/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(FILENAME_FORMAT="")
    def test_download_with_archive(self):
        content = b"This is a test"
        content_archive = b"This is the same test but archived"

        doc = Document.objects.create(
            title="none",
            filename="my_document.pdf",
            archive_filename="archived.pdf",
            mime_type="application/pdf",
        )

        with open(doc.source_path, "wb") as f:
            f.write(content)

        with open(doc.archive_path, "wb") as f:
            f.write(content_archive)

        response = self.client.get(f"/api/documents/{doc.pk}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content_archive)

        response = self.client.get(
            f"/api/documents/{doc.pk}/download/?original=true",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content)

        response = self.client.get(f"/api/documents/{doc.pk}/preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content_archive)

        response = self.client.get(
            f"/api/documents/{doc.pk}/preview/?original=true",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content)

    def test_document_actions_not_existing_file(self):
        doc = Document.objects.create(
            title="none",
            filename=os.path.basename("asd"),
            mime_type="application/pdf",
        )

        response = self.client.get(f"/api/documents/{doc.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(f"/api/documents/{doc.pk}/preview/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(f"/api/documents/{doc.pk}/thumb/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_filters(self):
        doc1 = Document.objects.create(
            title="none1",
            checksum="A",
            mime_type="application/pdf",
        )
        doc2 = Document.objects.create(
            title="none2",
            checksum="B",
            mime_type="application/pdf",
        )
        doc3 = Document.objects.create(
            title="none3",
            checksum="C",
            mime_type="application/pdf",
        )

        tag_inbox = Tag.objects.create(name="t1", is_inbox_tag=True)
        tag_2 = Tag.objects.create(name="t2")
        tag_3 = Tag.objects.create(name="t3")

        cf1 = CustomField.objects.create(
            name="stringfield",
            data_type=CustomField.FieldDataType.STRING,
        )
        cf2 = CustomField.objects.create(
            name="numberfield",
            data_type=CustomField.FieldDataType.INT,
        )

        doc1.tags.add(tag_inbox)
        doc2.tags.add(tag_2)
        doc3.tags.add(tag_2)
        doc3.tags.add(tag_3)

        cf1_d1 = CustomFieldInstance.objects.create(
            document=doc1,
            field=cf1,
            value_text="foobard1",
        )
        CustomFieldInstance.objects.create(
            document=doc1,
            field=cf2,
            value_int=999,
        )
        cf1_d3 = CustomFieldInstance.objects.create(
            document=doc3,
            field=cf1,
            value_text="foobard3",
        )

        response = self.client.get("/api/documents/?is_in_inbox=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc1.id)

        response = self.client.get("/api/documents/?is_in_inbox=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]["id"], results[1]["id"]], [doc2.id, doc3.id])

        response = self.client.get(
            f"/api/documents/?tags__id__in={tag_inbox.id},{tag_3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]["id"], results[1]["id"]], [doc1.id, doc3.id])

        response = self.client.get(
            f"/api/documents/?tags__id__in={tag_2.id},{tag_3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]["id"], results[1]["id"]], [doc2.id, doc3.id])

        response = self.client.get(
            f"/api/documents/?tags__id__all={tag_2.id},{tag_3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc3.id)

        response = self.client.get(
            f"/api/documents/?tags__id__all={tag_inbox.id},{tag_3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

        response = self.client.get(
            f"/api/documents/?tags__id__all={tag_inbox.id}a{tag_3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)

        response = self.client.get(f"/api/documents/?tags__id__none={tag_3.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]["id"], results[1]["id"]], [doc1.id, doc2.id])

        response = self.client.get(
            f"/api/documents/?tags__id__none={tag_3.id},{tag_2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc1.id)

        response = self.client.get(
            f"/api/documents/?tags__id__none={tag_2.id},{tag_inbox.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

        response = self.client.get(
            f"/api/documents/?id__in={doc1.id},{doc2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        response = self.client.get(
            f"/api/documents/?id__range={doc1.id},{doc3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)

        response = self.client.get(
            f"/api/documents/?id={doc2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        # custom field name
        response = self.client.get(
            f"/api/documents/?custom_fields__icontains={cf1.name}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        # custom field value
        response = self.client.get(
            f"/api/documents/?custom_fields__icontains={cf1_d1.value}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc1.id)

        response = self.client.get(
            f"/api/documents/?custom_fields__icontains={cf1_d3.value}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc3.id)

    def test_document_checksum_filter(self):
        Document.objects.create(
            title="none1",
            checksum="A",
            mime_type="application/pdf",
        )
        doc2 = Document.objects.create(
            title="none2",
            checksum="B",
            mime_type="application/pdf",
        )
        Document.objects.create(
            title="none3",
            checksum="C",
            mime_type="application/pdf",
        )

        response = self.client.get("/api/documents/?checksum__iexact=B")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc2.id)

        response = self.client.get("/api/documents/?checksum__iexact=X")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

    def test_document_original_filename_filter(self):
        doc1 = Document.objects.create(
            title="none1",
            checksum="A",
            mime_type="application/pdf",
            original_filename="docA.pdf",
        )
        doc2 = Document.objects.create(
            title="none2",
            checksum="B",
            mime_type="application/pdf",
            original_filename="docB.pdf",
        )
        doc3 = Document.objects.create(
            title="none3",
            checksum="C",
            mime_type="application/pdf",
            original_filename="docC.pdf",
        )

        response = self.client.get("/api/documents/?original_filename__iexact=DOCa.pdf")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], doc1.id)

        response = self.client.get("/api/documents/?original_filename__iexact=docx.pdf")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

        response = self.client.get("/api/documents/?original_filename__istartswith=dOc")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertCountEqual(
            [results[0]["id"], results[1]["id"], results[2]["id"]],
            [doc1.id, doc2.id, doc3.id],
        )

    def test_documents_title_content_filter(self):
        doc1 = Document.objects.create(
            title="title A",
            content="content A",
            checksum="A",
            mime_type="application/pdf",
        )
        doc2 = Document.objects.create(
            title="title B",
            content="content A",
            checksum="B",
            mime_type="application/pdf",
        )
        doc3 = Document.objects.create(
            title="title A",
            content="content B",
            checksum="C",
            mime_type="application/pdf",
        )
        doc4 = Document.objects.create(
            title="title B",
            content="content B",
            checksum="D",
            mime_type="application/pdf",
        )

        response = self.client.get("/api/documents/?title_content=A")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertCountEqual(
            [results[0]["id"], results[1]["id"], results[2]["id"]],
            [doc1.id, doc2.id, doc3.id],
        )

        response = self.client.get("/api/documents/?title_content=B")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertCountEqual(
            [results[0]["id"], results[1]["id"], results[2]["id"]],
            [doc2.id, doc3.id, doc4.id],
        )

        response = self.client.get("/api/documents/?title_content=X")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

    def test_document_owner_filters(self):
        """
        GIVEN:
            - Documents with owners, with and without granted permissions
        WHEN:
            - User filters by owner
        THEN:
            - Owner filters work correctly but still respect permissions
        """
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")
        u1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        u2.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        u1_doc1 = Document.objects.create(
            title="none1",
            checksum="A",
            mime_type="application/pdf",
            owner=u1,
        )
        Document.objects.create(
            title="none2",
            checksum="B",
            mime_type="application/pdf",
            owner=u2,
        )
        u0_doc1 = Document.objects.create(
            title="none3",
            checksum="C",
            mime_type="application/pdf",
        )
        u1_doc2 = Document.objects.create(
            title="none4",
            checksum="D",
            mime_type="application/pdf",
            owner=u1,
        )
        u2_doc2 = Document.objects.create(
            title="none5",
            checksum="E",
            mime_type="application/pdf",
            owner=u2,
        )

        self.client.force_authenticate(user=u1)
        assign_perm("view_document", u1, u2_doc2)

        # Will not show any u1 docs or u2_doc1 which isn't shared
        response = self.client.get(f"/api/documents/?owner__id__none={u1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual(
            [results[0]["id"], results[1]["id"]],
            [u0_doc1.id, u2_doc2.id],
        )

        # Will not show any u1 docs, u0_doc1 which has no owner or u2_doc1 which isn't shared
        response = self.client.get(
            f"/api/documents/?owner__id__none={u1.id}&owner__isnull=false",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertCountEqual([results[0]["id"]], [u2_doc2.id])

        # Will not show any u1 docs, u2_doc2 which is shared but has owner
        response = self.client.get(
            f"/api/documents/?owner__id__none={u1.id}&owner__isnull=true",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertCountEqual([results[0]["id"]], [u0_doc1.id])

        # Will not show any u1 docs or u2_doc1 which is not shared
        response = self.client.get(f"/api/documents/?owner__id={u2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertCountEqual([results[0]["id"]], [u2_doc2.id])

        # Will not show u2_doc1 which is not shared
        response = self.client.get(f"/api/documents/?owner__id__in={u1.id},{u2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertCountEqual(
            [results[0]["id"], results[1]["id"], results[2]["id"]],
            [u1_doc1.id, u1_doc2.id, u2_doc2.id],
        )

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
            # That's why we cant open the writer in a model on_save handler or something.
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

    @mock.patch("documents.index.autocomplete")
    def test_search_autocomplete(self, m):
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
            - API reuqest for autocomplete is made by user with or without permissions
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
        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

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

    def test_search_filtering_respect_owner(self):
        """
        GIVEN:
            - Documents with owners set & without
        WHEN:
            - API reuqest for advanced query (search) is made by non-superuser
            - API reuqest for advanced query (search) is made by superuser
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
            - API reuqest for advanced query (search) is made by user
        THEN:
            - Only docs with granted view permissions are returned
        """
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")
        u1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        u2.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        Document.objects.create(checksum="1", content="test 1", owner=u1)
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

        with AsyncWriter(index.open_index()) as writer:
            for doc in [d2, d3]:
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

    def test_pagination_all(self):
        """
        GIVEN:
            - A set of 50 documents
        WHEN:
            - API reuqest for document filtering
        THEN:
            - Results are paginated (25 items) and response["all"] returns all ids (50 items)
        """
        t = Tag.objects.create(name="tag")
        docs = []
        for i in range(50):
            d = Document.objects.create(checksum=i, content=f"test{i}")
            d.tags.add(t)
            docs.append(d)

        response = self.client.get(
            f"/api/documents/?tags__id__in={t.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 25)
        self.assertEqual(len(response.data["all"]), 50)
        self.assertCountEqual(response.data["all"], [d.id for d in docs])

    def test_statistics(self):
        doc1 = Document.objects.create(
            title="none1",
            checksum="A",
            mime_type="application/pdf",
            content="abc",
        )
        Document.objects.create(
            title="none2",
            checksum="B",
            mime_type="application/pdf",
            content="123",
        )
        Document.objects.create(
            title="none3",
            checksum="C",
            mime_type="text/plain",
            content="hello",
        )

        tag_inbox = Tag.objects.create(name="t1", is_inbox_tag=True)
        Tag.objects.create(name="t2")
        Tag.objects.create(name="t3")
        Correspondent.objects.create(name="c1")
        Correspondent.objects.create(name="c2")
        DocumentType.objects.create(name="dt1")
        StoragePath.objects.create(name="sp1")
        StoragePath.objects.create(name="sp2")

        doc1.tags.add(tag_inbox)

        response = self.client.get("/api/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["documents_total"], 3)
        self.assertEqual(response.data["documents_inbox"], 1)
        self.assertEqual(response.data["inbox_tag"], tag_inbox.pk)
        self.assertEqual(
            response.data["document_file_type_counts"][0]["mime_type_count"],
            2,
        )
        self.assertEqual(
            response.data["document_file_type_counts"][1]["mime_type_count"],
            1,
        )
        self.assertEqual(response.data["character_count"], 11)
        self.assertEqual(response.data["tag_count"], 3)
        self.assertEqual(response.data["correspondent_count"], 2)
        self.assertEqual(response.data["document_type_count"], 1)
        self.assertEqual(response.data["storage_path_count"], 2)

    def test_statistics_no_inbox_tag(self):
        Document.objects.create(title="none1", checksum="A")

        response = self.client.get("/api/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["documents_inbox"], None)
        self.assertEqual(response.data["inbox_tag"], None)

    def test_upload(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        input_doc, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(input_doc.original_file.name, "simple.pdf")
        self.assertIn(Path(settings.SCRATCH_DIR), input_doc.original_file.parents)
        self.assertIsNone(overrides.title)
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.tag_ids)

    def test_upload_empty_metadata(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "title": "", "correspondent": "", "document_type": ""},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        input_doc, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(input_doc.original_file.name, "simple.pdf")
        self.assertIn(Path(settings.SCRATCH_DIR), input_doc.original_file.parents)
        self.assertIsNone(overrides.title)
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.tag_ids)

    def test_upload_invalid_form(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"documenst": f},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.consume_file_mock.assert_not_called()

    def test_upload_invalid_file(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.zip"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.consume_file_mock.assert_not_called()

    def test_upload_with_title(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "title": "my custom title"},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        _, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(overrides.title, "my custom title")
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.tag_ids)

    def test_upload_with_correspondent(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        c = Correspondent.objects.create(name="test-corres")
        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "correspondent": c.id},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        _, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(overrides.correspondent_id, c.id)
        self.assertIsNone(overrides.title)
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.tag_ids)

    def test_upload_with_invalid_correspondent(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "correspondent": 3456},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.consume_file_mock.assert_not_called()

    def test_upload_with_document_type(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        dt = DocumentType.objects.create(name="invoice")
        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "document_type": dt.id},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        _, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(overrides.document_type_id, dt.id)
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.title)
        self.assertIsNone(overrides.tag_ids)

    def test_upload_with_invalid_document_type(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "document_type": 34578},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.consume_file_mock.assert_not_called()

    def test_upload_with_tags(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        t1 = Tag.objects.create(name="tag1")
        t2 = Tag.objects.create(name="tag2")
        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "tags": [t2.id, t1.id]},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        _, overrides = self.get_last_consume_delay_call_args()

        self.assertCountEqual(overrides.tag_ids, [t1.id, t2.id])
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.title)

    def test_upload_with_invalid_tags(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        t1 = Tag.objects.create(name="tag1")
        t2 = Tag.objects.create(name="tag2")
        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "tags": [t2.id, t1.id, 734563]},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.consume_file_mock.assert_not_called()

    def test_upload_with_created(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        created = datetime.datetime(
            2022,
            5,
            12,
            0,
            0,
            0,
            0,
            tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles"),
        )
        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "created": created},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        _, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(overrides.created, created)

    def test_upload_with_asn(self):
        self.consume_file_mock.return_value = celery.result.AsyncResult(
            id=str(uuid.uuid4()),
        )

        with open(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            "rb",
        ) as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "archive_serial_number": 500},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.consume_file_mock.assert_called_once()

        input_doc, overrides = self.get_last_consume_delay_call_args()

        self.assertEqual(input_doc.original_file.name, "simple.pdf")
        self.assertEqual(overrides.filename, "simple.pdf")
        self.assertIsNone(overrides.correspondent_id)
        self.assertIsNone(overrides.document_type_id)
        self.assertIsNone(overrides.tag_ids)
        self.assertEqual(500, overrides.asn)

    def test_get_metadata(self):
        doc = Document.objects.create(
            title="test",
            filename="file.pdf",
            mime_type="image/png",
            archive_checksum="A",
            archive_filename="archive.pdf",
        )

        source_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "documents",
            "thumbnails",
            "0000001.webp",
        )
        archive_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")

        shutil.copy(source_file, doc.source_path)
        shutil.copy(archive_file, doc.archive_path)

        response = self.client.get(f"/api/documents/{doc.pk}/metadata/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        meta = response.data

        self.assertEqual(meta["original_mime_type"], "image/png")
        self.assertTrue(meta["has_archive_version"])
        self.assertEqual(len(meta["original_metadata"]), 0)
        self.assertGreater(len(meta["archive_metadata"]), 0)
        self.assertEqual(meta["media_filename"], "file.pdf")
        self.assertEqual(meta["archive_media_filename"], "archive.pdf")
        self.assertEqual(meta["original_size"], os.stat(source_file).st_size)
        self.assertEqual(meta["archive_size"], os.stat(archive_file).st_size)

    def test_get_metadata_invalid_doc(self):
        response = self.client.get("/api/documents/34576/metadata/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_metadata_no_archive(self):
        doc = Document.objects.create(
            title="test",
            filename="file.pdf",
            mime_type="application/pdf",
        )

        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            doc.source_path,
        )

        response = self.client.get(f"/api/documents/{doc.pk}/metadata/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        meta = response.data

        self.assertEqual(meta["original_mime_type"], "application/pdf")
        self.assertFalse(meta["has_archive_version"])
        self.assertGreater(len(meta["original_metadata"]), 0)
        self.assertIsNone(meta["archive_metadata"])
        self.assertIsNone(meta["archive_media_filename"])

    def test_get_metadata_missing_files(self):
        doc = Document.objects.create(
            title="test",
            filename="file.pdf",
            mime_type="application/pdf",
            archive_filename="file.pdf",
            archive_checksum="B",
            checksum="A",
        )

        response = self.client.get(f"/api/documents/{doc.pk}/metadata/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        meta = response.data

        self.assertTrue(meta["has_archive_version"])
        self.assertIsNone(meta["original_metadata"])
        self.assertIsNone(meta["original_size"])
        self.assertIsNone(meta["archive_metadata"])
        self.assertIsNone(meta["archive_size"])

    def test_get_empty_suggestions(self):
        doc = Document.objects.create(title="test", mime_type="application/pdf")

        response = self.client.get(f"/api/documents/{doc.pk}/suggestions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "correspondents": [],
                "tags": [],
                "document_types": [],
                "storage_paths": [],
                "dates": [],
            },
        )

    def test_get_suggestions_invalid_doc(self):
        response = self.client.get("/api/documents/34676/suggestions/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch("documents.views.match_storage_paths")
    @mock.patch("documents.views.match_document_types")
    @mock.patch("documents.views.match_tags")
    @mock.patch("documents.views.match_correspondents")
    @override_settings(NUMBER_OF_SUGGESTED_DATES=10)
    def test_get_suggestions(
        self,
        match_correspondents,
        match_tags,
        match_document_types,
        match_storage_paths,
    ):
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is an invoice from 12.04.2022!",
        )

        match_correspondents.return_value = [Correspondent(id=88), Correspondent(id=2)]
        match_tags.return_value = [Tag(id=56), Tag(id=123)]
        match_document_types.return_value = [DocumentType(id=23)]
        match_storage_paths.return_value = [StoragePath(id=99), StoragePath(id=77)]

        response = self.client.get(f"/api/documents/{doc.pk}/suggestions/")
        self.assertEqual(
            response.data,
            {
                "correspondents": [88, 2],
                "tags": [56, 123],
                "document_types": [23],
                "storage_paths": [99, 77],
                "dates": ["2022-04-12"],
            },
        )

    @mock.patch("documents.parsers.parse_date_generator")
    @override_settings(NUMBER_OF_SUGGESTED_DATES=0)
    def test_get_suggestions_dates_disabled(
        self,
        parse_date_generator,
    ):
        """
        GIVEN:
            - NUMBER_OF_SUGGESTED_DATES = 0 (disables feature)
        WHEN:
            - API reuqest for document suggestions
        THEN:
            - Dont check for suggested dates at all
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is an invoice from 12.04.2022!",
        )

        self.client.get(f"/api/documents/{doc.pk}/suggestions/")
        self.assertFalse(parse_date_generator.called)

    def test_saved_views(self):
        u1 = User.objects.create_superuser("user1")
        u2 = User.objects.create_superuser("user2")

        v1 = SavedView.objects.create(
            owner=u1,
            name="test1",
            sort_field="",
            show_on_dashboard=False,
            show_in_sidebar=False,
        )
        SavedView.objects.create(
            owner=u2,
            name="test2",
            sort_field="",
            show_on_dashboard=False,
            show_in_sidebar=False,
        )
        SavedView.objects.create(
            owner=u2,
            name="test3",
            sort_field="",
            show_on_dashboard=False,
            show_in_sidebar=False,
        )

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        self.assertEqual(
            self.client.get(f"/api/saved_views/{v1.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.client.force_authenticate(user=u1)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            self.client.get(f"/api/saved_views/{v1.id}/").status_code,
            status.HTTP_200_OK,
        )

        self.client.force_authenticate(user=u2)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        self.assertEqual(
            self.client.get(f"/api/saved_views/{v1.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_create_update_patch(self):
        User.objects.create_user("user1")

        view = {
            "name": "test",
            "show_on_dashboard": True,
            "show_in_sidebar": True,
            "sort_field": "created2",
            "filter_rules": [{"rule_type": 4, "value": "test"}],
        }

        response = self.client.post("/api/saved_views/", view, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        v1 = SavedView.objects.get(name="test")
        self.assertEqual(v1.sort_field, "created2")
        self.assertEqual(v1.filter_rules.count(), 1)
        self.assertEqual(v1.owner, self.user)

        response = self.client.patch(
            f"/api/saved_views/{v1.id}/",
            {"show_in_sidebar": False},
            format="json",
        )

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(v1.show_in_sidebar)
        self.assertEqual(v1.filter_rules.count(), 1)

        view["filter_rules"] = [{"rule_type": 12, "value": "secret"}]

        response = self.client.put(f"/api/saved_views/{v1.id}/", view, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(v1.filter_rules.count(), 1)
        self.assertEqual(v1.filter_rules.first().value, "secret")

        view["filter_rules"] = []

        response = self.client.put(f"/api/saved_views/{v1.id}/", view, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(v1.filter_rules.count(), 0)

    def test_get_logs(self):
        log_data = "test\ntest2\n"
        with open(os.path.join(settings.LOGGING_DIR, "mail.log"), "w") as f:
            f.write(log_data)
        with open(os.path.join(settings.LOGGING_DIR, "paperless.log"), "w") as f:
            f.write(log_data)
        response = self.client.get("/api/logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(response.data, ["mail", "paperless"])

    def test_get_logs_only_when_exist(self):
        log_data = "test\ntest2\n"
        with open(os.path.join(settings.LOGGING_DIR, "paperless.log"), "w") as f:
            f.write(log_data)
        response = self.client.get("/api/logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(response.data, ["paperless"])

    def test_get_invalid_log(self):
        response = self.client.get("/api/logs/bogus_log/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(LOGGING_DIR="bogus_dir")
    def test_get_nonexistent_log(self):
        response = self.client.get("/api/logs/paperless/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_log(self):
        log_data = "test\ntest2\n"
        with open(os.path.join(settings.LOGGING_DIR, "paperless.log"), "w") as f:
            f.write(log_data)
        response = self.client.get("/api/logs/paperless/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertListEqual(response.data, ["test", "test2"])

    def test_invalid_regex_other_algorithm(self):
        for endpoint in ["correspondents", "tags", "document_types"]:
            response = self.client.post(
                f"/api/{endpoint}/",
                {
                    "name": "test",
                    "matching_algorithm": MatchingModel.MATCH_ANY,
                    "match": "[",
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, endpoint)

    def test_invalid_regex(self):
        for endpoint in ["correspondents", "tags", "document_types"]:
            response = self.client.post(
                f"/api/{endpoint}/",
                {
                    "name": "test",
                    "matching_algorithm": MatchingModel.MATCH_REGEX,
                    "match": "[",
                },
                format="json",
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                endpoint,
            )

    def test_valid_regex(self):
        for endpoint in ["correspondents", "tags", "document_types"]:
            response = self.client.post(
                f"/api/{endpoint}/",
                {
                    "name": "test",
                    "matching_algorithm": MatchingModel.MATCH_REGEX,
                    "match": "[0-9]",
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, endpoint)

    def test_regex_no_algorithm(self):
        for endpoint in ["correspondents", "tags", "document_types"]:
            response = self.client.post(
                f"/api/{endpoint}/",
                {"name": "test", "match": "[0-9]"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, endpoint)

    def test_tag_color_default(self):
        response = self.client.post("/api/tags/", {"name": "tag"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.get(id=response.data["id"]).color, "#a6cee3")
        self.assertEqual(
            self.client.get(f"/api/tags/{response.data['id']}/", format="json").data[
                "colour"
            ],
            1,
        )

    def test_tag_color(self):
        response = self.client.post(
            "/api/tags/",
            {"name": "tag", "colour": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.get(id=response.data["id"]).color, "#b2df8a")
        self.assertEqual(
            self.client.get(f"/api/tags/{response.data['id']}/", format="json").data[
                "colour"
            ],
            3,
        )

    def test_tag_color_invalid(self):
        response = self.client.post(
            "/api/tags/",
            {"name": "tag", "colour": 34},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tag_color_custom(self):
        tag = Tag.objects.create(name="test", color="#abcdef")
        self.assertEqual(
            self.client.get(f"/api/tags/{tag.id}/", format="json").data["colour"],
            1,
        )

    def test_get_existing_notes(self):
        """
        GIVEN:
            - A document with a single note
        WHEN:
            - API reuqest for document notes is made
        THEN:
            - The associated note is returned
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have notes!",
        )
        note = Note.objects.create(
            note="This is a note.",
            document=doc,
            user=self.user,
        )

        response = self.client.get(
            f"/api/documents/{doc.pk}/notes/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertEqual(len(resp_data), 1)

        resp_data = resp_data[0]
        del resp_data["created"]

        self.assertDictEqual(
            resp_data,
            {
                "id": note.id,
                "note": note.note,
                "user": {
                    "id": note.user.id,
                    "username": note.user.username,
                    "first_name": note.user.first_name,
                    "last_name": note.user.last_name,
                },
            },
        )

    def test_create_note(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - API request is made to add a note
        THEN:
            - note is created and associated with document, modified time is updated
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have notes added",
            created=timezone.now() - timedelta(days=1),
        )
        # set to yesterday
        doc.modified = timezone.now() - timedelta(days=1)
        self.assertEqual(doc.modified.day, (timezone.now() - timedelta(days=1)).day)

        resp = self.client.post(
            f"/api/documents/{doc.pk}/notes/",
            data={"note": "this is a posted note"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/documents/{doc.pk}/notes/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertEqual(len(resp_data), 1)

        resp_data = resp_data[0]

        self.assertEqual(resp_data["note"], "this is a posted note")

        doc = Document.objects.get(pk=doc.pk)
        # modified was updated to today
        self.assertEqual(doc.modified.day, timezone.now().day)

    def test_notes_permissions_aware(self):
        """
        GIVEN:
            - Existing document owned by user2 but with granted view perms for user1
        WHEN:
            - API request is made by user1 to add a note or delete
        THEN:
            - Notes are neither created nor deleted
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.save()

        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have notes added",
        )
        doc.owner = user2
        doc.save()

        self.client.force_authenticate(user1)

        resp = self.client.get(
            f"/api/documents/{doc.pk}/notes/",
            format="json",
        )
        self.assertEqual(resp.content, b"Insufficient permissions to view notes")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        assign_perm("view_document", user1, doc)

        resp = self.client.post(
            f"/api/documents/{doc.pk}/notes/",
            data={"note": "this is a posted note"},
        )
        self.assertEqual(resp.content, b"Insufficient permissions to create notes")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        note = Note.objects.create(
            note="This is a note.",
            document=doc,
            user=user2,
        )

        response = self.client.delete(
            f"/api/documents/{doc.pk}/notes/?id={note.pk}",
            format="json",
        )

        self.assertEqual(response.content, b"Insufficient permissions to delete notes")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_note(self):
        """
        GIVEN:
            - Existing document, existing note
        WHEN:
            - API request is made to delete a note
        THEN:
            - note is deleted, document modified is updated
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have notes!",
            created=timezone.now() - timedelta(days=1),
        )
        # set to yesterday
        doc.modified = timezone.now() - timedelta(days=1)
        self.assertEqual(doc.modified.day, (timezone.now() - timedelta(days=1)).day)
        note = Note.objects.create(
            note="This is a note.",
            document=doc,
            user=self.user,
        )

        response = self.client.delete(
            f"/api/documents/{doc.pk}/notes/?id={note.pk}",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(Note.objects.all()), 0)
        doc = Document.objects.get(pk=doc.pk)
        # modified was updated to today
        self.assertEqual(doc.modified.day, timezone.now().day)

    def test_get_notes_no_doc(self):
        """
        GIVEN:
            - A request to get notes from a non-existent document
        WHEN:
            - API request for document notes is made
        THEN:
            - HTTP status.HTTP_404_NOT_FOUND is returned
        """
        response = self.client.get(
            "/api/documents/500/notes/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tag_unique_name_and_owner(self):
        """
        GIVEN:
            - Multiple users
            - Tags owned by particular users
        WHEN:
            - API request for creating items which are unique by name and owner
        THEN:
            - Unique items are created
            - Non-unique items are not allowed
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.filter(codename="add_tag"))
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.user_permissions.add(*Permission.objects.filter(codename="add_tag"))
        user2.save()

        # User 1 creates tag 1 owned by user 1 by default
        # No issue
        self.client.force_authenticate(user1)
        response = self.client.post("/api/tags/", {"name": "tag 1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # User 2 creates tag 1 owned by user 2 by default
        # No issue
        self.client.force_authenticate(user2)
        response = self.client.post("/api/tags/", {"name": "tag 1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # User 2 creates tag 2 owned by user 1
        # No issue
        self.client.force_authenticate(user2)
        response = self.client.post(
            "/api/tags/",
            {"name": "tag 2", "owner": user1.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # User 1 creates tag 2 owned by user 1 by default
        # Not allowed, would create tag2/user1 which already exists
        self.client.force_authenticate(user1)
        response = self.client.post(
            "/api/tags/",
            {"name": "tag 2"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # User 1 creates tag 2 owned by user 1
        # Not allowed, would create tag2/user1 which already exists
        response = self.client.post(
            "/api/tags/",
            {"name": "tag 2", "owner": user1.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tag_unique_name_and_owner_enforced_on_update(self):
        """
        GIVEN:
            - Multiple users
            - Tags owned by particular users
        WHEN:
            - API request for to update tag in such as way as makes it non-unqiue
        THEN:
            - Unique items are created
            - Non-unique items are not allowed on update
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.filter(codename="change_tag"))
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.user_permissions.add(*Permission.objects.filter(codename="change_tag"))
        user2.save()

        # Create name tag 1 owned by user 1
        # Create name tag 1 owned by user 2
        Tag.objects.create(name="tag 1", owner=user1)
        tag2 = Tag.objects.create(name="tag 1", owner=user2)

        # User 2 attempts to change the owner of tag to user 1
        # Not allowed, would change to tag1/user1 which already exists
        self.client.force_authenticate(user2)
        response = self.client.patch(
            f"/api/tags/{tag2.id}/",
            {"owner": user1.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_share_links(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - API request is made to generate a share_link
            - API request is made to view share_links on incorrect doc pk
            - Invalid method request is made to view share_links doc
        THEN:
            - Link is created with a slug and associated with document
            - 404
            - Error
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have notes added",
        )
        # never expires
        resp = self.client.post(
            "/api/share_links/",
            data={
                "document": doc.pk,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        resp = self.client.post(
            "/api/share_links/",
            data={
                "expiration": (timezone.now() + timedelta(days=7)).isoformat(),
                "document": doc.pk,
                "file_version": "original",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/documents/{doc.pk}/share_links/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertEqual(len(resp_data), 2)

        self.assertGreater(len(resp_data[1]["slug"]), 0)
        self.assertIsNone(resp_data[1]["expiration"])
        self.assertEqual(
            (parser.isoparse(resp_data[0]["expiration"]) - timezone.now()).days,
            6,
        )

        sl1 = ShareLink.objects.get(slug=resp_data[1]["slug"])
        self.assertEqual(str(sl1), f"Share Link for {doc.title}")

        response = self.client.post(
            f"/api/documents/{doc.pk}/share_links/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.get(
            "/api/documents/99/share_links/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_links_permissions_aware(self):
        """
        GIVEN:
            - Existing document owned by user2 but with granted view perms for user1
        WHEN:
            - API request is made by user1 to view share links
        THEN:
            - Links only shown if user has permissions
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.save()

        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have share links added",
        )
        doc.owner = user2
        doc.save()

        self.client.force_authenticate(user1)

        resp = self.client.get(
            f"/api/documents/{doc.pk}/share_links/",
            format="json",
        )
        self.assertEqual(resp.content, b"Insufficient permissions to add share link")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        assign_perm("change_document", user1, doc)

        resp = self.client.get(
            f"/api/documents/{doc.pk}/share_links/",
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_next_asn(self):
        """
        GIVEN:
            - Existing documents with ASNs, highest owned by user2
        WHEN:
            - API request is made by user1 to get next ASN
        THEN:
            - ASN +1 from user2's doc is returned for user1
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.save()

        doc1 = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document 1",
            checksum="1",
            archive_serial_number=998,
        )
        doc1.owner = user1
        doc1.save()

        doc2 = Document.objects.create(
            title="test2",
            mime_type="application/pdf",
            content="this is a document 2 with higher ASN",
            checksum="2",
            archive_serial_number=999,
        )
        doc2.owner = user2
        doc2.save()

        self.client.force_authenticate(user1)

        resp = self.client.get(
            "/api/documents/next_asn/",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.content, b"1000")


class TestDocumentApiV2(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")

        self.client.force_authenticate(user=self.user)
        self.client.defaults["HTTP_ACCEPT"] = "application/json; version=2"

    def test_tag_validate_color(self):
        self.assertEqual(
            self.client.post(
                "/api/tags/",
                {"name": "test", "color": "#12fFaA"},
                format="json",
            ).status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            self.client.post(
                "/api/tags/",
                {"name": "test1", "color": "abcdef"},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                "/api/tags/",
                {"name": "test2", "color": "#abcdfg"},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                "/api/tags/",
                {"name": "test3", "color": "#asd"},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                "/api/tags/",
                {"name": "test4", "color": "#12121212"},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_tag_text_color(self):
        t = Tag.objects.create(name="tag1", color="#000000")
        self.assertEqual(
            self.client.get(f"/api/tags/{t.id}/", format="json").data["text_color"],
            "#ffffff",
        )

        t.color = "#ffffff"
        t.save()
        self.assertEqual(
            self.client.get(f"/api/tags/{t.id}/", format="json").data["text_color"],
            "#000000",
        )

        t.color = "asdf"
        t.save()
        self.assertEqual(
            self.client.get(f"/api/tags/{t.id}/", format="json").data["text_color"],
            "#000000",
        )

        t.color = "123"
        t.save()
        self.assertEqual(
            self.client.get(f"/api/tags/{t.id}/", format="json").data["text_color"],
            "#000000",
        )


class TestApiUiSettings(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/ui_settings/"

    def setUp(self):
        super().setUp()
        self.test_user = User.objects.create_superuser(username="test")
        self.test_user.first_name = "Test"
        self.test_user.last_name = "User"
        self.test_user.save()
        self.client.force_authenticate(user=self.test_user)

    def test_api_get_ui_settings(self):
        response = self.client.get(self.ENDPOINT, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data["user"],
            {
                "id": self.test_user.id,
                "username": self.test_user.username,
                "is_superuser": True,
                "groups": [],
                "first_name": self.test_user.first_name,
                "last_name": self.test_user.last_name,
            },
        )
        self.assertDictEqual(
            response.data["settings"],
            {
                "update_checking": {
                    "backend_setting": "default",
                },
            },
        )

    def test_api_set_ui_settings(self):
        settings = {
            "settings": {
                "dark_mode": {
                    "enabled": True,
                },
            },
        }

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(settings),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ui_settings = self.test_user.ui_settings
        self.assertDictEqual(
            ui_settings.settings,
            settings["settings"],
        )


class TestBulkEdit(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

        patcher = mock.patch("documents.bulk_edit.bulk_update_documents.delay")
        self.async_task = patcher.start()
        self.addCleanup(patcher.stop)
        self.c1 = Correspondent.objects.create(name="c1")
        self.c2 = Correspondent.objects.create(name="c2")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.dt2 = DocumentType.objects.create(name="dt2")
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.doc1 = Document.objects.create(checksum="A", title="A")
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            correspondent=self.c1,
            document_type=self.dt1,
        )
        self.doc3 = Document.objects.create(
            checksum="C",
            title="C",
            correspondent=self.c2,
            document_type=self.dt2,
        )
        self.doc4 = Document.objects.create(checksum="D", title="D")
        self.doc5 = Document.objects.create(checksum="E", title="E")
        self.doc2.tags.add(self.t1)
        self.doc3.tags.add(self.t2)
        self.doc4.tags.add(self.t1, self.t2)
        self.sp1 = StoragePath.objects.create(name="sp1", path="Something/{checksum}")

    def test_set_correspondent(self):
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.c2.id,
        )
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 3)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_correspondent(self):
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 0)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_type(self):
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.dt2.id,
        )
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 3)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_document_type(self):
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 0)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_storage_path(self):
        """
        GIVEN:
            - 5 documents without defined storage path
        WHEN:
            - Bulk edit called to add storage path to 1 document
        THEN:
            - Single document storage path update
        """
        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            self.sp1.id,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 4)

        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_unset_document_storage_path(self):
        """
        GIVEN:
            - 4 documents without defined storage path
            - 1 document with a defined storage
        WHEN:
            - Bulk edit called to remove storage path from 1 document
        THEN:
            - Single document storage path removed
        """
        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            self.sp1.id,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 4)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            None,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        self.async_task.assert_called()
        args, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_add_tag(self):
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.add_tag(
            [self.doc1.id, self.doc2.id, self.doc3.id, self.doc4.id],
            self.t1.id,
        )
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 4)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc3.id])

    def test_remove_tag(self):
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.remove_tag([self.doc1.id, self.doc3.id, self.doc4.id], self.t1.id)
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 1)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc4.id])

    def test_modify_tags(self):
        tag_unrelated = Tag.objects.create(name="unrelated")
        self.doc2.tags.add(tag_unrelated)
        self.doc3.tags.add(tag_unrelated)
        bulk_edit.modify_tags(
            [self.doc2.id, self.doc3.id],
            add_tags=[self.t2.id],
            remove_tags=[self.t1.id],
        )

        self.assertCountEqual(list(self.doc2.tags.all()), [self.t2, tag_unrelated])
        self.assertCountEqual(list(self.doc3.tags.all()), [self.t2, tag_unrelated])

        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        # TODO: doc3 should not be affected, but the query for that is rather complicated
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_delete(self):
        self.assertEqual(Document.objects.count(), 5)
        bulk_edit.delete([self.doc1.id, self.doc2.id])
        self.assertEqual(Document.objects.count(), 3)
        self.assertCountEqual(
            [doc.id for doc in Document.objects.all()],
            [self.doc3.id, self.doc4.id, self.doc5.id],
        )

    @mock.patch("documents.serialisers.bulk_edit.set_correspondent")
    def test_api_set_correspondent(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": self.c1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["correspondent"], self.c1.id)

    @mock.patch("documents.serialisers.bulk_edit.set_correspondent")
    def test_api_unset_correspondent(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": None},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertIsNone(kwargs["correspondent"])

    @mock.patch("documents.serialisers.bulk_edit.set_document_type")
    def test_api_set_type(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": self.dt1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["document_type"], self.dt1.id)

    @mock.patch("documents.serialisers.bulk_edit.set_document_type")
    def test_api_unset_type(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": None},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertIsNone(kwargs["document_type"])

    @mock.patch("documents.serialisers.bulk_edit.add_tag")
    def test_api_add_tag(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "add_tag",
                    "parameters": {"tag": self.t1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["tag"], self.t1.id)

    @mock.patch("documents.serialisers.bulk_edit.remove_tag")
    def test_api_remove_tag(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "remove_tag",
                    "parameters": {"tag": self.t1.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["tag"], self.t1.id)

    @mock.patch("documents.serialisers.bulk_edit.modify_tags")
    def test_api_modify_tags(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t1.id],
                        "remove_tags": [self.t2.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertListEqual(args[0], [self.doc1.id, self.doc3.id])
        self.assertEqual(kwargs["add_tags"], [self.t1.id])
        self.assertEqual(kwargs["remove_tags"], [self.t2.id])

    @mock.patch("documents.serialisers.bulk_edit.modify_tags")
    def test_api_modify_tags_not_provided(self, m):
        """
        GIVEN:
            - API data to modify tags is missing modify_tags field
        WHEN:
            - API to edit tags is called
        THEN:
            - API returns HTTP 400
            - modify_tags is not called
        """
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc3.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t1.id],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        m.assert_not_called()

    @mock.patch("documents.serialisers.bulk_edit.delete")
    def test_api_delete(self, m):
        m.return_value = "OK"
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc1.id], "method": "delete", "parameters": {}},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], [self.doc1.id])
        self.assertEqual(len(kwargs), 0)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_set_storage_path(self, m):
        """
        GIVEN:
            - API data to set the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args

        self.assertListEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["storage_path"], self.sp1.id)

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_api_unset_storage_path(self, m):
        """
        GIVEN:
            - API data to clear/unset the storage path of a document
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and None storage_path
        """
        m.return_value = "OK"

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": None},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()
        args, kwargs = m.call_args

        self.assertListEqual(args[0], [self.doc1.id])
        self.assertEqual(kwargs["storage_path"], None)

    def test_api_invalid_storage_path(self):
        """
        GIVEN:
            - API data to set the storage path of a document
            - Given storage_path ID isn't valid
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id + 10},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.async_task.assert_not_called()

    def test_api_set_storage_path_not_provided(self):
        """
        GIVEN:
            - API data to set the storage path of a document
            - API data is missing storage path ID
        WHEN:
            - API is called
        THEN:
            - set_storage_path is called with correct document IDs and storage_path ID
        """
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_storage_path",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.async_task.assert_not_called()

    def test_api_invalid_doc(self):
        self.assertEqual(Document.objects.count(), 5)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps({"documents": [-235], "method": "delete", "parameters": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 5)

    def test_api_invalid_method(self):
        self.assertEqual(Document.objects.count(), 5)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "exterminate",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 5)

    def test_api_invalid_correspondent(self):
        self.assertEqual(self.doc2.correspondent, self.c1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_correspondent",
                    "parameters": {"correspondent": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        doc2 = Document.objects.get(id=self.doc2.id)
        self.assertEqual(doc2.correspondent, self.c1)

    def test_api_no_correspondent(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_correspondent",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_invalid_document_type(self):
        self.assertEqual(self.doc2.document_type, self.dt1)
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_document_type",
                    "parameters": {"document_type": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        doc2 = Document.objects.get(id=self.doc2.id)
        self.assertEqual(doc2.document_type, self.dt1)

    def test_api_no_document_type(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "set_document_type",
                    "parameters": {},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_add_invalid_tag(self):
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "add_tag",
                    "parameters": {"tag": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(list(self.doc2.tags.all()), [self.t1])

    def test_api_add_tag_no_tag(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "add_tag", "parameters": {}},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_delete_invalid_tag(self):
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "remove_tag",
                    "parameters": {"tag": 345657},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(list(self.doc2.tags.all()), [self.t1])

    def test_api_delete_tag_no_tag(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {"documents": [self.doc2.id], "method": "remove_tag", "parameters": {}},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_modify_invalid_tags(self):
        self.assertEqual(list(self.doc2.tags.all()), [self.t1])
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {
                        "add_tags": [self.t2.id, 1657],
                        "remove_tags": [1123123],
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_modify_tags_no_tags(self):
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {"remove_tags": [1123123]},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id],
                    "method": "modify_tags",
                    "parameters": {"add_tags": [self.t2.id, 1657]},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_selection_data_empty(self):
        response = self.client.post(
            "/api/documents/selection_data/",
            json.dumps({"documents": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field, Entity in [
            ("selected_correspondents", Correspondent),
            ("selected_tags", Tag),
            ("selected_document_types", DocumentType),
        ]:
            self.assertEqual(len(response.data[field]), Entity.objects.count())
            for correspondent in response.data[field]:
                self.assertEqual(correspondent["document_count"], 0)
            self.assertCountEqual(
                map(lambda c: c["id"], response.data[field]),
                map(lambda c: c["id"], Entity.objects.values("id")),
            )

    def test_api_selection_data(self):
        response = self.client.post(
            "/api/documents/selection_data/",
            json.dumps(
                {"documents": [self.doc1.id, self.doc2.id, self.doc4.id, self.doc5.id]},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertCountEqual(
            response.data["selected_correspondents"],
            [
                {"id": self.c1.id, "document_count": 1},
                {"id": self.c2.id, "document_count": 0},
            ],
        )
        self.assertCountEqual(
            response.data["selected_tags"],
            [
                {"id": self.t1.id, "document_count": 2},
                {"id": self.t2.id, "document_count": 1},
            ],
        )
        self.assertCountEqual(
            response.data["selected_document_types"],
            [
                {"id": self.c1.id, "document_count": 1},
                {"id": self.c2.id, "document_count": 0},
            ],
        )

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_set_permissions(self, m):
        m.return_value = "OK"
        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")
        permissions = {
            "view": {
                "users": [user1.id, user2.id],
                "groups": None,
            },
            "change": {
                "users": [user1.id],
                "groups": None,
            },
        }

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertCountEqual(args[0], [self.doc2.id, self.doc3.id])
        self.assertEqual(len(kwargs["set_permissions"]["view"]["users"]), 2)

    @mock.patch("documents.serialisers.bulk_edit.set_permissions")
    def test_insufficient_permissions_ownership(self, m):
        """
        GIVEN:
            - Documents owned by user other than logged in user
        WHEN:
            - set_permissions bulk edit API endpoint is called
        THEN:
            - User is not able to change permissions
        """
        m.return_value = "OK"
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        self.client.force_authenticate(user=user1)

        permissions = {
            "owner": user1.id,
        }

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "method": "set_permissions",
                    "parameters": {"set_permissions": permissions},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        m.assert_called_once()

    @mock.patch("documents.serialisers.bulk_edit.set_storage_path")
    def test_insufficient_permissions_edit(self, m):
        """
        GIVEN:
            - Documents for which current user only has view permissions
        WHEN:
            - API is called
        THEN:
            - set_storage_path is only called if user can edit all docs
        """
        m.return_value = "OK"
        self.doc1.owner = User.objects.get(username="temp_admin")
        self.doc1.save()
        user1 = User.objects.create(username="user1")
        assign_perm("view_document", user1, self.doc1)
        self.client.force_authenticate(user=user1)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        m.assert_not_called()
        self.assertEqual(response.content, b"Insufficient permissions")

        assign_perm("change_document", user1, self.doc1)

        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id, self.doc3.id],
                    "method": "set_storage_path",
                    "parameters": {"storage_path": self.sp1.id},
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        m.assert_called_once()


class TestBulkDownload(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/documents/bulk_download/"

    def setUp(self):
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

        self.doc1 = Document.objects.create(title="unrelated", checksum="A")
        self.doc2 = Document.objects.create(
            title="document A",
            filename="docA.pdf",
            mime_type="application/pdf",
            checksum="B",
            created=timezone.make_aware(datetime.datetime(2021, 1, 1)),
        )
        self.doc2b = Document.objects.create(
            title="document A",
            filename="docA2.pdf",
            mime_type="application/pdf",
            checksum="D",
            created=timezone.make_aware(datetime.datetime(2021, 1, 1)),
        )
        self.doc3 = Document.objects.create(
            title="document B",
            filename="docB.jpg",
            mime_type="image/jpeg",
            checksum="C",
            created=timezone.make_aware(datetime.datetime(2020, 3, 21)),
            archive_filename="docB.pdf",
            archive_checksum="D",
        )

        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"),
            self.doc2.source_path,
        )
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.png"),
            self.doc2b.source_path,
        )
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "simple.jpg"),
            self.doc3.source_path,
        )
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "samples", "test_with_bom.pdf"),
            self.doc3.archive_path,
        )

    def test_download_originals(self):
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {"documents": [self.doc2.id, self.doc3.id], "content": "originals"},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 2)
            self.assertIn("2021-01-01 document A.pdf", zipf.namelist())
            self.assertIn("2020-03-21 document B.jpg", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(f.read(), zipf.read("2021-01-01 document A.pdf"))

            with self.doc3.source_file as f:
                self.assertEqual(f.read(), zipf.read("2020-03-21 document B.jpg"))

    def test_download_default(self):
        response = self.client.post(
            self.ENDPOINT,
            json.dumps({"documents": [self.doc2.id, self.doc3.id]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 2)
            self.assertIn("2021-01-01 document A.pdf", zipf.namelist())
            self.assertIn("2020-03-21 document B.pdf", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(f.read(), zipf.read("2021-01-01 document A.pdf"))

            with self.doc3.archive_file as f:
                self.assertEqual(f.read(), zipf.read("2020-03-21 document B.pdf"))

    def test_download_both(self):
        response = self.client.post(
            self.ENDPOINT,
            json.dumps({"documents": [self.doc2.id, self.doc3.id], "content": "both"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 3)
            self.assertIn("originals/2021-01-01 document A.pdf", zipf.namelist())
            self.assertIn("archive/2020-03-21 document B.pdf", zipf.namelist())
            self.assertIn("originals/2020-03-21 document B.jpg", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("originals/2021-01-01 document A.pdf"),
                )

            with self.doc3.archive_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("archive/2020-03-21 document B.pdf"),
                )

            with self.doc3.source_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("originals/2020-03-21 document B.jpg"),
                )

    def test_filename_clashes(self):
        response = self.client.post(
            self.ENDPOINT,
            json.dumps({"documents": [self.doc2.id, self.doc2b.id]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 2)

            self.assertIn("2021-01-01 document A.pdf", zipf.namelist())
            self.assertIn("2021-01-01 document A_01.pdf", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(f.read(), zipf.read("2021-01-01 document A.pdf"))

            with self.doc2b.source_file as f:
                self.assertEqual(f.read(), zipf.read("2021-01-01 document A_01.pdf"))

    def test_compression(self):
        self.client.post(
            self.ENDPOINT,
            json.dumps(
                {"documents": [self.doc2.id, self.doc2b.id], "compression": "lzma"},
            ),
            content_type="application/json",
        )

    @override_settings(FILENAME_FORMAT="{correspondent}/{title}")
    def test_formatted_download_originals(self):
        """
        GIVEN:
            - Defined file naming format
        WHEN:
            - Bulk download request for original documents
            - Bulk download request requests to follow format
        THEN:
            - Files defined in resulting zipfile are formatted
        """

        c = Correspondent.objects.create(name="test")
        c2 = Correspondent.objects.create(name="a space name")

        self.doc2.correspondent = c
        self.doc2.title = "This is Doc 2"
        self.doc2.save()

        self.doc3.correspondent = c2
        self.doc3.title = "Title 2 - Doc 3"
        self.doc3.save()

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "content": "originals",
                    "follow_formatting": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 2)
            self.assertIn("a space name/Title 2 - Doc 3.jpg", zipf.namelist())
            self.assertIn("test/This is Doc 2.pdf", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(f.read(), zipf.read("test/This is Doc 2.pdf"))

            with self.doc3.source_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("a space name/Title 2 - Doc 3.jpg"),
                )

    @override_settings(FILENAME_FORMAT="somewhere/{title}")
    def test_formatted_download_archive(self):
        """
        GIVEN:
            - Defined file naming format
        WHEN:
            - Bulk download request for archive documents
            - Bulk download request requests to follow format
        THEN:
            - Files defined in resulting zipfile are formatted
        """

        self.doc2.title = "This is Doc 2"
        self.doc2.save()

        self.doc3.title = "Title 2 - Doc 3"
        self.doc3.save()
        print(self.doc3.archive_path)
        print(self.doc3.archive_filename)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "follow_formatting": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 2)
            self.assertIn("somewhere/This is Doc 2.pdf", zipf.namelist())
            self.assertIn("somewhere/Title 2 - Doc 3.pdf", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(f.read(), zipf.read("somewhere/This is Doc 2.pdf"))

            with self.doc3.archive_file as f:
                self.assertEqual(f.read(), zipf.read("somewhere/Title 2 - Doc 3.pdf"))

    @override_settings(FILENAME_FORMAT="{document_type}/{title}")
    def test_formatted_download_both(self):
        """
        GIVEN:
            - Defined file naming format
        WHEN:
            - Bulk download request for original documents and archive documents
            - Bulk download request requests to follow format
        THEN:
            - Files defined in resulting zipfile are formatted
        """

        dc1 = DocumentType.objects.create(name="bill")
        dc2 = DocumentType.objects.create(name="statement")

        self.doc2.document_type = dc1
        self.doc2.title = "This is Doc 2"
        self.doc2.save()

        self.doc3.document_type = dc2
        self.doc3.title = "Title 2 - Doc 3"
        self.doc3.save()

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc2.id, self.doc3.id],
                    "content": "both",
                    "follow_formatting": True,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertEqual(len(zipf.filelist), 3)
            self.assertIn("originals/bill/This is Doc 2.pdf", zipf.namelist())
            self.assertIn("archive/statement/Title 2 - Doc 3.pdf", zipf.namelist())
            self.assertIn("originals/statement/Title 2 - Doc 3.jpg", zipf.namelist())

            with self.doc2.source_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("originals/bill/This is Doc 2.pdf"),
                )

            with self.doc3.archive_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("archive/statement/Title 2 - Doc 3.pdf"),
                )

            with self.doc3.source_file as f:
                self.assertEqual(
                    f.read(),
                    zipf.read("originals/statement/Title 2 - Doc 3.jpg"),
                )


class TestApiAuth(DirectoriesMixin, APITestCase):
    def test_auth_required(self):
        d = Document.objects.create(title="Test")

        self.assertEqual(
            self.client.get("/api/documents/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            self.client.get(f"/api/documents/{d.id}/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/documents/{d.id}/download/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/documents/{d.id}/preview/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/documents/{d.id}/thumb/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            self.client.get("/api/tags/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/correspondents/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/document_types/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            self.client.get("/api/logs/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/saved_views/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            self.client.get("/api/search/autocomplete/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/documents/bulk_edit/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/documents/bulk_download/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get("/api/documents/selection_data/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_api_version_no_auth(self):
        response = self.client.get("/api/")
        self.assertNotIn("X-Api-Version", response)
        self.assertNotIn("X-Version", response)

    def test_api_version_with_auth(self):
        user = User.objects.create_superuser(username="test")
        self.client.force_authenticate(user)
        response = self.client.get("/api/")
        self.assertIn("X-Api-Version", response)
        self.assertIn("X-Version", response)

    def test_api_insufficient_permissions(self):
        user = User.objects.create_user(username="test")
        self.client.force_authenticate(user)

        Document.objects.create(title="Test")

        self.assertEqual(
            self.client.get("/api/documents/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            self.client.get("/api/tags/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/correspondents/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/document_types/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            self.client.get("/api/logs/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/saved_views/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_api_sufficient_permissions(self):
        user = User.objects.create_user(username="test")
        user.user_permissions.add(*Permission.objects.all())
        self.client.force_authenticate(user)

        Document.objects.create(title="Test")

        self.assertEqual(
            self.client.get("/api/documents/").status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(self.client.get("/api/tags/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get("/api/correspondents/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get("/api/document_types/").status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(self.client.get("/api/logs/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get("/api/saved_views/").status_code,
            status.HTTP_200_OK,
        )

    def test_api_get_object_permissions(self):
        user1 = User.objects.create_user(username="test1")
        user2 = User.objects.create_user(username="test2")
        user1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        self.client.force_authenticate(user1)

        self.assertEqual(
            self.client.get("/api/documents/").status_code,
            status.HTTP_200_OK,
        )

        d = Document.objects.create(title="Test", content="the content 1", checksum="1")

        # no owner
        self.assertEqual(
            self.client.get(f"/api/documents/{d.id}/").status_code,
            status.HTTP_200_OK,
        )

        d2 = Document.objects.create(
            title="Test 2",
            content="the content 2",
            checksum="2",
            owner=user2,
        )

        self.assertEqual(
            self.client.get(f"/api/documents/{d2.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_api_default_owner(self):
        """
        GIVEN:
            - API request to create an object (Tag)
        WHEN:
            - owner is not set at all
        THEN:
            - Object created with current user as owner
        """
        user1 = User.objects.create_superuser(username="user1")

        self.client.force_authenticate(user1)

        response = self.client.post(
            "/api/tags/",
            json.dumps(
                {
                    "name": "test1",
                    "matching_algorithm": MatchingModel.MATCH_AUTO,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tag1 = Tag.objects.filter(name="test1").first()
        self.assertEqual(tag1.owner, user1)

    def test_api_set_no_owner(self):
        """
        GIVEN:
            - API request to create an object (Tag)
        WHEN:
            - owner is passed as None
        THEN:
            - Object created with no owner
        """
        user1 = User.objects.create_superuser(username="user1")

        self.client.force_authenticate(user1)

        response = self.client.post(
            "/api/tags/",
            json.dumps(
                {
                    "name": "test1",
                    "matching_algorithm": MatchingModel.MATCH_AUTO,
                    "owner": None,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tag1 = Tag.objects.filter(name="test1").first()
        self.assertEqual(tag1.owner, None)

    def test_api_set_owner_w_permissions(self):
        """
        GIVEN:
            - API request to create an object (Tag) that supplies set_permissions object
        WHEN:
            - owner is passed as user id
            - view > users is set & view > groups is set
        THEN:
            - Object permissions are set appropriately
        """
        user1 = User.objects.create_superuser(username="user1")
        user2 = User.objects.create(username="user2")
        group1 = Group.objects.create(name="group1")

        self.client.force_authenticate(user1)

        response = self.client.post(
            "/api/tags/",
            json.dumps(
                {
                    "name": "test1",
                    "matching_algorithm": MatchingModel.MATCH_AUTO,
                    "owner": user1.id,
                    "set_permissions": {
                        "view": {
                            "users": [user2.id],
                            "groups": [group1.id],
                        },
                        "change": {
                            "users": None,
                            "groups": None,
                        },
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tag1 = Tag.objects.filter(name="test1").first()

        from guardian.core import ObjectPermissionChecker

        checker = ObjectPermissionChecker(user2)
        self.assertEqual(checker.has_perm("view_tag", tag1), True)
        self.assertIn("view_tag", get_perms(group1, tag1))

    def test_api_set_other_owner_w_permissions(self):
        """
        GIVEN:
            - API request to create an object (Tag)
        WHEN:
            - a different owner than is logged in is set
            - view > groups is set
        THEN:
            - Object permissions are set appropriately
        """
        user1 = User.objects.create_superuser(username="user1")
        user2 = User.objects.create(username="user2")
        group1 = Group.objects.create(name="group1")

        self.client.force_authenticate(user1)

        response = self.client.post(
            "/api/tags/",
            json.dumps(
                {
                    "name": "test1",
                    "matching_algorithm": MatchingModel.MATCH_AUTO,
                    "owner": user2.id,
                    "set_permissions": {
                        "view": {
                            "users": None,
                            "groups": [group1.id],
                        },
                        "change": {
                            "users": None,
                            "groups": None,
                        },
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tag1 = Tag.objects.filter(name="test1").first()

        self.assertEqual(tag1.owner, user2)
        self.assertIn("view_tag", get_perms(group1, tag1))

    def test_api_set_doc_permissions(self):
        """
        GIVEN:
            - API request to update doc permissions and owner
        WHEN:
            - owner is set
            - view > users is set & view > groups is set
        THEN:
            - Object permissions are set appropriately
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document",
        )
        user1 = User.objects.create_superuser(username="user1")
        user2 = User.objects.create(username="user2")
        group1 = Group.objects.create(name="group1")

        self.client.force_authenticate(user1)

        response = self.client.patch(
            f"/api/documents/{doc.id}/",
            json.dumps(
                {
                    "owner": user1.id,
                    "set_permissions": {
                        "view": {
                            "users": [user2.id],
                            "groups": [group1.id],
                        },
                        "change": {
                            "users": None,
                            "groups": None,
                        },
                    },
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc = Document.objects.get(pk=doc.id)

        self.assertEqual(doc.owner, user1)
        from guardian.core import ObjectPermissionChecker

        checker = ObjectPermissionChecker(user2)
        self.assertTrue(checker.has_perm("view_document", doc))
        self.assertIn("view_document", get_perms(group1, doc))

    def test_dynamic_permissions_fields(self):
        user1 = User.objects.create_user(username="user1")
        user1.user_permissions.add(*Permission.objects.filter(codename="view_document"))
        user2 = User.objects.create_user(username="user2")

        Document.objects.create(title="Test", content="content 1", checksum="1")
        doc2 = Document.objects.create(
            title="Test2",
            content="content 2",
            checksum="2",
            owner=user2,
        )
        doc3 = Document.objects.create(
            title="Test3",
            content="content 3",
            checksum="3",
            owner=user2,
        )

        assign_perm("view_document", user1, doc2)
        assign_perm("view_document", user1, doc3)
        assign_perm("change_document", user1, doc3)

        self.client.force_authenticate(user1)

        response = self.client.get(
            "/api/documents/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertNotIn("permissions", resp_data["results"][0])
        self.assertIn("user_can_change", resp_data["results"][0])
        self.assertEqual(resp_data["results"][0]["user_can_change"], True)  # doc1
        self.assertEqual(resp_data["results"][1]["user_can_change"], False)  # doc2
        self.assertEqual(resp_data["results"][2]["user_can_change"], True)  # doc3

        response = self.client.get(
            "/api/documents/?full_perms=true",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertIn("permissions", resp_data["results"][0])
        self.assertNotIn("user_can_change", resp_data["results"][0])


class TestApiRemoteVersion(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/remote_version/"

    def setUp(self):
        super().setUp()

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_no_update_prefix(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps({"tag_name": "ngx-1.6.0"}).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "1.6.0",
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_no_update_no_prefix(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps(
            {"tag_name": version.__full_version_str__},
        ).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": version.__full_version_str__,
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_update(self, urlopen_mock):
        new_version = (
            version.__version__[0],
            version.__version__[1],
            version.__version__[2] + 1,
        )
        new_version_str = ".".join(map(str, new_version))

        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps(
            {"tag_name": new_version_str},
        ).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": new_version_str,
                "update_available": True,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_bad_json(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = b'{ "blah":'
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "0.0.0",
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_exception(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.side_effect = urllib.error.URLError("an error")
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "0.0.0",
                "update_available": False,
            },
        )


class TestApiObjects(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

        self.tag1 = Tag.objects.create(name="t1", is_inbox_tag=True)
        self.tag2 = Tag.objects.create(name="t2")
        self.tag3 = Tag.objects.create(name="t3")
        self.c1 = Correspondent.objects.create(name="c1")
        self.c2 = Correspondent.objects.create(name="c2")
        self.c3 = Correspondent.objects.create(name="c3")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.dt2 = DocumentType.objects.create(name="dt2")
        self.sp1 = StoragePath.objects.create(name="sp1", path="Something/{title}")
        self.sp2 = StoragePath.objects.create(name="sp2", path="Something2/{title}")

    def test_object_filters(self):
        response = self.client.get(
            f"/api/tags/?id={self.tag2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        response = self.client.get(
            f"/api/tags/?id__in={self.tag1.id},{self.tag3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        response = self.client.get(
            f"/api/correspondents/?id={self.c2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        response = self.client.get(
            f"/api/correspondents/?id__in={self.c1.id},{self.c3.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        response = self.client.get(
            f"/api/document_types/?id={self.dt1.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        response = self.client.get(
            f"/api/document_types/?id__in={self.dt1.id},{self.dt2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

        response = self.client.get(
            f"/api/storage_paths/?id={self.sp1.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

        response = self.client.get(
            f"/api/storage_paths/?id__in={self.sp1.id},{self.sp2.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)


class TestApiStoragePaths(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/storage_paths/"

    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

        self.sp1 = StoragePath.objects.create(name="sp1", path="Something/{checksum}")

    def test_api_get_storage_path(self):
        """
        GIVEN:
            - API request to get all storage paths
        WHEN:
            - API is called
        THEN:
            - Existing storage paths are returned
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        resp_storage_path = response.data["results"][0]
        self.assertEqual(resp_storage_path["id"], self.sp1.id)
        self.assertEqual(resp_storage_path["path"], self.sp1.path)

    def test_api_create_storage_path(self):
        """
        GIVEN:
            - API request to create a storage paths
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New storage path is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "A storage path",
                    "path": "Somewhere/{asn}",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StoragePath.objects.count(), 2)

    def test_api_create_invalid_storage_path(self):
        """
        GIVEN:
            - API request to create a storage paths
            - Storage path format is incorrect
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
            - No storage path is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Another storage path",
                    "path": "Somewhere/{correspdent}",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StoragePath.objects.count(), 1)

    def test_api_storage_path_placeholders(self):
        """
        GIVEN:
            - API request to create a storage path with placeholders
            - Storage path is valid
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New storage path is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Storage path with placeholders",
                    "path": "{title}/{correspondent}/{document_type}/{created}/{created_year}"
                    "/{created_year_short}/{created_month}/{created_month_name}"
                    "/{created_month_name_short}/{created_day}/{added}/{added_year}"
                    "/{added_year_short}/{added_month}/{added_month_name}"
                    "/{added_month_name_short}/{added_day}/{asn}/{tags}"
                    "/{tag_list}/{owner_username}/{original_name}/{doc_pk}/",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StoragePath.objects.count(), 2)

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_update_storage_path(self, bulk_update_mock):
        """
        GIVEN:
            - API request to get all storage paths
        WHEN:
            - API is called
        THEN:
            - Existing storage paths are returned
        """
        document = Document.objects.create(
            mime_type="application/pdf",
            storage_path=self.sp1,
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{self.sp1.pk}/",
            data={
                "path": "somewhere/{created} - {title}",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        bulk_update_mock.assert_called_once()

        args, _ = bulk_update_mock.call_args

        self.assertCountEqual([document.pk], args[0])


class TestTasks(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/tasks/"
    ENDPOINT_ACKNOWLEDGE = "/api/acknowledge_tasks/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_tasks(self):
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get tasks
        THEN:
            - Attempting and pending tasks are serialized and provided
        """

        task1 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        task2 = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        returned_task1 = response.data[1]
        returned_task2 = response.data[0]

        self.assertEqual(returned_task1["task_id"], task1.task_id)
        self.assertEqual(returned_task1["status"], celery.states.PENDING)
        self.assertEqual(returned_task1["task_file_name"], task1.task_file_name)

        self.assertEqual(returned_task2["task_id"], task2.task_id)
        self.assertEqual(returned_task2["status"], celery.states.PENDING)
        self.assertEqual(returned_task2["task_file_name"], task2.task_file_name)

    def test_get_single_task_status(self):
        """
        GIVEN
            - Query parameter for a valid task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - Single task data is returned
        """

        id1 = str(uuid.uuid4())
        task1 = PaperlessTask.objects.create(
            task_id=id1,
            task_file_name="task_one.pdf",
        )

        _ = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + f"?task_id={id1}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        returned_task1 = response.data[0]

        self.assertEqual(returned_task1["task_id"], task1.task_id)

    def test_get_single_task_status_not_valid(self):
        """
        GIVEN
            - Query parameter for a non-existent task ID
        WHEN:
            - API call is made to get task status
        THEN:
            - No task data is returned
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        _ = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_two.pdf",
        )

        response = self.client.get(self.ENDPOINT + "?task_id=bad-task-id")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_acknowledge_tasks(self):
        """
        GIVEN:
            - Attempted celery tasks
        WHEN:
            - API call is made to get mark task as acknowledged
        THEN:
            - Task is marked as acknowledged
        """
        task = PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
        )

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(len(response.data), 1)

        response = self.client.post(
            self.ENDPOINT_ACKNOWLEDGE,
            {"tasks": [task.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(len(response.data), 0)

    def test_task_result_no_error(self):
        """
        GIVEN:
            - A celery task completed without error
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned data includes the task result
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.SUCCESS,
            result="Success. New document id 1 created",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["result"], "Success. New document id 1 created")
        self.assertEqual(returned_data["related_document"], "1")

    def test_task_result_with_error(self):
        """
        GIVEN:
            - A celery task completed with an exception
        WHEN:
            - API call is made to get tasks
        THEN:
            - The returned result is the exception info
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="task_one.pdf",
            status=celery.states.FAILURE,
            result="test.pdf: Not consuming test.pdf: It is a duplicate.",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(
            returned_data["result"],
            "test.pdf: Not consuming test.pdf: It is a duplicate.",
        )

    def test_task_name_webui(self):
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the webui
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="test.pdf",
            task_name="documents.tasks.some_task",
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "test.pdf")

    def test_task_name_consume_folder(self):
        """
        GIVEN:
            - Attempted celery task
            - Task was created through the consume folder
        WHEN:
            - API call is made to get tasks
        THEN:
            - Returned data include the filename
        """
        PaperlessTask.objects.create(
            task_id=str(uuid.uuid4()),
            task_file_name="anothertest.pdf",
            task_name="documents.tasks.some_task",
            status=celery.states.SUCCESS,
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        returned_data = response.data[0]

        self.assertEqual(returned_data["task_file_name"], "anothertest.pdf")


class TestApiUser(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/users/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_users(self):
        """
        GIVEN:
            - Configured users
        WHEN:
            - API call is made to get users
        THEN:
            - Configured users are provided
        """

        user1 = User.objects.create(
            username="testuser",
            password="test",
            first_name="Test",
            last_name="User",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        returned_user2 = response.data["results"][1]

        self.assertEqual(returned_user2["username"], user1.username)
        self.assertEqual(returned_user2["password"], "**********")
        self.assertEqual(returned_user2["first_name"], user1.first_name)
        self.assertEqual(returned_user2["last_name"], user1.last_name)

    def test_create_user(self):
        """
        WHEN:
            - API request is made to add a user account
        THEN:
            - A new user account is created
        """

        user1 = {
            "username": "testuser",
            "password": "test",
            "first_name": "Test",
            "last_name": "User",
        }

        response = self.client.post(
            self.ENDPOINT,
            data=user1,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        returned_user1 = User.objects.get(username="testuser")

        self.assertEqual(returned_user1.username, user1["username"])
        self.assertEqual(returned_user1.first_name, user1["first_name"])
        self.assertEqual(returned_user1.last_name, user1["last_name"])

    def test_delete_user(self):
        """
        GIVEN:
            - Existing user account
        WHEN:
            - API request is made to delete a user account
        THEN:
            - Account is deleted
        """

        user1 = User.objects.create(
            username="testuser",
            password="test",
            first_name="Test",
            last_name="User",
        )

        nUsers = User.objects.count()

        response = self.client.delete(
            f"{self.ENDPOINT}{user1.pk}/",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(User.objects.count(), nUsers - 1)

    def test_update_user(self):
        """
        GIVEN:
            - Existing user accounts
        WHEN:
            - API request is made to update user account
        THEN:
            - The user account is updated, password only updated if not '****'
        """

        user1 = User.objects.create(
            username="testuser",
            password="test",
            first_name="Test",
            last_name="User",
        )

        initial_password = user1.password

        response = self.client.patch(
            f"{self.ENDPOINT}{user1.pk}/",
            data={
                "first_name": "Updated Name 1",
                "password": "******",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_user1 = User.objects.get(pk=user1.pk)
        self.assertEqual(returned_user1.first_name, "Updated Name 1")
        self.assertEqual(returned_user1.password, initial_password)

        response = self.client.patch(
            f"{self.ENDPOINT}{user1.pk}/",
            data={
                "first_name": "Updated Name 2",
                "password": "123xyz",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_user2 = User.objects.get(pk=user1.pk)
        self.assertEqual(returned_user2.first_name, "Updated Name 2")
        self.assertNotEqual(returned_user2.password, initial_password)


class TestApiGroup(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/groups/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_groups(self):
        """
        GIVEN:
            - Configured groups
        WHEN:
            - API call is made to get groups
        THEN:
            - Configured groups are provided
        """

        group1 = Group.objects.create(
            name="Test Group",
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        returned_group1 = response.data["results"][0]

        self.assertEqual(returned_group1["name"], group1.name)

    def test_create_group(self):
        """
        WHEN:
            - API request is made to add a group
        THEN:
            - A new group is created
        """

        group1 = {
            "name": "Test Group",
        }

        response = self.client.post(
            self.ENDPOINT,
            data=group1,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        returned_group1 = Group.objects.get(name="Test Group")

        self.assertEqual(returned_group1.name, group1["name"])

    def test_delete_group(self):
        """
        GIVEN:
            - Existing group
        WHEN:
            - API request is made to delete a group
        THEN:
            - Group is deleted
        """

        group1 = Group.objects.create(
            name="Test Group",
        )

        response = self.client.delete(
            f"{self.ENDPOINT}{group1.pk}/",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(len(Group.objects.all()), 0)

    def test_update_group(self):
        """
        GIVEN:
            - Existing groups
        WHEN:
            - API request is made to update group
        THEN:
            - The group is updated
        """

        group1 = Group.objects.create(
            name="Test Group",
        )

        response = self.client.patch(
            f"{self.ENDPOINT}{group1.pk}/",
            data={
                "name": "Updated Name 1",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_group1 = Group.objects.get(pk=group1.pk)
        self.assertEqual(returned_group1.name, "Updated Name 1")


class TestBulkEditObjectPermissions(APITestCase):
    def setUp(self):
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.c1 = Correspondent.objects.create(name="c1")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.sp1 = StoragePath.objects.create(name="sp1")
        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")

    def test_bulk_object_set_permissions(self):
        """
        GIVEN:
            - Existing objects
        WHEN:
            - bulk_edit_object_perms API endpoint is called
        THEN:
            - Permissions and / or owner are changed
        """
        permissions = {
            "view": {
                "users": [self.user1.id, self.user2.id],
                "groups": [],
            },
            "change": {
                "users": [self.user1.id],
                "groups": [],
            },
        }

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "permissions": permissions,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1, get_users_with_perms(self.t1))

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.c1.id],
                    "object_type": "correspondents",
                    "permissions": permissions,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1, get_users_with_perms(self.c1))

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.dt1.id],
                    "object_type": "document_types",
                    "permissions": permissions,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1, get_users_with_perms(self.dt1))

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.sp1.id],
                    "object_type": "storage_paths",
                    "permissions": permissions,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1, get_users_with_perms(self.sp1))

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "owner": self.user3.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Tag.objects.get(pk=self.t2.id).owner, self.user3)

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.sp1.id],
                    "object_type": "storage_paths",
                    "owner": self.user3.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(StoragePath.objects.get(pk=self.sp1.id).owner, self.user3)

    def test_bulk_edit_object_permissions_insufficient_perms(self):
        """
        GIVEN:
            - Objects owned by user other than logged in user
        WHEN:
            - bulk_edit_object_perms API endpoint is called
        THEN:
            - User is not able to change permissions
        """
        self.t1.owner = User.objects.get(username="temp_admin")
        self.t1.save()
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "owner": self.user1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")

    def test_bulk_edit_object_permissions_validation(self):
        """
        GIVEN:
            - Existing objects
        WHEN:
            - bulk_edit_object_perms API endpoint is called with invalid params
        THEN:
            - Validation fails
        """
        # not a list
        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": self.t1.id,
                    "object_type": "tags",
                    "owner": self.user1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # not a list of ints
        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": ["one"],
                    "object_type": "tags",
                    "owner": self.user1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # duplicates
        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id, self.t1.id],
                    "object_type": "tags",
                    "owner": self.user1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # not a valid object type
        response = self.client.post(
            "/api/bulk_edit_object_perms/",
            json.dumps(
                {
                    "objects": [1],
                    "object_type": "madeup",
                    "owner": self.user1.id,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestApiConsumptionTemplates(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/consumption_templates/"

    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)
        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")
        self.group1 = Group.objects.create(name="group1")

        self.c = Correspondent.objects.create(name="Correspondent Name")
        self.c2 = Correspondent.objects.create(name="Correspondent Name 2")
        self.dt = DocumentType.objects.create(name="DocType Name")
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.t3 = Tag.objects.create(name="t3")
        self.sp = StoragePath.objects.create(path="/test/")

        self.ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{int(DocumentSource.ApiUpload)},{int(DocumentSource.ConsumeFolder)},{int(DocumentSource.MailFetch)}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        self.ct.assign_tags.add(self.t1)
        self.ct.assign_tags.add(self.t2)
        self.ct.assign_tags.add(self.t3)
        self.ct.assign_view_users.add(self.user3.pk)
        self.ct.assign_view_groups.add(self.group1.pk)
        self.ct.assign_change_users.add(self.user3.pk)
        self.ct.assign_change_groups.add(self.group1.pk)
        self.ct.save()

    def test_api_get_consumption_template(self):
        """
        GIVEN:
            - API request to get all consumption template
        WHEN:
            - API is called
        THEN:
            - Existing consumption templates are returned
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        resp_consumption_template = response.data["results"][0]
        self.assertEqual(resp_consumption_template["id"], self.ct.id)
        self.assertEqual(
            resp_consumption_template["assign_correspondent"],
            self.ct.assign_correspondent.pk,
        )

    def test_api_create_consumption_template(self):
        """
        GIVEN:
            - API request to create a consumption template
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New template is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*test*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ConsumptionTemplate.objects.count(), 2)

    def test_api_create_invalid_consumption_template(self):
        """
        GIVEN:
            - API request to create a consumption template
            - Neither file name nor path filter are specified
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
            - No template is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StoragePath.objects.count(), 1)

    def test_api_create_consumption_template_with_mailrule(self):
        """
        GIVEN:
            - API request to create a consumption template with a mail rule but no MailFetch source
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New template is created with MailFetch as source
        """
        account1 = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        rule1 = MailRule.objects.create(
            name="Rule1",
            account=account1,
            folder="INBOX",
            filter_from="from@example.com",
            filter_to="someone@somewhere.com",
            filter_subject="subject",
            filter_body="body",
            filter_attachment_filename="file.pdf",
            maximum_age=30,
            action=MailRule.MailAction.MARK_READ,
            assign_title_from=MailRule.TitleSource.FROM_SUBJECT,
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_NOTHING,
            order=0,
            attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
        )
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_mailrule": rule1.pk,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ConsumptionTemplate.objects.count(), 2)
        ct = ConsumptionTemplate.objects.get(name="Template 2")
        self.assertEqual(ct.sources, [int(DocumentSource.MailFetch).__str__()])


class TestApiProfile(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/profile/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(
            username="temp_admin",
            first_name="firstname",
            last_name="surname",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to get profile
        THEN:
            - Profile is returned
        """

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], self.user.first_name)
        self.assertEqual(response.data["last_name"], self.user.last_name)

    def test_update_profile(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to update profile
        THEN:
            - Profile is updated
        """

        user_data = {
            "email": "new@email.com",
            "password": "superpassword1234",
            "first_name": "new first name",
            "last_name": "new last name",
        }
        response = self.client.patch(self.ENDPOINT, user_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username=self.user.username)
        self.assertTrue(user.check_password(user_data["password"]))
        self.assertEqual(user.email, user_data["email"])
        self.assertEqual(user.first_name, user_data["first_name"])
        self.assertEqual(user.last_name, user_data["last_name"])

    def test_update_auth_token(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to generate auth token
        THEN:
            - Token is created the first time, updated the second
        """

        self.assertEqual(len(Token.objects.all()), 0)

        response = self.client.post(f"{self.ENDPOINT}generate_auth_token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token1 = Token.objects.filter(user=self.user).first()
        self.assertIsNotNone(token1)

        response = self.client.post(f"{self.ENDPOINT}generate_auth_token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token2 = Token.objects.filter(user=self.user).first()

        self.assertNotEqual(token1.key, token2.key)
