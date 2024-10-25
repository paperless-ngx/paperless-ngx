import datetime
import json
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


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

    def test_correspondent_last_correspondence(self):
        """
        GIVEN:
            - Correspondent with documents
        WHEN:
            - API is called
        THEN:
            - Last correspondence date is returned only if requested for list, and for detail
        """

        Document.objects.create(
            mime_type="application/pdf",
            correspondent=self.c1,
            created=timezone.make_aware(datetime.datetime(2022, 1, 1)),
            checksum="123",
        )
        Document.objects.create(
            mime_type="application/pdf",
            correspondent=self.c1,
            created=timezone.make_aware(datetime.datetime(2022, 1, 2)),
            checksum="456",
        )

        # Only if requested for list
        response = self.client.get(
            "/api/correspondents/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertNotIn("last_correspondence", results[0])

        response = self.client.get(
            "/api/correspondents/?last_correspondence=true",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertIn(
            "2022-01-02",
            results[0]["last_correspondence"],
        )

        # Included in detail by default
        response = self.client.get(
            f"/api/correspondents/{self.c1.id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "2022-01-02",
            response.data["last_correspondence"],
        )


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
                    "/{added_month_name_short}/{added_day}/{asn}"
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

    @mock.patch("documents.bulk_edit.bulk_update_documents.delay")
    def test_api_delete_storage_path(self, bulk_update_mock):
        """
        GIVEN:
            - API request to delete a storage
        WHEN:
            - API is called
        THEN:
            - Documents using the storage path are updated
        """
        document = Document.objects.create(
            mime_type="application/pdf",
            storage_path=self.sp1,
        )
        response = self.client.delete(
            f"{self.ENDPOINT}{self.sp1.pk}/",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # sp with no documents
        sp2 = StoragePath.objects.create(name="sp2", path="Something2/{checksum}")
        response = self.client.delete(
            f"{self.ENDPOINT}{sp2.pk}/",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # only called once
        bulk_update_mock.assert_called_once_with([document.pk])

    def test_test_storage_path(self):
        """
        GIVEN:
            - API request to test a storage path
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - Correct response data
        """
        document = Document.objects.create(
            mime_type="application/pdf",
            storage_path=self.sp1,
            title="Something",
            checksum="123",
        )
        response = self.client.post(
            f"{self.ENDPOINT}test/",
            json.dumps(
                {
                    "document": document.id,
                    "path": "path/{{ title }}",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, "path/Something")


class TestBulkEditObjects(APITestCase):
    # See test_api_permissions.py for bulk tests on permissions
    def setUp(self):
        super().setUp()

        self.temp_admin = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.temp_admin)

        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.c1 = Correspondent.objects.create(name="c1")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.sp1 = StoragePath.objects.create(name="sp1")
        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")

    def test_bulk_objects_delete(self):
        """
        GIVEN:
            - Existing objects
        WHEN:
            - bulk_edit_objects API endpoint is called with delete operation
        THEN:
            - Objects are deleted
        """
        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Tag.objects.count(), 0)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.c1.id],
                    "object_type": "correspondents",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Correspondent.objects.count(), 0)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.dt1.id],
                    "object_type": "document_types",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(DocumentType.objects.count(), 0)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.sp1.id],
                    "object_type": "storage_paths",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(StoragePath.objects.count(), 0)

    def test_bulk_edit_object_permissions_insufficient_global_perms(self):
        """
        GIVEN:
            - Existing objects, user does not have global delete permissions
        WHEN:
            - bulk_edit_objects API endpoint is called with delete operation
        THEN:
            - User is not able to delete objects
        """
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")

    def test_bulk_edit_object_permissions_sufficient_global_perms(self):
        """
        GIVEN:
            - Existing objects, user does have global delete permissions
        WHEN:
            - bulk_edit_objects API endpoint is called with delete operation
        THEN:
            - User is able to delete objects
        """
        self.user1.user_permissions.add(
            *Permission.objects.filter(codename="delete_tag"),
        )
        self.user1.save()
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bulk_edit_object_permissions_insufficient_object_perms(self):
        """
        GIVEN:
            - Objects owned by user other than logged in user
        WHEN:
            - bulk_edit_objects API endpoint is called with delete operation
        THEN:
            - User is not able to delete objects
        """
        self.t2.owner = User.objects.get(username="temp_admin")
        self.t2.save()

        self.user1.user_permissions.add(
            *Permission.objects.filter(codename="delete_tag"),
        )
        self.user1.save()
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            "/api/bulk_edit_objects/",
            json.dumps(
                {
                    "objects": [self.t1.id, self.t2.id],
                    "object_type": "tags",
                    "operation": "delete",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content, b"Insufficient permissions")
