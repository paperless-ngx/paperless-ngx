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

from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import permitted_document_ids
from documents.permissions import permitted_object_ids
from documents.permissions import restrict_queryset_to_visible
from documents.serialisers import _get_viewable_duplicates
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import StoragePathFactory
from documents.tests.factories import TagFactory


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

        # Granted on the VERSION itself, but NOT on the root. If the endpoint
        # ever regressed to checking "root OR version" instead of root-only,
        # this grant would incorrectly unlock access. This is the case that
        # actually discriminates correct (root-only) enforcement from a
        # root-or-version bug; a user with no grant at all (the old
        # `stranger` case) can't tell the two apart, since they're denied
        # either way.
        version_only_grantee = User.objects.create_user(username="version_only_grantee")
        assign_perm("view_document", version_only_grantee, version)
        rest_api_client.force_authenticate(user=version_only_grantee)
        response = rest_api_client.post(
            "/api/documents/bulk_download/",
            {"documents": [version.pk]},
            format="json",
        )
        assert (
            response.status_code == HTTPStatus.FORBIDDEN
        )  # version-only grant must not substitute for root permission


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
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


@pytest.mark.django_db
class TestTrashViewExcludesExplicitlyGrantedDocuments:
    """
    Regression test pinning TrashView's use of
    ``_TrashPermittedObjectsFilter`` (``include_granted = False``). If that
    flag were ever flipped to the default ``True``, or the subclass removed
    in favor of the base ``PermittedObjectsFilter``, a trashed document
    would leak into ``/api/trash/`` results for any user holding an
    explicit guardian grant on it, even though they are neither the owner
    nor a superuser.
    """

    def test_explicit_grant_does_not_leak_trashed_document(self, rest_api_client):
        owner = User.objects.create_user(username="trash_owner")
        grantee = User.objects.create_user(username="trash_grantee")
        doc = DocumentFactory(owner=owner)
        doc.delete()  # soft delete
        assign_perm("view_document", grantee, doc)

        rest_api_client.force_authenticate(user=grantee)
        response = rest_api_client.get("/api/trash/")

        assert response.status_code == HTTPStatus.OK
        result_ids = {result["id"] for result in response.data["results"]}
        assert doc.pk not in result_ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model", "factory", "perm"),
    [
        (Tag, TagFactory, "view_tag"),
        (Correspondent, CorrespondentFactory, "view_correspondent"),
        (DocumentType, DocumentTypeFactory, "view_documenttype"),
        (StoragePath, StoragePathFactory, "view_storagepath"),
    ],
)
class TestPermittedObjectIdsGenericModels:
    def test_owner_sees_own_object(self, model, factory, perm):
        owner = User.objects.create_user(username=f"owner_{model.__name__}")
        stranger = User.objects.create_user(username=f"stranger_{model.__name__}")
        owned = factory(owner=owner)
        strangers = factory(owner=stranger)

        assert_visible_document_ids(
            permitted_object_ids(owner, model, perm),
            expected_visible=[owned.pk],
            expected_hidden=[strangers.pk],
        )

    @pytest.mark.parametrize("is_superuser", [False, True])
    def test_inactive_user_sees_nothing(self, model, factory, perm, is_superuser):
        suffix = f"{model.__name__}_{is_superuser}"
        user = User.objects.create_user(
            username=f"inactive_{suffix}",
            is_active=False,
            is_superuser=is_superuser,
        )
        other = User.objects.create_user(username=f"other_{suffix}")
        granted = factory(owner=other)
        assign_perm(perm, user, granted)

        assert_visible_document_ids(
            permitted_object_ids(user, model, perm),
            expected_visible=[],
            expected_hidden=[
                factory(owner=None).pk,
                factory(owner=user).pk,
                granted.pk,
            ],
        )

    def test_unowned_object_visible_to_everyone(self, model, factory, perm):
        user = User.objects.create_user(username=f"user_{model.__name__}")
        unowned = factory(owner=None)

        assert_visible_document_ids(
            permitted_object_ids(user, model, perm),
            expected_visible=[unowned.pk],
            expected_hidden=[],
        )

    def test_explicit_permission_grants_visibility(self, model, factory, perm):
        owner = User.objects.create_user(username=f"owner2_{model.__name__}")
        grantee = User.objects.create_user(username=f"grantee_{model.__name__}")
        stranger = User.objects.create_user(username=f"stranger2_{model.__name__}")
        shared = factory(owner=owner)
        not_shared = factory(owner=owner)
        assign_perm(perm, grantee, shared)

        assert_visible_document_ids(
            permitted_object_ids(grantee, model, perm),
            expected_visible=[shared.pk],
            expected_hidden=[not_shared.pk],
        )
        assert_visible_document_ids(
            permitted_object_ids(stranger, model, perm),
            expected_visible=[],
            expected_hidden=[shared.pk, not_shared.pk],
        )

    def test_group_permission_grants_visibility_to_members_only(
        self,
        model,
        factory,
        perm,
    ):
        owner = User.objects.create_user(username=f"owner3_{model.__name__}")
        member = User.objects.create_user(username=f"member_{model.__name__}")
        non_member = User.objects.create_user(username=f"nonmember_{model.__name__}")
        group = Group.objects.create(name=f"group_{model.__name__}")
        member.groups.add(group)
        shared = factory(owner=owner)
        assign_perm(perm, group, shared)

        assert_visible_document_ids(
            permitted_object_ids(member, model, perm),
            expected_visible=[shared.pk],
            expected_hidden=[],
        )
        assert_visible_document_ids(
            permitted_object_ids(non_member, model, perm),
            expected_visible=[],
            expected_hidden=[shared.pk],
        )

    def test_superuser_sees_everything(self, model, factory, perm):
        superuser = User.objects.create_superuser(username=f"root_{model.__name__}")
        owner = User.objects.create_user(username=f"owner4_{model.__name__}")
        obj = factory(owner=owner)

        assert_visible_document_ids(
            permitted_object_ids(superuser, model, perm),
            expected_visible=[obj.pk],
            expected_hidden=[],
        )


@pytest.mark.django_db
class TestMatchingRespectsObjectPermissions:
    def test_match_tags_only_considers_tags_visible_to_user(self):
        owner = User.objects.create_user(username="tag_owner")
        classifying_user = User.objects.create_user(username="classifier_user")
        visible_tag = TagFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=Tag.MATCH_LITERAL,
        )
        hidden_tag = TagFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=Tag.MATCH_LITERAL,
        )
        assign_perm("view_tag", classifying_user, visible_tag)
        doc = DocumentFactory(owner=classifying_user, content="an invoice document")

        matched = match_tags(doc, classifier=None, user=classifying_user)
        matched_ids = {t.pk for t in matched}
        assert visible_tag.pk in matched_ids
        assert hidden_tag.pk not in matched_ids

    def test_match_correspondents_only_considers_correspondents_visible_to_user(self):
        owner = User.objects.create_user(username="correspondent_owner")
        classifying_user = User.objects.create_user(username="classifier_user2")
        visible_correspondent = CorrespondentFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=Correspondent.MATCH_LITERAL,
        )
        hidden_correspondent = CorrespondentFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=Correspondent.MATCH_LITERAL,
        )
        assign_perm("view_correspondent", classifying_user, visible_correspondent)
        doc = DocumentFactory(owner=classifying_user, content="an invoice document")

        matched = match_correspondents(doc, classifier=None, user=classifying_user)
        matched_ids = {c.pk for c in matched}
        assert visible_correspondent.pk in matched_ids
        assert hidden_correspondent.pk not in matched_ids

    def test_match_document_types_only_considers_document_types_visible_to_user(self):
        owner = User.objects.create_user(username="document_type_owner")
        classifying_user = User.objects.create_user(username="classifier_user3")
        visible_document_type = DocumentTypeFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=DocumentType.MATCH_LITERAL,
        )
        hidden_document_type = DocumentTypeFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=DocumentType.MATCH_LITERAL,
        )
        assign_perm("view_documenttype", classifying_user, visible_document_type)
        doc = DocumentFactory(owner=classifying_user, content="an invoice document")

        matched = match_document_types(doc, classifier=None, user=classifying_user)
        matched_ids = {dt.pk for dt in matched}
        assert visible_document_type.pk in matched_ids
        assert hidden_document_type.pk not in matched_ids

    def test_match_storage_paths_only_considers_storage_paths_visible_to_user(self):
        owner = User.objects.create_user(username="storage_path_owner")
        classifying_user = User.objects.create_user(username="classifier_user4")
        visible_storage_path = StoragePathFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=StoragePath.MATCH_LITERAL,
        )
        hidden_storage_path = StoragePathFactory(
            owner=owner,
            match="invoice",
            matching_algorithm=StoragePath.MATCH_LITERAL,
        )
        assign_perm("view_storagepath", classifying_user, visible_storage_path)
        doc = DocumentFactory(owner=classifying_user, content="an invoice document")

        matched = match_storage_paths(doc, classifier=None, user=classifying_user)
        matched_ids = {sp.pk for sp in matched}
        assert visible_storage_path.pk in matched_ids
        assert hidden_storage_path.pk not in matched_ids


@pytest.mark.django_db
class TestBulkEditObjectsApplyToAllPermissionBoundary:
    def test_apply_to_all_tags_excludes_unpermitted_tag(self, rest_api_client):
        owner = User.objects.create_user(username="tags_owner")
        requester = User.objects.create_user(username="tags_requester")
        new_owner = User.objects.create_user(username="tags_new_owner")
        # grant the global change_tag permission so the object-level
        # filtering (not the global has_perm check) is what's under test
        requester.user_permissions.add(
            Permission.objects.get(codename="change_tag"),
        )
        rest_api_client.force_authenticate(user=requester)
        visible = TagFactory(owner=requester)
        hidden = TagFactory(owner=owner)

        response = rest_api_client.post(
            "/api/bulk_edit_objects/",
            {
                "object_type": "tags",
                "operation": "set_permissions",
                "all": True,
                "filters": {},
                "owner": new_owner.pk,
            },
            format="json",
        )
        assert response.status_code == HTTPStatus.OK

        # The apply_to_all dispatch must resolve permitted objects up front:
        # the requester's own tag gets its owner reassigned, while the tag
        # owned by someone else is excluded entirely and keeps its owner.
        visible.refresh_from_db()
        hidden.refresh_from_db()
        assert visible.owner == new_owner
        assert hidden.owner == owner

    def test_apply_to_all_tags_refuses_shared_but_unowned_tag(self, rest_api_client):
        """
        A tag owned by someone else but shared with the requester is inside the
        permitted set, so it reaches the ownership gate and fails the whole
        request rather than being silently skipped. Editing permissions is
        limited to the owner, same as documents.
        """
        owner = User.objects.create_user(username="shared_tags_owner")
        requester = User.objects.create_user(username="shared_tags_requester")
        requester.user_permissions.add(
            Permission.objects.get(codename="change_tag"),
        )
        rest_api_client.force_authenticate(user=requester)
        owned = TagFactory(owner=requester)
        shared = TagFactory(owner=owner)
        assign_perm("view_tag", requester, shared)
        assign_perm("change_tag", requester, shared)

        response = rest_api_client.post(
            "/api/bulk_edit_objects/",
            {
                "object_type": "tags",
                "operation": "set_permissions",
                "all": True,
                "filters": {},
                "owner": requester.pk,
            },
            format="json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

        owned.refresh_from_db()
        shared.refresh_from_db()
        assert shared.owner == owner
        assert owned.owner == requester


@pytest.mark.django_db
class TestBulkEditObjectsTagDescendantPartialPermission:
    def test_apply_to_all_descendant_expansion_respects_per_object_permissions(
        self,
        rest_api_client,
    ):
        """
        GIVEN:
            - A tag hierarchy (parent -> permitted_child, unpermitted_child)
            - A non-superuser requester who owns the parent and only ONE of
              the two children
        WHEN:
            - bulk_edit_objects is called with all=True and a filter that
              matches only the root (parent) tag, engaging the
              tag-descendant-expansion logic in BulkEditObjectsView.post
        THEN:
            - The descendant expansion only pulls in descendants the
              requester actually has permission on: the permitted child's
              owner is reassigned alongside the parent's, while the
              unpermitted child keeps its original owner. This pins that the
              expansion checks per-object permissions (editable_ids), not
              merely "is a descendant of a filter match".

        NOTE: this uses ``set_permissions`` (owner reassignment) rather than
        ``delete`` as the operation, because Tag.tn_parent (django-treenode)
        cascades deletes to descendants at the database/ORM level regardless
        of which tags the view resolved into ``objs`` - a delete-based test
        would pass/fail based on FK cascade behavior, not on whether the
        descendant-expansion logic itself respected per-object permissions.
        """
        owner = User.objects.create_user(username="tag_hierarchy_owner")
        requester = User.objects.create_user(username="tag_hierarchy_requester")
        new_owner = User.objects.create_user(username="tag_hierarchy_new_owner")
        # global change_tag permission so the has_perm() gate passes and the
        # object-level permitted_object_ids filtering is what's under test
        requester.user_permissions.add(
            Permission.objects.get(codename="change_tag"),
        )
        rest_api_client.force_authenticate(user=requester)

        parent = TagFactory(owner=requester, name="parent-tag")
        permitted_child = TagFactory(
            owner=requester,
            name="permitted-child-tag",
            tn_parent=parent,
        )
        unpermitted_child = TagFactory(
            owner=owner,
            name="unpermitted-child-tag",
            tn_parent=parent,
        )

        response = rest_api_client.post(
            "/api/bulk_edit_objects/",
            {
                "object_type": "tags",
                "operation": "set_permissions",
                "all": True,
                "filters": {"is_root": True},
                "owner": new_owner.pk,
            },
            format="json",
        )
        assert response.status_code == HTTPStatus.OK

        parent.refresh_from_db()
        permitted_child.refresh_from_db()
        unpermitted_child.refresh_from_db()
        assert parent.owner == new_owner
        assert permitted_child.owner == new_owner
        assert unpermitted_child.owner == owner


@pytest.mark.django_db
class TestRestrictQuerysetToVisible:
    """restrict_queryset_to_visible() returns its queryset argument
    unchanged only for "no restriction at all", so the cases that may do
    that have to be kept narrow."""

    def test_no_user_means_no_restriction(self) -> None:
        """
        GIVEN:
            - No user at all (a system-triggered call)
        WHEN:
            - restrict_queryset_to_visible() is called
        THEN:
            - The queryset is returned unfiltered, rather than
              permitted_object_ids(None, ...)'s narrower "unowned rows only"
        """
        owner = User.objects.create_user(username="vis_none_owner")
        tag = TagFactory(owner=owner)

        visible = restrict_queryset_to_visible(Tag.objects.all(), None, "view_tag")

        assert tag.pk in visible.values_list("pk", flat=True)

    def test_active_superuser_means_no_restriction(self) -> None:
        """
        GIVEN:
            - An active superuser
        WHEN:
            - restrict_queryset_to_visible() is called
        THEN:
            - The queryset is returned unfiltered, skipping the permission
              lookup entirely
        """
        superuser = User.objects.create_superuser(username="vis_active_super")
        owner = User.objects.create_user(username="vis_active_super_owner")
        tag = TagFactory(owner=owner)

        visible = restrict_queryset_to_visible(
            Tag.objects.all(),
            superuser,
            "view_tag",
        )

        assert tag.pk in visible.values_list("pk", flat=True)

    def test_inactive_superuser_is_denied_not_unrestricted(self) -> None:
        """
        GIVEN:
            - A deactivated superuser
        WHEN:
            - restrict_queryset_to_visible() is called
        THEN:
            - No rows are visible, never the whole unrestricted queryset -
              deactivation has to win over the superuser shortcut, matching
              permitted_object_ids's own ordering
        """
        user = User.objects.create_user(
            username="vis_inactive_super",
            is_active=False,
            is_superuser=True,
        )
        TagFactory(owner=None)
        TagFactory(owner=user)

        visible = restrict_queryset_to_visible(Tag.objects.all(), user, "view_tag")

        assert not visible.exists()

    def test_regular_user_gets_permitted_ids(self) -> None:
        """
        GIVEN:
            - An ordinary active user and a tag owned by someone else
        WHEN:
            - restrict_queryset_to_visible() is called
        THEN:
            - Only the rows permitted_object_ids() reports are visible
        """
        user = User.objects.create_user(username="vis_regular")
        other = User.objects.create_user(username="vis_regular_other")
        own = TagFactory(owner=user)
        hidden = TagFactory(owner=other)

        visible_ids = set(
            restrict_queryset_to_visible(
                Tag.objects.all(),
                user,
                "view_tag",
            ).values_list("pk", flat=True),
        )

        assert own.pk in visible_ids
        assert hidden.pk not in visible_ids
