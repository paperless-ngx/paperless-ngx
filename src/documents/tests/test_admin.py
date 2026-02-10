import types
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from documents import index
from documents.admin import DocumentAdmin
from documents.admin import TagAdmin
from documents.models import Document
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from paperless.admin import PaperlessUserAdmin


class TestDocumentAdmin(DirectoriesMixin, TestCase):
    def get_document_from_index(self, doc):
        ix = index.open_index()
        with ix.searcher() as searcher:
            return searcher.document(id=doc.id)

    def setUp(self) -> None:
        super().setUp()
        self.doc_admin = DocumentAdmin(model=Document, admin_site=AdminSite())

    def test_save_model(self) -> None:
        doc = Document.objects.create(title="test")

        doc.title = "new title"
        self.doc_admin.save_model(None, doc, None, None)
        self.assertEqual(Document.objects.get(id=doc.id).title, "new title")
        self.assertEqual(self.get_document_from_index(doc)["id"], doc.id)

    def test_delete_model(self) -> None:
        doc = Document.objects.create(title="test")
        index.add_or_update_document(doc)
        self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_model(None, doc)

        self.assertRaises(Document.DoesNotExist, Document.objects.get, id=doc.id)
        self.assertIsNone(self.get_document_from_index(doc))

    def test_delete_queryset(self) -> None:
        docs = []
        for i in range(42):
            doc = Document.objects.create(
                title="Many documents with the same title",
                checksum=f"{i:02}",
            )
            docs.append(doc)
            index.add_or_update_document(doc)

        self.assertEqual(Document.objects.count(), 42)

        for doc in docs:
            self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_queryset(None, Document.objects.all())

        self.assertEqual(Document.objects.count(), 0)

        for doc in docs:
            self.assertIsNone(self.get_document_from_index(doc))

    def test_created(self) -> None:
        doc = Document.objects.create(
            title="test",
            created=timezone.make_aware(timezone.datetime(2020, 4, 12)),
        )
        self.assertEqual(self.doc_admin.created_(doc), "2020-04-12")


class TestTagAdmin(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tag_admin = TagAdmin(model=Tag, admin_site=AdminSite())

    @patch("documents.tasks.bulk_update_documents")
    def test_parent_tags_get_added(self, mock_bulk_update):
        document = Document.objects.create(title="test")
        parent = Tag.objects.create(name="parent")
        child = Tag.objects.create(name="child")
        document.tags.add(child)

        child.tn_parent = parent
        self.tag_admin.save_model(None, child, None, change=True)
        document.refresh_from_db()
        self.assertIn(parent, document.tags.all())


class TestPaperlessAdmin(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_admin = PaperlessUserAdmin(model=User, admin_site=AdminSite())

    def test_request_is_passed_to_form(self) -> None:
        user = User.objects.create(username="test", is_superuser=False)
        non_superuser = User.objects.create(username="requestuser")
        request = types.SimpleNamespace(user=non_superuser)
        formType = self.user_admin.get_form(request)
        form = formType(data={}, instance=user)
        self.assertEqual(form.request, request)

    def test_only_superuser_can_change_superuser(self) -> None:
        superuser = User.objects.create_superuser(username="superuser", password="test")
        non_superuser = User.objects.create(username="requestuser")
        user = User.objects.create(username="test", is_superuser=False)

        data = {
            "username": "test",
            "is_superuser": True,
        }
        form = self.user_admin.form(data, instance=user)
        form.request = types.SimpleNamespace(user=non_superuser)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors.get("__all__"),
            ["Superuser status can only be changed by a superuser"],
        )

        form = self.user_admin.form(data, instance=user)
        form.request = types.SimpleNamespace(user=superuser)
        self.assertTrue(form.is_valid())
        self.assertEqual({}, form.errors)

    def test_superuser_can_only_be_modified_by_superuser(self) -> None:
        superuser = User.objects.create_superuser(username="superuser", password="test")
        user = User.objects.create(
            username="test",
            is_superuser=False,
            is_staff=True,
        )
        change_user_perm = Permission.objects.get(codename="change_user")
        user.user_permissions.add(change_user_perm)

        self.client.force_login(user)
        response = self.client.patch(
            f"/api/users/{superuser.pk}/",
            {"first_name": "Updated"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.content.decode(),
            "Superusers can only be modified by other superusers",
        )

        self.client.logout()
        self.client.force_login(superuser)
        response = self.client.patch(
            f"/api/users/{superuser.pk}/",
            {"first_name": "Updated"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        superuser.refresh_from_db()
        self.assertEqual(superuser.first_name, "Updated")
