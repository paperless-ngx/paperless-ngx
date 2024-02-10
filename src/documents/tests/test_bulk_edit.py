from unittest import mock

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import TestCase
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_groups_with_perms
from guardian.shortcuts import get_users_with_perms

from documents.bulk_edit import set_permissions
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestBulkEditPermissions(DirectoriesMixin, TestCase):
    def setUp(self):
        super().setUp()

        self.doc1 = Document.objects.create(checksum="A", title="A")
        self.doc2 = Document.objects.create(checksum="B", title="B")
        self.doc3 = Document.objects.create(checksum="C", title="C")

        self.owner = User.objects.create(username="test_owner")
        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.group1 = Group.objects.create(name="group1")
        self.group2 = Group.objects.create(name="group2")

    @mock.patch("documents.tasks.bulk_update_documents.delay")
    def test_set_permissions(self, m):
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]

        assign_perm("view_document", self.group1, self.doc1)

        permissions = {
            "view": {
                "users": [self.user1.id, self.user2.id],
                "groups": [self.group2.id],
            },
            "change": {
                "users": [self.user1.id],
                "groups": [self.group2.id],
            },
        }

        set_permissions(
            doc_ids,
            set_permissions=permissions,
            owner=self.owner,
            merge=False,
        )
        m.assert_called_once()

        self.assertEqual(Document.objects.filter(owner=self.owner).count(), 3)
        self.assertEqual(Document.objects.filter(id__in=doc_ids).count(), 3)

        users_with_perms = get_users_with_perms(
            self.doc1,
        )
        self.assertEqual(users_with_perms.count(), 2)

        # group1 should be replaced by group2
        groups_with_perms = get_groups_with_perms(
            self.doc1,
        )
        self.assertEqual(groups_with_perms.count(), 1)

    @mock.patch("documents.tasks.bulk_update_documents.delay")
    def test_set_permissions_merge(self, m):
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]

        self.doc1.owner = self.user1
        self.doc1.save()

        assign_perm("view_document", self.user1, self.doc1)
        assign_perm("view_document", self.group1, self.doc1)

        permissions = {
            "view": {
                "users": [self.user2.id],
                "groups": [self.group2.id],
            },
            "change": {
                "users": [self.user2.id],
                "groups": [self.group2.id],
            },
        }
        set_permissions(
            doc_ids,
            set_permissions=permissions,
            owner=self.owner,
            merge=True,
        )
        m.assert_called_once()

        # when merge is true owner doesn't get replaced if its not empty
        self.assertEqual(Document.objects.filter(owner=self.owner).count(), 2)
        self.assertEqual(Document.objects.filter(id__in=doc_ids).count(), 3)

        # merge of user1 which was pre-existing and user2
        users_with_perms = get_users_with_perms(
            self.doc1,
        )
        self.assertEqual(users_with_perms.count(), 2)

        # group1 should be merged by group2
        groups_with_perms = get_groups_with_perms(
            self.doc1,
        )
        self.assertEqual(groups_with_perms.count(), 2)
