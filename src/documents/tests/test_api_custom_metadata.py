from datetime import timedelta
from unittest import mock
from unittest.mock import MagicMock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomMetadata
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestCustomMetadata(DirectoriesMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        return super().setUp()

    @staticmethod
    def create_json_no_date(metadata: CustomMetadata):
        """
        Small helper to remove the created datatime from the JSON
        It doesn't matter to verify
        """
        expected = metadata.to_json()
        del expected["created"]
        return expected

    def test_get_existing_custom_metadata(self):
        """
        GIVEN:
            - A document with 2 different metadata attached to it
        WHEN:
            - API request for document custom metadata is made
        THEN:
            - Both associated values are returned
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom metadata on it!  Neat",
        )

        metadata1 = CustomMetadata.objects.create(
            data_type=CustomMetadata.DataType.STRING,
            name="Invoice Number",
            data="#123456",
            document=doc,
            user=self.user,
        )

        metadata2 = CustomMetadata.objects.create(
            data_type=CustomMetadata.DataType.URL,
            name="October 20th, 2023 On This Day",
            data="https://en.wikipedia.org/wiki/Pope_Pius_XII",
            document=doc,
            user=self.user,
        )

        all_metadata = [metadata1, metadata2]

        response = self.client.get(
            f"/api/documents/{doc.pk}/custom_metadata/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertEqual(len(resp_data), 2)

        for idx, resp_data in enumerate(reversed(resp_data)):
            del resp_data["created"]

            self.assertDictEqual(
                resp_data,
                self.create_json_no_date(all_metadata[idx]),
            )

    def test_create_custom_metadata(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - API request is made to add 2 custom metadata fields
        THEN:
            - metadata objects are created and associated with document
            - Document modified time is updated
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom_metadata added",
            created=timezone.now() - timedelta(days=1),
        )
        # set to yesterday
        doc.modified = timezone.now() - timedelta(days=1)
        self.assertEqual(doc.modified.day, (timezone.now() - timedelta(days=1)).day)

        resp = self.client.post(
            f"/api/documents/{doc.pk}/custom_metadata/",
            data={"type": "string", "name": "Custom Field 1", "data": "Custom Data 1"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/documents/{doc.pk}/custom_metadata/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resp_data = response.json()

        self.assertEqual(len(resp_data), 1)

        resp_data = resp_data[0]

        self.assertEqual(resp_data["data"], "Custom Data 1")

        doc = Document.objects.get(pk=doc.pk)
        # modified was updated to today
        self.assertEqual(doc.modified.day, timezone.now().day)

    def test_custom_metadata_view_add_delete_permissions_aware(self):
        """
        GIVEN:
            - Existing document owned by user2 but with granted view perms for user1
        WHEN:
            - API request is made by user1 to add a custom metadata
        THEN:
            - custom metadata is not created
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.all())
        user1.save()

        user2 = User.objects.create_user(username="test2")
        user2.save()

        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom_metadata added",
        )
        doc.owner = user2
        doc.save()

        self.client.force_authenticate(user1)

        resp = self.client.get(
            f"/api/documents/{doc.pk}/custom_metadata/",
            format="json",
        )
        self.assertEqual(
            resp.content,
            b"Insufficient permissions to view custom metadata",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        assign_perm("view_document", user1, doc)

        resp = self.client.post(
            f"/api/documents/{doc.pk}/custom_metadata/",
            data={"type": "string", "name": "Custom Field 1", "data": "Custom Data 1"},
        )
        self.assertEqual(
            resp.content,
            b"Insufficient permissions to create custom metadata",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        metadata = CustomMetadata.objects.create(
            data_type=CustomMetadata.DataType.STRING,
            name="Invoice Number",
            data="#123456",
            document=doc,
            user=self.user,
        )

        response = self.client.delete(
            f"/api/documents/{doc.pk}/custom_metadata/?id={metadata.pk}",
            format="json",
        )

        self.assertEqual(
            response.content,
            b"Insufficient permissions to delete custom metadata",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_custom_metadata(self):
        """
        GIVEN:
            - Existing document, existing custom metadata
        WHEN:
            - API request is made to delete a custom metadata
        THEN:
            - custom metadata is deleted, document modified is updated
        """
        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom metadata!",
            created=timezone.now() - timedelta(days=1),
        )
        # set to yesterday
        doc.modified = timezone.now() - timedelta(days=1)
        self.assertEqual(doc.modified.day, (timezone.now() - timedelta(days=1)).day)

        metadata = CustomMetadata.objects.create(
            data_type=CustomMetadata.DataType.DATE,
            name="Invoice Number",
            data="2023-10-20",
            document=doc,
            user=self.user,
        )

        response = self.client.delete(
            f"/api/documents/{doc.pk}/custom_metadata/?id={metadata.pk}",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(CustomMetadata.objects.all()), 0)
        doc = Document.objects.get(pk=doc.pk)
        # modified was updated to today
        self.assertEqual(doc.modified.day, timezone.now().day)

    def test_get_custom_metadata_no_doc(self):
        """
        GIVEN:
            - A request to get custom metadata from a non-existent document
        WHEN:
            - API request for document custom metadata is made
        THEN:
            - HTTP status.HTTP_404_NOT_FOUND is returned
        """
        response = self.client.get(
            "/api/documents/500/custom_metadata/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch("documents.views.CustomMetadata.to_json")
    def test_get_custom_metadata_failure(self, mocked_to_json: MagicMock):
        mocked_to_json.side_effect = Exception("this failed somehow")

        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom metadata on it!  Neat",
        )

        _ = CustomMetadata.objects.create(
            data_type=CustomMetadata.DataType.STRING,
            name="Invoice Number",
            data="#123456",
            document=doc,
            user=self.user,
        )

        response = self.client.get(
            f"/api/documents/{doc.pk}/custom_metadata/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @mock.patch("documents.views.CustomMetadata.from_json")
    def test_add_custom_metadata_failure(self, mocked_from_json: MagicMock):
        mocked_from_json.side_effect = Exception("this failed somehow else")

        doc = Document.objects.create(
            title="test",
            mime_type="application/pdf",
            content="this is a document which will have custom metadata on it!  Neat",
        )

        response = self.client.post(
            f"/api/documents/{doc.pk}/custom_metadata/",
            data={"type": "string", "name": "Custom Field 1", "data": "Custom Data 1"},
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
