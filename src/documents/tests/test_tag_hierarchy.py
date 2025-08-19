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
        self.child = Tag.objects.create(name="Child", parent=self.parent)

        self.document = Document.objects.create(
            title="doc",
            content="",
            checksum="1",
            mime_type="application/pdf",
        )

    def test_api_add_child_adds_parent(self):
        self.client.patch(
            f"/api/documents/{self.document.pk}/",
            {"tags": [self.child.pk]},
            format="json",
        )
        self.document.refresh_from_db()
        tags = set(self.document.tags.values_list("pk", flat=True))
        assert tags == {self.parent.pk, self.child.pk}

    def test_api_remove_parent_removes_child(self):
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
