from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import override_settings
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from documents.permissions import permitted_document_ids
from documents.tests.factories import DocumentFactory


def assert_visible_document_ids(actual_ids, *, expected_visible, expected_hidden):
    actual_ids = set(actual_ids)
    expected_visible = set(expected_visible)
    assert actual_ids == expected_visible, (
        f"visible set mismatch: missing={expected_visible - actual_ids}, "
        f"unexpected={actual_ids - expected_visible}"
    )
    for doc_id in expected_hidden:
        assert doc_id not in actual_ids, (
            f"document {doc_id} leaked but should be hidden"
        )


@pytest.mark.django_db
class TestPermittedDocumentIdsSecurity:
    def test_owner_sees_own_document(self):
        user = User.objects.create_user(username="alice")
        stranger = User.objects.create_user(username="mallory")
        owned = DocumentFactory(owner=user)
        strangers_doc = DocumentFactory(owner=stranger)

        visible = permitted_document_ids(user)

        assert_visible_document_ids(
            visible,
            expected_visible=[owned.pk],
            expected_hidden=[strangers_doc.pk],
        )

    def test_unowned_document_visible_to_everyone(self):
        user = User.objects.create_user(username="alice")
        unowned = DocumentFactory(owner=None)

        assert_visible_document_ids(
            permitted_document_ids(user),
            expected_visible=[unowned.pk],
            expected_hidden=[],
        )

    def test_explicit_user_permission_grants_visibility(self):
        grantee = User.objects.create_user(username="alice")
        stranger = User.objects.create_user(username="mallory")
        owner = User.objects.create_user(username="owner")
        shared = DocumentFactory(owner=owner)
        not_shared = DocumentFactory(owner=owner)
        assign_perm("view_document", grantee, shared)

        assert_visible_document_ids(
            permitted_document_ids(grantee),
            expected_visible=[shared.pk],
            expected_hidden=[not_shared.pk],
        )
        assert_visible_document_ids(
            permitted_document_ids(stranger),
            expected_visible=[],
            expected_hidden=[shared.pk, not_shared.pk],
        )

    def test_explicit_group_permission_grants_visibility_to_members_only(self):
        owner = User.objects.create_user(username="owner")
        member = User.objects.create_user(username="member")
        non_member = User.objects.create_user(username="non_member")
        group = Group.objects.create(name="finance")
        member.groups.add(group)
        shared = DocumentFactory(owner=owner)
        assign_perm("view_document", group, shared)

        assert_visible_document_ids(
            permitted_document_ids(member),
            expected_visible=[shared.pk],
            expected_hidden=[],
        )
        assert_visible_document_ids(
            permitted_document_ids(non_member),
            expected_visible=[],
            expected_hidden=[shared.pk],
        )

    def test_soft_deleted_document_excluded_by_default(self):
        owner = User.objects.create_user(username="owner")
        doc = DocumentFactory(owner=owner)
        doc.delete()  # soft delete
        doc.refresh_from_db()
        assert doc.deleted_at is not None, (
            "document should be soft-deleted, not hard-deleted, for this "
            "test to actually validate the deleted_at filtering behavior"
        )

        assert_visible_document_ids(
            permitted_document_ids(owner),
            expected_visible=[],
            expected_hidden=[doc.pk],
        )

    def test_superuser_sees_everything_including_no_perm_documents(self):
        superuser = User.objects.create_superuser(username="root")
        owner = User.objects.create_user(username="owner")
        doc = DocumentFactory(owner=owner)

        assert_visible_document_ids(
            permitted_document_ids(superuser),
            expected_visible=[doc.pk],
            expected_hidden=[],
        )

    def test_anonymous_user_sees_only_unowned_documents(self):
        owner = User.objects.create_user(username="owner")
        owned = DocumentFactory(owner=owner)
        unowned = DocumentFactory(owner=None)

        assert_visible_document_ids(
            permitted_document_ids(AnonymousUser()),
            expected_visible=[unowned.pk],
            expected_hidden=[owned.pk],
        )


@pytest.mark.django_db
class TestPermittedDocumentIdsIncludeDeleted:
    def test_include_deleted_true_reveals_soft_deleted_owned_document(self):
        owner = User.objects.create_user(username="owner")
        doc = DocumentFactory(owner=owner)
        doc.delete()

        assert_visible_document_ids(
            permitted_document_ids(owner, include_deleted=True),
            expected_visible=[doc.pk],
            expected_hidden=[],
        )

    def test_include_deleted_true_still_respects_permission_boundary(self):
        owner = User.objects.create_user(username="owner")
        stranger = User.objects.create_user(username="mallory")
        doc = DocumentFactory(owner=owner)
        doc.delete()

        assert_visible_document_ids(
            permitted_document_ids(stranger, include_deleted=True),
            expected_visible=[],
            expected_hidden=[doc.pk],
        )


@pytest.mark.django_db
class TestAiChatAllDocumentsPermissionBoundary:
    """
    Regression test pinning the "ask across all documents" AI chat behavior
    (ChatStreamingView.post, no document_id) to the same owner/permission
    boundary enforced by permitted_document_ids(). This call site was
    migrated from get_objects_for_user_owner_aware() to
    permitted_document_ids() in Task 5; this test must stay green across
    that swap.
    """

    ENDPOINT = "/api/documents/chat/"

    @override_settings(AI_ENABLED=True)
    @patch("documents.views.stream_chat_with_documents")
    def test_chat_all_documents_excludes_unshared_document(self, mock_stream_chat):
        mock_stream_chat.return_value = iter([b"data"])

        owner = User.objects.create_user(username="owner")
        asker = User.objects.create_user(username="asker")
        asker.user_permissions.add(
            *Permission.objects.filter(codename="view_document"),
        )
        shared = DocumentFactory(owner=owner)
        not_shared = DocumentFactory(owner=owner)
        assign_perm("view_document", asker, shared)

        client = APIClient()
        client.force_authenticate(user=asker)
        response = client.post(
            self.ENDPOINT,
            data={"q": "question"},
            format="json",
        )

        assert response.status_code == 200
        mock_stream_chat.assert_called_once()
        _, kwargs = mock_stream_chat.call_args
        visible_ids = {doc.pk for doc in kwargs["documents"]}
        assert shared.pk in visible_ids
        assert not_shared.pk not in visible_ids
