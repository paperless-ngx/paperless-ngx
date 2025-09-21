from unittest import mock

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from documents import bulk_edit
from documents.models import Document
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.serialisers import TagSerializer
from documents.signals.handlers import run_workflows


class TestTagHierarchy(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="admin")
        self.client.force_authenticate(user=self.user)

        self.parent = Tag.objects.create(name="Parent")
        self.child = Tag.objects.create(name="Child", tn_parent=self.parent)

        patcher = mock.patch("documents.bulk_edit.bulk_update_documents.delay")
        self.async_task = patcher.start()
        self.addCleanup(patcher.stop)

        self.document = Document.objects.create(
            title="doc",
            content="",
            checksum="1",
            mime_type="application/pdf",
        )

    def test_document_api_add_child_adds_parent(self) -> None:
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": [self.child.pk]},
            format="json",
        )
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

    def test_document_api_remove_parent_removes_children(self) -> None:
        self.document.add_nested_tags([self.parent, self.child])
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": [self.child.pk]},
            format="json",
        )
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_document_api_remove_parent_removes_child(self) -> None:
        self.document.add_nested_tags([self.child])
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": []},
            format="json",
        )
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_bulk_edit_respects_hierarchy(self) -> None:
        bulk_edit.add_tag([self.document.pk], self.child.pk)
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

        bulk_edit.remove_tag([self.document.pk], self.parent.pk)
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

        bulk_edit.modify_tags([self.document.pk], [self.child.pk], [])
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

        bulk_edit.modify_tags([self.document.pk], [], [self.parent.pk])
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_workflow_actions(self) -> None:
        workflow = Workflow.objects.create(name="wf", order=0)
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        assign_action = WorkflowAction.objects.create()
        assign_action.assign_tags.add(self.child)
        workflow.triggers.add(trigger)
        workflow.actions.add(assign_action)

        run_workflows(trigger.type, self.document)
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

        # removal
        removal_action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        removal_action.remove_tags.add(self.parent)
        workflow.actions.clear()
        workflow.actions.add(removal_action)

        run_workflows(trigger.type, self.document)
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_tag_view_parent_update_adds_parent_to_docs(self) -> None:
        orphan = Tag.objects.create(name="Orphan")
        self.document.tags.add(orphan)

        self.client.patch(
            f"/api/tags/{orphan.pk}/",
            {"parent": self.parent.pk},
            format="json",
        )

        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, orphan.pk}

    def test_child_document_count_included_when_parent_paginated(self) -> None:
        self.document.tags.add(self.child)

        response = self.client.get(
            "/api/tags/",
            {"page_size": 1, "ordering": "-name"},
        )

        assert response.status_code == 200
        assert response.data["results"][0]["id"] == self.parent.pk

        children = response.data["results"][0]["children"]
        assert len(children) == 1

        child_entry = children[0]
        assert child_entry["id"] == self.child.pk
        assert child_entry["document_count"] == 1

    def test_tag_serializer_populates_document_filter_context(self) -> None:
        context = {}

        serializer = TagSerializer(self.parent, context=context)
        assert serializer.data  # triggers serialization
        assert "document_count_filter" in context

    def test_cannot_set_parent_to_self(self) -> None:
        tag = Tag.objects.create(name="Selfie")
        resp = self.client.patch(
            f"/api/tags/{tag.pk}/",
            {"parent": tag.pk},
            format="json",
        )
        assert resp.status_code == 400
        assert "Cannot set itself as parent" in str(resp.data["parent"])

    def test_cannot_set_parent_to_descendant(self) -> None:
        a = Tag.objects.create(name="A")
        b = Tag.objects.create(name="B", tn_parent=a)
        c = Tag.objects.create(name="C", tn_parent=b)

        # Attempt to set A's parent to C (descendant) should fail
        resp = self.client.patch(
            f"/api/tags/{a.pk}/",
            {"parent": c.pk},
            format="json",
        )
        assert resp.status_code == 400
        assert "Cannot set parent to a descendant" in str(resp.data["parent"])

    def test_max_depth_on_create(self) -> None:
        a = Tag.objects.create(name="A1")
        b = Tag.objects.create(name="B1", tn_parent=a)
        c = Tag.objects.create(name="C1", tn_parent=b)
        d = Tag.objects.create(name="D1", tn_parent=c)

        # Creating E under D yields depth 5: allowed
        resp_ok = self.client.post(
            "/api/tags/",
            {"name": "E1", "parent": d.pk},
            format="json",
        )
        assert resp_ok.status_code in (200, 201)
        e_id = (
            resp_ok.data["id"] if resp_ok.status_code == 201 else resp_ok.data.get("id")
        )
        assert e_id is not None

        # Creating F under E would yield depth 6: rejected
        resp_fail = self.client.post(
            "/api/tags/",
            {"name": "F1", "parent": e_id},
            format="json",
        )
        assert resp_fail.status_code == 400
        assert "parent" in resp_fail.data
        assert "Maximum nesting depth exceeded" in str(resp_fail.data["parent"])

    def test_max_depth_on_move_subtree(self) -> None:
        a = Tag.objects.create(name="A2")
        b = Tag.objects.create(name="B2", tn_parent=a)
        c = Tag.objects.create(name="C2", tn_parent=b)
        d = Tag.objects.create(name="D2", tn_parent=c)

        x = Tag.objects.create(name="X2")
        y = Tag.objects.create(name="Y2", tn_parent=x)
        assert y.parent_pk == x.pk

        # Moving X under D would make deepest node Y exceed depth 5 -> reject
        resp_fail = self.client.patch(
            f"/api/tags/{x.pk}/",
            {"parent": d.pk},
            format="json",
        )
        assert resp_fail.status_code == 400
        assert "Maximum nesting depth exceeded" in str(
            resp_fail.data["parent"],
        )

        # Moving X under C (depth 3) should be allowed (deepest becomes 5)
        resp_ok = self.client.patch(
            f"/api/tags/{x.pk}/",
            {"parent": c.pk},
            format="json",
        )
        assert resp_ok.status_code in (200, 202)
        x.refresh_from_db()
        assert x.parent_pk == c.id

    def test_is_root_filter_returns_only_root_tags(self) -> None:
        other_root = Tag.objects.create(name="Other parent")

        response = self.client.get(
            "/api/tags/",
            {"is_root": "true"},
        )

        assert response.status_code == 200
        assert response.data["count"] == 2

        returned_ids = {row["id"] for row in response.data["results"]}
        assert self.child.pk not in returned_ids
        assert self.parent.pk in returned_ids
        assert other_root.pk in returned_ids

        parent_entry = next(
            row for row in response.data["results"] if row["id"] == self.parent.pk
        )
        assert any(child["id"] == self.child.pk for child in parent_entry["children"])
