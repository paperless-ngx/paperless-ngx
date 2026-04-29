import types

import pytest
import tantivy
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase
from pytest_mock import MockerFixture
from rest_framework import status

from documents.admin import DocumentAdmin
from documents.admin import TagAdmin
from documents.models import Document
from documents.models import Tag
from documents.search import get_backend
from documents.search import reset_backend
from documents.tests.factories import DocumentFactory
from documents.tests.factories import TagFactory
from documents.tests.factories import UserFactory
from documents.tests.utils import DirectoriesMixin
from paperless.admin import PaperlessUserAdmin


@pytest.fixture
def tag_admin() -> TagAdmin:
    return TagAdmin(model=Tag, admin_site=AdminSite())


@pytest.fixture
def user_admin() -> PaperlessUserAdmin:
    return PaperlessUserAdmin(model=User, admin_site=AdminSite())


@pytest.fixture
def superuser(db) -> User:
    return UserFactory.create(username="superuser", superuser=True)


@pytest.fixture
def staff_user(db) -> User:
    return UserFactory.create(username="staff", staff=True)


class TestDocumentAdmin(DirectoriesMixin, TestCase):
    def get_document_from_index(self, doc):
        backend = get_backend()
        searcher = backend._index.searcher()
        results = searcher.search(
            tantivy.Query.term_query(backend._schema, "id", doc.pk),
            limit=1,
        )
        if results.hits:
            return searcher.doc(results.hits[0][1]).to_dict()
        return None

    def setUp(self) -> None:
        super().setUp()
        reset_backend()
        self.doc_admin = DocumentAdmin(model=Document, admin_site=AdminSite())

    def tearDown(self) -> None:
        reset_backend()
        super().tearDown()

    def test_save_model(self) -> None:
        doc = DocumentFactory.create(title="test")

        doc.title = "new title"
        self.doc_admin.save_model(None, doc, None, None)

        self.assertEqual(self.get_document_from_index(doc)["id"], [doc.id])

    def test_delete_model(self) -> None:
        doc = DocumentFactory.create(title="test")
        get_backend().add_or_update(doc)
        self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_model(None, doc)

        self.assertIsNone(self.get_document_from_index(doc))

    def test_delete_queryset(self) -> None:
        docs = DocumentFactory.create_batch(
            2,
            title="Many documents with the same title",
        )
        for doc in docs:
            get_backend().add_or_update(doc)
            self.assertIsNotNone(self.get_document_from_index(doc))

        self.doc_admin.delete_queryset(None, Document.objects.all())

        for doc in docs:
            self.assertIsNone(self.get_document_from_index(doc))


@pytest.mark.django_db
class TestTagAdmin:
    def test_parent_tags_get_added(
        self,
        tag_admin: TagAdmin,
        mocker: MockerFixture,
    ) -> None:
        mock_bulk_update = mocker.patch(
            "documents.tasks.bulk_update_documents.apply_async",
        )
        document = DocumentFactory.create(title="test")
        parent = TagFactory.create(name="parent")
        child = TagFactory.create(name="child")
        document.tags.add(child)

        child.tn_parent = parent
        tag_admin.save_model(None, child, None, change=True)

        document.refresh_from_db()
        assert parent in document.tags.all()
        mock_bulk_update.assert_called_once()
        assert mock_bulk_update.call_args.kwargs["kwargs"] == {
            "document_ids": [document.id],
        }


@pytest.mark.django_db
class TestPaperlessAdmin:
    def test_request_is_passed_to_form(
        self,
        user_admin: PaperlessUserAdmin,
    ) -> None:
        user = UserFactory.create()
        non_superuser = UserFactory.create()
        request = types.SimpleNamespace(user=non_superuser)
        form_type = user_admin.get_form(request)
        form = form_type(data={}, instance=user)
        assert form.request == request

    def test_non_superuser_cannot_change_superuser_status(
        self,
        user_admin: PaperlessUserAdmin,
    ) -> None:
        non_superuser = UserFactory.create()
        user = UserFactory.create()

        form = user_admin.form(
            {"username": user.username, "is_superuser": True},
            instance=user,
        )
        form.request = types.SimpleNamespace(user=non_superuser)

        assert not form.is_valid()
        assert form.errors.get("__all__") == [
            "Superuser status can only be changed by a superuser",
        ]

    def test_superuser_can_change_superuser_status(
        self,
        user_admin: PaperlessUserAdmin,
        superuser: User,
    ) -> None:
        user = UserFactory.create()

        form = user_admin.form(
            {"username": user.username, "is_superuser": True},
            instance=user,
        )
        form.request = types.SimpleNamespace(user=superuser)

        assert form.is_valid()
        assert form.errors == {}

    @pytest.mark.parametrize(
        ("method", "perm_codename", "expected_message"),
        [
            pytest.param(
                "patch",
                "change_user",
                "Superusers can only be modified by other superusers",
                id="modify",
            ),
            pytest.param(
                "delete",
                "delete_user",
                "Superusers can only be deleted by other superusers",
                id="delete",
            ),
        ],
    )
    def test_non_superuser_cannot_mutate_superuser(
        self,
        client: Client,
        superuser: User,
        staff_user: User,
        method: str,
        perm_codename: str,
        expected_message: str,
    ) -> None:
        staff_user.user_permissions.add(
            Permission.objects.get(codename=perm_codename),
        )
        client.force_login(staff_user)

        response = getattr(client, method)(
            f"/api/users/{superuser.pk}/",
            {"first_name": "Updated"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.content.decode() == expected_message
        assert User.objects.filter(pk=superuser.pk).exists()

    def test_superuser_can_modify_superuser(
        self,
        client: Client,
        superuser: User,
    ) -> None:
        client.force_login(superuser)
        response = client.patch(
            f"/api/users/{superuser.pk}/",
            {"first_name": "Updated"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        superuser.refresh_from_db()
        assert superuser.first_name == "Updated"

    def test_superuser_can_delete_superuser(
        self,
        client: Client,
        superuser: User,
    ) -> None:
        target = UserFactory.create(superuser=True)
        client.force_login(superuser)

        response = client.delete(f"/api/users/{target.pk}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(pk=target.pk).exists()
