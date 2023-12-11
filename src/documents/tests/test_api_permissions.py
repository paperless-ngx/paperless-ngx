import json

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_perms
from guardian.shortcuts import get_users_with_perms
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.models import ConsumptionTemplate
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


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
        self.cf1 = CustomField.objects.create(name="Custom Field 1", data_type="string")
        self.cf2 = CustomField.objects.create(
            name="Custom Field 2",
            data_type="integer",
        )

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
        self.ct.assign_custom_fields.add(self.cf1.pk)
        self.ct.assign_custom_fields.add(self.cf2.pk)
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
        self.assertEqual(ConsumptionTemplate.objects.count(), 1)

    def test_api_create_consumption_template_empty_fields(self):
        """
        GIVEN:
            - API request to create a consumption template
            - Path or filename filter or assign title are empty string
        WHEN:
            - API is called
        THEN:
            - Template is created but filter or title assignment is not set if ""
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*test*",
                    "filter_path": "",
                    "assign_title": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct = ConsumptionTemplate.objects.get(name="Template 2")
        self.assertEqual(ct.filter_filename, "*test*")
        self.assertIsNone(ct.filter_path)
        self.assertIsNone(ct.assign_title)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 3",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "",
                    "filter_path": "*/test/*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct2 = ConsumptionTemplate.objects.get(name="Template 3")
        self.assertEqual(ct2.filter_path, "*/test/*")
        self.assertIsNone(ct2.filter_filename)

    def test_api_create_consumption_template_with_mailrule(self):
        """
        GIVEN:
            - API request to create a consumption template with a mail rule but no MailFetch source
        WHEN:
            - API is called
        THEN:
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
            filter_attachment_filename_include="file.pdf",
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
