from __future__ import annotations

from http import HTTPStatus
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
from documents.serialisers import _get_viewable_duplicates
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
    permitted_document_ids(); this test must stay green across that swap.
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

        assert response.status_code == HTTPStatus.OK
        mock_stream_chat.assert_called_once()
        _, kwargs = mock_stream_chat.call_args
        visible_ids = {doc.pk for doc in kwargs["documents"]}
        assert shared.pk in visible_ids
        assert not_shared.pk not in visible_ids


@pytest.mark.django_db
class TestDuplicateDocumentsPermissionBoundary:
    def test_get_viewable_duplicates_includes_soft_deleted_but_respects_perms(self):
        owner = User.objects.create_user(username="owner")
        stranger = User.objects.create_user(username="mallory")
        original = DocumentFactory(owner=owner, checksum="dupe-checksum")
        dup_visible = DocumentFactory(owner=owner, checksum="dupe-checksum")
        dup_hidden = DocumentFactory(owner=owner, checksum="dupe-checksum")
        dup_hidden.delete()  # soft delete, should still be found (include_deleted=True)
        assign_perm("view_document", stranger, dup_visible)

        result_owner = _get_viewable_duplicates(original, owner)
        assert {d.pk for d in result_owner} == {dup_visible.pk, dup_hidden.pk}

        result_stranger = _get_viewable_duplicates(original, stranger)
        assert {d.pk for d in result_stranger} == {dup_visible.pk}


@pytest.mark.django_db
class TestPermittedDocumentIdsArbitraryPermission:
    def test_change_document_permission_is_distinct_from_view(self):
        owner = User.objects.create_user(username="owner")
        viewer_only = User.objects.create_user(username="viewer")
        editor = User.objects.create_user(username="editor")
        doc = DocumentFactory(owner=owner)
        assign_perm("view_document", viewer_only, doc)
        assign_perm("change_document", editor, doc)
        assign_perm("view_document", editor, doc)

        assert_visible_document_ids(
            permitted_document_ids(editor, perm="change_document"),
            expected_visible=[doc.pk],
            expected_hidden=[],
        )
        assert_visible_document_ids(
            permitted_document_ids(viewer_only, perm="change_document"),
            expected_visible=[],
            expected_hidden=[doc.pk],
        )

    def test_qualified_permission_string_is_normalized_to_codename(self):
        owner = User.objects.create_user(username="owner")
        editor = User.objects.create_user(username="editor")
        doc = DocumentFactory(owner=owner)
        assign_perm("change_document", editor, doc)

        assert_visible_document_ids(
            permitted_document_ids(editor, perm="documents.change_document"),
            expected_visible=[doc.pk],
            expected_hidden=[],
        )

    def test_delete_permission_with_include_deleted_for_trash_restore(self):
        owner = User.objects.create_user(username="owner")
        stranger = User.objects.create_user(username="mallory")
        view_only = User.objects.create_user(username="viewer")
        doc = DocumentFactory(owner=owner)
        assign_perm("view_document", view_only, doc)
        doc.delete()

        assert_visible_document_ids(
            permitted_document_ids(owner, perm="delete_document", include_deleted=True),
            expected_visible=[doc.pk],
            expected_hidden=[],
        )
        assert_visible_document_ids(
            permitted_document_ids(
                stranger,
                perm="delete_document",
                include_deleted=True,
            ),
            expected_visible=[],
            expected_hidden=[doc.pk],
        )
        assert_visible_document_ids(
            permitted_document_ids(
                view_only,
                perm="delete_document",
                include_deleted=True,
            ),
            expected_visible=[],
            expected_hidden=[doc.pk],
        )


@pytest.mark.django_db
class TestEmailDocumentPermissionBoundary:
    def test_email_action_rejects_document_without_view_permission(
        self,
        rest_api_client,
    ):
        owner = User.objects.create_user(username="owner")
        requester = User.objects.create_user(username="requester")
        rest_api_client.force_authenticate(user=requester)
        hidden = DocumentFactory(owner=owner)

        response = rest_api_client.post(
            "/api/documents/email/",
            {
                "documents": [hidden.pk],
                "addresses": "someone@example.com",
                "subject": "test",
                "message": "test",
            },
            format="json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
class TestBulkEditChangePermissionBoundary:
    def test_bulk_edit_rejects_mixed_batch_when_any_document_lacks_change_permission(
        self,
        rest_api_client,
    ):
        # A bulk-edit request containing both a document the requester CAN
        # change and one they CANNOT should be rejected as a whole: the
        # permitted document must not be partially applied just because it
        # was bundled with a forbidden one, proving the endpoint checks
        # every document in the batch rather than only the first/last.
        owner = User.objects.create_user(username="owner")
        requester = User.objects.create_user(username="requester")
        # grant the global change_document permission so the object-level
        # check (not the global has_perm check) is what's under test
        requester.user_permissions.add(
            Permission.objects.get(codename="change_document"),
        )
        rest_api_client.force_authenticate(user=requester)
        changeable = DocumentFactory(owner=owner)
        assign_perm("view_document", requester, changeable)
        assign_perm("change_document", requester, changeable)  # fully permitted
        target = DocumentFactory(owner=owner)
        assign_perm("view_document", requester, target)  # view only, NOT change

        response = rest_api_client.post(
            "/api/documents/bulk_edit/",
            {
                "documents": [changeable.pk, target.pk],
                "method": "modify_tags",
                "parameters": {"add_tags": [], "remove_tags": []},
            },
            format="json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
class TestBulkDownloadPermissionChecksRootDocument:
    def test_permission_checked_on_root_not_on_version(
        self,
        rest_api_client,
        paperless_dirs,
        _media_settings,
    ):
        owner = User.objects.create_user(username="owner")
        requester = User.objects.create_user(username="requester")
        rest_api_client.force_authenticate(user=requester)
        root = DocumentFactory(owner=owner)
        # a version of root that the requester has NOT been individually granted
        version = DocumentFactory(owner=owner, root_document=root, version_index=1)
        version.source_path.write_bytes(b"%PDF-1.4 test")
        assign_perm("view_document", requester, root)  # granted on ROOT only

        response = rest_api_client.post(
            "/api/documents/bulk_download/",
            {"documents": [version.pk]},
            format="json",
        )
        assert (
            response.status_code == HTTPStatus.OK
        )  # visible because root is permitted

        stranger = User.objects.create_user(username="mallory")
        rest_api_client.force_authenticate(user=stranger)
        response = rest_api_client.post(
            "/api/documents/bulk_download/",
            {"documents": [version.pk]},
            format="json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
class TestTrashRestorePermissionBoundary:
    def test_restore_rejects_document_without_delete_permission(
        self,
        rest_api_client,
    ):
        owner = User.objects.create_user(username="owner")
        requester = User.objects.create_user(username="requester")
        rest_api_client.force_authenticate(user=requester)
        doc = DocumentFactory(owner=owner)
        assign_perm("view_document", requester, doc)  # view only, NOT delete
        doc.delete()

        response = rest_api_client.post(
            "/api/trash/",
            {"documents": [doc.pk], "action": "restore"},
            format="json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_restore_allows_document_with_explicit_delete_permission(
        self,
        rest_api_client,
    ):
        owner = User.objects.create_user(username="owner")
        requester = User.objects.create_user(username="requester")
        rest_api_client.force_authenticate(user=requester)
        doc = DocumentFactory(owner=owner)
        assign_perm("delete_document", requester, doc)
        doc.delete()

        response = rest_api_client.post(
            "/api/trash/",
            {"documents": [doc.pk], "action": "restore"},
            format="json",
        )
        assert response.status_code == HTTPStatus.OK
