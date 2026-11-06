from django.contrib.auth.models import Group
from django.test import TestCase

from documents.matching import document_matches_workflow
from documents.matching import existing_document_matches_workflow
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.permissions import user_can_trigger_workflow_trigger
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory


class TestActionButtonTriggerMatching(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.t1 = Tag.objects.create(name="t1")
        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            button_label="Run it",
        )
        self.action = WorkflowAction.objects.create(assign_title="Processed")
        self.workflow = Workflow.objects.create(name="Workflow 1", order=0)
        self.workflow.triggers.add(self.trigger)
        self.workflow.actions.add(self.action)
        self.workflow.save()

    def test_document_matches_workflow_dispatches_action_button_to_existing_document_check(
        self,
    ) -> None:
        """
        GIVEN:
            - A workflow with an ACTION_BUTTON trigger and a tag filter
        WHEN:
            - document_matches_workflow is called with trigger_type
              ACTION_BUTTON
        THEN:
            - It uses the same "existing document" filter checks as
              Document Added/Updated/Scheduled, rather than raising for an
              unhandled trigger type
        """
        document = DocumentFactory.create()

        # No filters configured yet: matches any document.
        self.assertTrue(
            document_matches_workflow(
                document,
                self.workflow,
                WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            ),
        )

        self.trigger.filter_has_tags.add(self.t1)
        self.assertFalse(
            document_matches_workflow(
                document,
                self.workflow,
                WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            ),
        )

        document.tags.add(self.t1)
        self.assertTrue(
            document_matches_workflow(
                document,
                self.workflow,
                WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            ),
        )

    def test_existing_document_matches_workflow_works_directly_on_action_button_trigger(
        self,
    ) -> None:
        document = DocumentFactory.create()
        self.trigger.filter_has_tags.add(self.t1)

        matched, _ = existing_document_matches_workflow(document, self.trigger)
        self.assertFalse(matched)

        document.tags.add(self.t1)
        matched, _ = existing_document_matches_workflow(document, self.trigger)
        self.assertTrue(matched)


class TestUserCanTriggerWorkflowTrigger(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            button_label="Run it",
        )
        self.user = UserFactory(username="user1")

    def test_superuser_can_always_trigger(self) -> None:
        superuser = UserFactory(username="admin", superuser=True)
        self.assertTrue(user_can_trigger_workflow_trigger(superuser, self.trigger))

    def test_user_without_grant_cannot_trigger(self) -> None:
        self.assertFalse(user_can_trigger_workflow_trigger(self.user, self.trigger))

    def test_user_in_trigger_users_can_trigger(self) -> None:
        self.trigger.trigger_users.add(self.user)
        self.assertTrue(user_can_trigger_workflow_trigger(self.user, self.trigger))

    def test_user_in_trigger_group_can_trigger(self) -> None:
        group = Group.objects.create(name="group1")
        self.user.groups.add(group)
        self.trigger.trigger_groups.add(group)
        self.assertTrue(user_can_trigger_workflow_trigger(self.user, self.trigger))

    def test_none_user_cannot_trigger(self) -> None:
        self.assertFalse(user_can_trigger_workflow_trigger(None, self.trigger))
