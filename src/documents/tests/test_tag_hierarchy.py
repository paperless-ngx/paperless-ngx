from unittest import mock

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from documents import bulk_edit
from documents.models import Document
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.signals.handlers import run_workflows


class TestTagHierarchy(APITestCase):
    def setUp(self):
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

    def test_document_api_add_child_adds_parent(self):
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": [self.child.pk]},
            format="json",
        )
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

    def test_document_api_remove_parent_removes_children(self):
        self.document.add_nested_tags([self.parent, self.child])
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": [self.child.pk]},
            format="json",
        )
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_document_api_remove_parent_removes_child(self):
        self.document.add_nested_tags([self.child])
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": []},
            format="json",
        )
        self.document.refresh_from_db()
        assert self.document.tags.count() == 0

    def test_bulk_edit_respects_hierarchy(self):
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

    def test_workflow_actions(self):
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

    def test_tag_view_parent_update_adds_parent_to_docs(self):
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

    def test_cannot_set_parent_to_self(self):
        tag = Tag.objects.create(name="Selfie")
        resp = self.client.patch(
            f"/api/tags/{tag.pk}/",
            {"parent": tag.pk},
            format="json",
        )
        assert resp.status_code == 400
        assert "Cannot set itself as parent" in str(resp.data["parent"])

    def test_cannot_set_parent_to_descendant(self):
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

    def test_max_depth_on_create(self):
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
        assert "Invalid" in str(resp_fail.data["parent"])

    def test_max_depth_on_move_subtree(self):
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
            resp_fail.data["non_field_errors"],
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
