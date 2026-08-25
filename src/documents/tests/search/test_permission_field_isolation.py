"""Permission filtering must hold against the real indexed document shape.

Only three of the index's unsigned ``*_id`` columns are load-bearing:
``owner_id``, ``viewer_id`` and ``viewer_group_id``, all read by
build_permission_filter. The rest (correspondent/document_type/storage_path/tag
ids) were written on every document and read by nothing, and were dropped.

These tests index real Documents through the backend's own document builder and
assert result-level visibility per user, so a mistake about which columns are
load-bearing shows up as documents leaking across users rather than as a passing
unit test over a hand-built index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


@pytest.fixture
def owner() -> User:
    return User.objects.create_user(username="owner")


@pytest.fixture
def stranger() -> User:
    return User.objects.create_user(username="stranger")


@pytest.fixture
def viewer() -> User:
    return User.objects.create_user(username="viewer")


@pytest.fixture
def group_member() -> User:
    user = User.objects.create_user(username="group_member")
    user.groups.add(Group.objects.create(name="accounting"))
    return user


class TestPermissionFilteringOnIndexedDocuments:
    def test_unowned_document_is_visible_to_everyone(
        self,
        backend: TantivyBackend,
        stranger: User,
    ) -> None:
        doc = Document.objects.create(
            title="Public Invoice",
            content="invoice total due",
            checksum="perm-unowned",
        )
        backend.add_or_update(doc)

        assert backend.search_ids("invoice", user=stranger) == [doc.pk]

    def test_owned_document_is_visible_only_to_its_owner(
        self,
        backend: TantivyBackend,
        owner: User,
        stranger: User,
    ) -> None:
        doc = Document.objects.create(
            title="Private Invoice",
            content="invoice total due",
            checksum="perm-owned",
            owner=owner,
        )
        backend.add_or_update(doc)

        assert backend.search_ids("invoice", user=owner) == [doc.pk]
        assert backend.search_ids("invoice", user=stranger) == []

    def test_explicitly_shared_document_is_visible_to_the_viewer(
        self,
        backend: TantivyBackend,
        owner: User,
        viewer: User,
        stranger: User,
    ) -> None:
        doc = Document.objects.create(
            title="Shared Invoice",
            content="invoice total due",
            checksum="perm-shared-user",
            owner=owner,
        )
        assign_perm("view_document", viewer, doc)
        backend.add_or_update(doc)

        assert backend.search_ids("invoice", user=viewer) == [doc.pk]
        assert backend.search_ids("invoice", user=stranger) == []

    def test_group_shared_document_is_visible_to_group_members(
        self,
        backend: TantivyBackend,
        owner: User,
        group_member: User,
        stranger: User,
    ) -> None:
        doc = Document.objects.create(
            title="Group Invoice",
            content="invoice total due",
            checksum="perm-shared-group",
            owner=owner,
        )
        assign_perm("view_document", group_member.groups.first(), doc)
        backend.add_or_update(doc)

        assert backend.search_ids("invoice", user=group_member) == [doc.pk]
        assert backend.search_ids("invoice", user=stranger) == []

    def test_metadata_does_not_widen_visibility(
        self,
        backend: TantivyBackend,
        owner: User,
        stranger: User,
    ) -> None:
        """A document carrying correspondent/type/storage-path/tag metadata is
        still filtered by owner alone."""
        doc = Document.objects.create(
            title="Tagged Invoice",
            content="invoice total due",
            checksum="perm-metadata",
            owner=owner,
            correspondent=Correspondent.objects.create(name="ACME"),
            document_type=DocumentType.objects.create(name="Bill"),
            storage_path=StoragePath.objects.create(name="Archive", path="archive/"),
        )
        doc.tags.add(Tag.objects.create(name="paid"))
        backend.add_or_update(doc)

        assert backend.search_ids("invoice", user=owner) == [doc.pk]
        assert backend.search_ids("invoice", user=stranger) == []
