import json

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.models import Folder
from documents.models import get_default_folder
from documents.tests.utils import DirectoriesMixin


class TestApiFolders(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/folders/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_create_folder(self) -> None:
        """
        WHEN:
            - API request to create a folder
        THEN:
            - Folder is created
        """
        response = self.client.post(
            self.ENDPOINT,
            data={"name": "Personal"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Folder.objects.filter(name="Personal").count(), 1)

    def test_create_subfolder(self) -> None:
        parent = Folder.objects.create(name="Parent")
        response = self.client.post(
            self.ENDPOINT,
            data={"name": "Child", "parent": parent.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        child = Folder.objects.get(name="Child")
        self.assertEqual(child.parent_id, parent.id)
        self.assertEqual(child.full_path, "Parent/Child")

    def test_duplicate_name_in_same_parent_rejected(self) -> None:
        parent = Folder.objects.create(name="Parent")
        Folder.objects.create(name="Child", parent=parent)
        response = self.client.post(
            self.ENDPOINT,
            data={"name": "Child", "parent": parent.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_name_different_parent_allowed(self) -> None:
        p1 = Folder.objects.create(name="P1")
        p2 = Folder.objects.create(name="P2")
        Folder.objects.create(name="Shared", parent=p1)
        response = self.client.post(
            self.ENDPOINT,
            data={"name": "Shared", "parent": p2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_returns_tree_for_roots(self) -> None:
        root = Folder.objects.create(name="Root")
        Folder.objects.create(name="Sub", parent=root)

        response = self.client.get(f"{self.ENDPOINT}?is_root=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        # Only root folders are returned (the migration-created default folder
        # may also be present, so locate our "Root" entry explicitly).
        names = [r["name"] for r in results]
        self.assertIn("Root", names)
        root_result = next(r for r in results if r["name"] == "Root")
        self.assertEqual(len(root_result["children"]), 1)
        self.assertEqual(root_result["children"][0]["name"], "Sub")

    def test_rename_folder(self) -> None:
        folder = Folder.objects.create(name="OldName")
        response = self.client.patch(
            f"{self.ENDPOINT}{folder.id}/",
            data={"name": "NewName"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        folder.refresh_from_db()
        self.assertEqual(folder.name, "NewName")

    def test_move_folder_into_another(self) -> None:
        a = Folder.objects.create(name="A")
        b = Folder.objects.create(name="B")
        response = self.client.patch(
            f"{self.ENDPOINT}{b.id}/",
            data={"parent": a.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        b.refresh_from_db()
        self.assertEqual(b.parent_id, a.id)

    def test_cannot_create_cycle(self) -> None:
        a = Folder.objects.create(name="A")
        b = Folder.objects.create(name="B", parent=a)
        # Try to make A a child of B (its own descendant)
        response = self.client.patch(
            f"{self.ENDPOINT}{a.id}/",
            data={"parent": b.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_folder_reassigns_documents(self) -> None:
        """
        GIVEN:
            - A folder with documents and a subfolder with documents
        WHEN:
            - The folder is deleted
        THEN:
            - Documents are reassigned (never left without a folder) and the
              subtree is removed
        """
        parent = Folder.objects.create(name="Parent")
        sub = Folder.objects.create(name="Sub", parent=parent)
        doc1 = Document.objects.create(checksum="A", title="A", folder=parent)
        doc2 = Document.objects.create(checksum="B", title="B", folder=sub)

        response = self.client.delete(f"{self.ENDPOINT}{parent.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Folder.objects.filter(pk=parent.id).exists())
        self.assertFalse(Folder.objects.filter(pk=sub.id).exists())

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        # Reassigned to the default folder (parent had no parent of its own)
        self.assertIsNotNone(doc1.folder)
        self.assertIsNotNone(doc2.folder)
        self.assertTrue(doc1.folder.is_default)
        self.assertTrue(doc2.folder.is_default)

    def test_delete_subfolder_reassigns_to_parent(self) -> None:
        parent = Folder.objects.create(name="Parent")
        sub = Folder.objects.create(name="Sub", parent=parent)
        doc = Document.objects.create(checksum="A", title="A", folder=sub)

        response = self.client.delete(f"{self.ENDPOINT}{sub.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        doc.refresh_from_db()
        self.assertEqual(doc.folder_id, parent.id)

    def test_cannot_delete_default_folder(self) -> None:
        default = get_default_folder()
        response = self.client.delete(f"{self.ENDPOINT}{default.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Folder.objects.filter(pk=default.id).exists())

    def test_document_count(self) -> None:
        folder = Folder.objects.create(name="Counted")
        Document.objects.create(checksum="A", title="A", folder=folder)
        Document.objects.create(checksum="B", title="B", folder=folder)
        response = self.client.get(f"{self.ENDPOINT}{folder.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["document_count"], 2)


class TestApiFolderPermissions(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/folders/"

    def setUp(self) -> None:
        super().setUp()
        self.user1 = User.objects.create_user(username="user1", password="pw")
        self.user2 = User.objects.create_user(username="user2", password="pw")
        for codename in [
            "view_folder",
            "add_folder",
            "change_folder",
            "delete_folder",
        ]:
            perm = Permission.objects.get(codename=codename)
            self.user1.user_permissions.add(perm)
            self.user2.user_permissions.add(perm)

    def test_user_cannot_see_other_users_folders(self) -> None:
        owned = Folder.objects.create(name="Private", owner=self.user2)
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [f["name"] for f in response.data["results"]]
        self.assertNotIn("Private", names)
        # but user2 can see it
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(self.ENDPOINT)
        names = [f["name"] for f in response.data["results"]]
        self.assertIn("Private", names)
        self.assertEqual(owned.owner, self.user2)

    def test_unowned_folder_visible_to_all(self) -> None:
        Folder.objects.create(name="Shared")
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.ENDPOINT)
        names = [f["name"] for f in response.data["results"]]
        self.assertIn("Shared", names)


class TestApiFolderBulkMove(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        self.f1 = Folder.objects.create(name="f1")
        self.f2 = Folder.objects.create(name="f2")
        self.doc1 = Document.objects.create(checksum="A", title="A", folder=self.f1)
        self.doc2 = Document.objects.create(checksum="B", title="B", folder=self.f1)

    def test_bulk_set_folder(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id, self.doc2.id],
                    "method": "set_folder",
                    "parameters": {"folder": self.f2.id},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Document.objects.filter(folder=self.f2).count(), 2)

    def test_bulk_set_folder_invalid(self) -> None:
        response = self.client.post(
            "/api/documents/bulk_edit/",
            json.dumps(
                {
                    "documents": [self.doc1.id],
                    "method": "set_folder",
                    "parameters": {"folder": 99999},
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_folder_filter(self) -> None:
        response = self.client.get(f"/api/documents/?folder__id={self.f1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
