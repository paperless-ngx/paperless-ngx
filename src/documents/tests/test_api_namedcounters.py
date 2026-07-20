from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.models import NamedCounter
from documents.tests.utils import DirectoriesMixin


class TestNamedCounterApi(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/named_counters/"

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username="admin")
        self.client.force_authenticate(self.user)

    def test_list_empty(self) -> None:
        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)

    def test_create(self) -> None:
        resp = self.client.post(
            self.ENDPOINT,
            data={"name": "Binder A"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Binder A")
        self.assertEqual(NamedCounter.objects.count(), 1)

    def test_create_duplicate_name_fails(self) -> None:
        NamedCounter.objects.create(name="Binder A")
        resp = self.client.post(
            self.ENDPOINT,
            data={"name": "Binder A"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve(self) -> None:
        counter = NamedCounter.objects.create(name="Binder A")
        resp = self.client.get(f"{self.ENDPOINT}{counter.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Binder A")

    def test_update(self) -> None:
        counter = NamedCounter.objects.create(name="Old Name")
        resp = self.client.patch(
            f"{self.ENDPOINT}{counter.pk}/",
            data={"name": "New Name"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        counter.refresh_from_db()
        self.assertEqual(counter.name, "New Name")

    def test_delete(self) -> None:
        counter = NamedCounter.objects.create(name="To Delete")
        resp = self.client.delete(f"{self.ENDPOINT}{counter.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(NamedCounter.objects.count(), 0)

    def test_delete_sets_null_on_documents(self) -> None:
        """
        GIVEN:
            - Counter with an assigned document
        WHEN:
            - Counter is deleted
        THEN:
            - Document's named_counter becomes NULL (SET_NULL behaviour)
        """
        counter = NamedCounter.objects.create(name="Binder A")
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="content",
            checksum="abc",
            archive_serial_number=1,
            named_counter=counter,
        )
        self.client.delete(f"{self.ENDPOINT}{counter.pk}/")
        doc.refresh_from_db()
        self.assertIsNone(doc.named_counter)

    def test_document_count_annotation(self) -> None:
        counter = NamedCounter.objects.create(name="Binder A")
        Document.objects.create(
            title="doc1",
            mime_type="application/pdf",
            content="content",
            checksum="c1",
            archive_serial_number=1,
            named_counter=counter,
        )
        Document.objects.create(
            title="doc2",
            mime_type="application/pdf",
            content="content2",
            checksum="c2",
            archive_serial_number=2,
            named_counter=counter,
        )
        resp = self.client.get(f"{self.ENDPOINT}{counter.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["document_count"], 2)

    def test_unauthenticated_returns_401(self) -> None:
        self.client.logout()
        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_permission_cannot_create(self) -> None:
        restricted_user = User.objects.create_user(username="restricted")
        self.client.force_authenticate(restricted_user)
        resp = self.client.post(
            self.ENDPOINT,
            data={"name": "New Counter"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_add_permission_can_create(self) -> None:
        limited_user = User.objects.create_user(username="limited")
        limited_user.user_permissions.add(*Permission.objects.all())
        limited_user.save()
        self.client.force_authenticate(limited_user)
        resp = self.client.post(
            self.ENDPOINT,
            data={"name": "Allowed Counter"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
