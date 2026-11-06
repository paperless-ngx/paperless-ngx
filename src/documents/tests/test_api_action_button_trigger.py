import json

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global
from paperless_testing.permissions import grant_object


class TestApiActionButtonTrigger(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/workflows/"

    def setUp(self) -> None:
        super().setUp()

        self.admin = UserFactory(username="temp_admin", superuser=True)
        self.client.force_authenticate(user=self.admin)
        self.user2 = User.objects.create(username="user2")
        self.group1 = Group.objects.create(name="group1")
        self.t1 = Tag.objects.create(name="t1")

        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            button_label="Run it",
            button_color="#ff0000",
        )
        self.trigger.filter_has_tags.add(self.t1)
        self.trigger.trigger_users.add(self.user2)
        self.trigger.trigger_groups.add(self.group1)
        self.trigger.save()

        self.action = WorkflowAction.objects.create(
            assign_title="Processed",
        )

        self.workflow = Workflow.objects.create(name="Workflow 1", order=0)
        self.workflow.triggers.add(self.trigger)
        self.workflow.actions.add(self.action)
        self.workflow.save()

    def test_api_create_workflow_with_action_button_trigger(self) -> None:
        """
        GIVEN:
            - API request to create a workflow with an action button trigger
        WHEN:
            - API is called
        THEN:
            - The trigger's button settings and permission grantees are
              persisted
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
                            "button_label": "Mark reviewed",
                            "button_color": "#00ff00",
                            "require_confirmation": True,
                            "trigger_users": [self.user2.id],
                            "trigger_groups": [self.group1.id],
                            "filter_has_tags": [self.t1.id],
                        },
                    ],
                    "actions": [{"assign_title": "Reviewed"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        workflow = Workflow.objects.get(name="Workflow 2")
        trigger = workflow.triggers.first()
        self.assertEqual(trigger.button_label, "Mark reviewed")
        self.assertEqual(trigger.button_color, "#00ff00")
        self.assertTrue(trigger.require_confirmation)
        self.assertEqual(list(trigger.trigger_users.all()), [self.user2])
        self.assertEqual(list(trigger.trigger_groups.all()), [self.group1])
        self.assertEqual(list(trigger.filter_has_tags.all()), [self.t1])

    def test_action_button_trigger_requires_button_label(self) -> None:
        """
        GIVEN:
            - API request to create an action button trigger without a label
        WHEN:
            - API is called
        THEN:
            - The request is rejected
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
                        },
                    ],
                    "actions": [{"assign_title": "Reviewed"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_action_button_trigger_invalid_color(self) -> None:
        """
        GIVEN:
            - API request to create an action button trigger with an invalid
              button color
        WHEN:
            - API is called
        THEN:
            - The request is rejected
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
                            "button_label": "Go",
                            "button_color": "not-a-color",
                        },
                    ],
                    "actions": [{"assign_title": "Reviewed"}],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_actions_endpoint_lists_matching_trigger(self) -> None:
        """
        GIVEN:
            - An enabled workflow with an action button trigger matching a
              document's tags
        WHEN:
            - GET /api/documents/{id}/actions/
        THEN:
            - The trigger is listed with its button settings
        """
        document = DocumentFactory.create()
        document.tags.add(self.t1)

        response = self.client.get(f"/api/documents/{document.id}/actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": self.trigger.id,
                    "button_label": "Run it",
                    "button_color": "#ff0000",
                    "require_confirmation": False,
                },
            ],
        )

    def test_document_actions_endpoint_excludes_non_matching_document(self) -> None:
        """
        GIVEN:
            - An enabled workflow with an action button trigger requiring a
              tag
        WHEN:
            - GET /api/documents/{id}/actions/ for a document without that tag
        THEN:
            - The trigger is not listed
        """
        document = DocumentFactory.create()

        response = self.client.get(f"/api/documents/{document.id}/actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_document_actions_endpoint_excludes_disabled_workflow(self) -> None:
        """
        GIVEN:
            - A matching action button trigger whose workflow is disabled
        WHEN:
            - GET /api/documents/{id}/actions/
        THEN:
            - The trigger is not listed
        """
        self.workflow.enabled = False
        self.workflow.save()
        document = DocumentFactory.create()
        document.tags.add(self.t1)

        response = self.client.get(f"/api/documents/{document.id}/actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_document_actions_endpoint_excludes_trigger_without_permission(
        self,
    ) -> None:
        """
        GIVEN:
            - A matching action button trigger whose trigger_users/
              trigger_groups do not include the requesting user
        WHEN:
            - GET /api/documents/{id}/actions/
        THEN:
            - The trigger is not listed
        """
        document = DocumentFactory.create()
        document.tags.add(self.t1)

        other_user = User.objects.create(username="other")
        grant_global(other_user, "documents.view_document")
        grant_object(other_user, document, "view_document")
        self.client.force_authenticate(user=other_user)

        response = self.client.get(f"/api/documents/{document.id}/actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_document_actions_endpoint_executes_trigger(self) -> None:
        """
        GIVEN:
            - An enabled, matching action button trigger whose workflow
              assigns a title
        WHEN:
            - POST /api/documents/{id}/actions/ with that trigger's id
        THEN:
            - The workflow's actions are applied to the document, a
              WorkflowRun audit record is created, and the updated document
              is returned
        """
        document = DocumentFactory.create()
        document.tags.add(self.t1)

        response = self.client.post(
            f"/api/documents/{document.id}/actions/",
            json.dumps({"trigger": self.trigger.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        document.refresh_from_db()
        self.assertEqual(document.title, "Processed")
        self.assertEqual(
            WorkflowRun.objects.filter(
                workflow=self.workflow,
                document=document,
                type=WorkflowTrigger.WorkflowTriggerType.ACTION_BUTTON,
            ).count(),
            1,
        )

    def test_document_actions_endpoint_rejects_execute_without_trigger_permission(
        self,
    ) -> None:
        """
        GIVEN:
            - An enabled, matching action button trigger whose trigger_users/
              trigger_groups do not include the requesting user
        WHEN:
            - POST /api/documents/{id}/actions/ with that trigger's id
        THEN:
            - The request is rejected and nothing is applied, re-verifying
              permission server-side rather than trusting an earlier GET
        """
        document = DocumentFactory.create()
        document.tags.add(self.t1)
        original_title = document.title

        other_user = User.objects.create(username="other")
        grant_global(other_user, "documents.view_document")
        grant_object(other_user, document, "view_document")
        self.client.force_authenticate(user=other_user)

        response = self.client.post(
            f"/api/documents/{document.id}/actions/",
            json.dumps({"trigger": self.trigger.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        document.refresh_from_db()
        self.assertEqual(document.title, original_title)
