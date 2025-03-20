import json

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.tests.utils import DirectoriesMixin


class TestApiWorkflows(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/workflows/"
    ENDPOINT_TRIGGERS = "/api/workflow_triggers/"
    ENDPOINT_ACTIONS = "/api/workflow_actions/"

    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)
        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")
        self.group1 = Group.objects.create(name="group1")

        self.c = Correspondent.objects.create(name="Correspondent Name")
        self.c2 = Correspondent.objects.create(name="Correspondent Name 2")
        self.dt = DocumentType.objects.create(name="DocType Name")
        self.dt2 = DocumentType.objects.create(name="DocType Name 2")
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.t3 = Tag.objects.create(name="t3")
        self.sp = StoragePath.objects.create(name="Storage Path 1", path="/test/")
        self.sp2 = StoragePath.objects.create(name="Storage Path 2", path="/test2/")
        self.cf1 = CustomField.objects.create(name="Custom Field 1", data_type="string")
        self.cf2 = CustomField.objects.create(
            name="Custom Field 2",
            data_type="integer",
        )

        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{int(DocumentSource.ApiUpload)},{int(DocumentSource.ConsumeFolder)},{int(DocumentSource.MailFetch)}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
        )
        self.action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        self.action.assign_tags.add(self.t1)
        self.action.assign_tags.add(self.t2)
        self.action.assign_tags.add(self.t3)
        self.action.assign_view_users.add(self.user3.pk)
        self.action.assign_view_groups.add(self.group1.pk)
        self.action.assign_change_users.add(self.user3.pk)
        self.action.assign_change_groups.add(self.group1.pk)
        self.action.assign_custom_fields.add(self.cf1.pk)
        self.action.assign_custom_fields.add(self.cf2.pk)
        self.action.save()

        self.workflow = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        self.workflow.triggers.add(self.trigger)
        self.workflow.actions.add(self.action)
        self.workflow.save()

    def test_api_get_workflow(self):
        """
        GIVEN:
            - API request to get all workflows
        WHEN:
            - API is called
        THEN:
            - Existing workflows are returned
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        resp_workflow = response.data["results"][0]
        self.assertEqual(resp_workflow["id"], self.workflow.id)
        self.assertEqual(
            resp_workflow["actions"][0]["assign_correspondent"],
            self.action.assign_correspondent.pk,
        )

    def test_api_create_workflow(self):
        """
        GIVEN:
            - API request to create a workflow, trigger and action separately
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New workflow, trigger and action are created
        """
        trigger_response = self.client.post(
            self.ENDPOINT_TRIGGERS,
            json.dumps(
                {
                    "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(trigger_response.status_code, status.HTTP_201_CREATED)

        action_response = self.client.post(
            self.ENDPOINT_ACTIONS,
            json.dumps(
                {
                    "assign_title": "Action Title",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(action_response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "id": trigger_response.data["id"],
                            "sources": [DocumentSource.ApiUpload],
                            "type": trigger_response.data["type"],
                            "filter_filename": trigger_response.data["filter_filename"],
                        },
                    ],
                    "actions": [
                        {
                            "id": action_response.data["id"],
                            "assign_title": action_response.data["assign_title"],
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Workflow.objects.count(), 2)

    def test_api_create_workflow_nested(self):
        """
        GIVEN:
            - API request to create a workflow with nested trigger and action
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New workflow, trigger and action are created
        """

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "sources": [DocumentSource.ApiUpload],
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "filter_filename": "*",
                            "filter_path": "*/samples/*",
                            "filter_has_tags": [self.t1.id],
                            "filter_has_document_type": self.dt.id,
                            "filter_has_correspondent": self.c.id,
                        },
                    ],
                    "actions": [
                        {
                            "assign_title": "Action Title",
                            "assign_tags": [self.t2.id],
                            "assign_document_type": self.dt2.id,
                            "assign_correspondent": self.c2.id,
                            "assign_storage_path": self.sp2.id,
                            "assign_owner": self.user2.id,
                            "assign_view_users": [self.user2.id],
                            "assign_view_groups": [self.group1.id],
                            "assign_change_users": [self.user2.id],
                            "assign_change_groups": [self.group1.id],
                            "assign_custom_fields": [self.cf2.id],
                        },
                        {
                            "type": WorkflowAction.WorkflowActionType.REMOVAL,
                            "remove_tags": [self.t3.id],
                            "remove_document_types": [self.dt.id],
                            "remove_correspondents": [self.c.id],
                            "remove_storage_paths": [self.sp.id],
                            "remove_custom_fields": [self.cf1.id],
                            "remove_owners": [self.user2.id],
                            "remove_view_users": [self.user3.id],
                            "remove_change_users": [self.user3.id],
                            "remove_view_groups": [self.group1.id],
                            "remove_change_groups": [self.group1.id],
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Workflow.objects.count(), 2)

    def test_api_create_invalid_workflow_trigger(self):
        """
        GIVEN:
            - API request to create a workflow trigger
            - Neither type or file name nor path filter are specified
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
            - No objects are created
        """
        response = self.client.post(
            self.ENDPOINT_TRIGGERS,
            json.dumps(
                {
                    "sources": [DocumentSource.ApiUpload],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.ENDPOINT_TRIGGERS,
            json.dumps(
                {
                    "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                    "sources": [DocumentSource.ApiUpload],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(WorkflowTrigger.objects.count(), 1)

    def test_api_create_invalid_assign_title(self):
        """
        GIVEN:
            - API request to create a workflow
            - Invalid f-string for assign_title
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
            - No objects are created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 1",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
                        },
                    ],
                    "actions": [
                        {
                            "assign_title": "{created_year]",
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Invalid f-string detected",
            response.data["actions"][0]["assign_title"][0],
        )

        self.assertEqual(Workflow.objects.count(), 1)

    def test_api_create_workflow_trigger_action_empty_fields(self):
        """
        GIVEN:
            - API request to create a workflow trigger and action
            - Path or filename filter or assign title are empty string
        WHEN:
            - API is called
        THEN:
            - Template is created but filter or title assignment is not set if ""
        """
        response = self.client.post(
            self.ENDPOINT_TRIGGERS,
            json.dumps(
                {
                    "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*test*",
                    "filter_path": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        trigger = WorkflowTrigger.objects.get(id=response.data["id"])
        self.assertEqual(trigger.filter_filename, "*test*")
        self.assertIsNone(trigger.filter_path)

        response = self.client.post(
            self.ENDPOINT_ACTIONS,
            json.dumps(
                {
                    "assign_title": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        action = WorkflowAction.objects.get(id=response.data["id"])
        self.assertIsNone(action.assign_title)

        response = self.client.post(
            self.ENDPOINT_TRIGGERS,
            json.dumps(
                {
                    "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "",
                    "filter_path": "*/test/*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        trigger2 = WorkflowTrigger.objects.get(id=response.data["id"])
        self.assertEqual(trigger2.filter_path, "*/test/*")
        self.assertIsNone(trigger2.filter_filename)

    def test_api_update_workflow_nested_triggers_actions(self):
        """
        GIVEN:
            - Existing workflow with trigger and action
        WHEN:
            - API request to update an existing workflow with nested triggers actions
        THEN:
            - Triggers and actions are updated
        """

        response = self.client.patch(
            f"{self.ENDPOINT}{self.workflow.id}/",
            json.dumps(
                {
                    "name": "Workflow Updated",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
                            "filter_has_tags": [self.t1.id],
                            "filter_has_correspondent": self.c.id,
                            "filter_has_document_type": self.dt.id,
                        },
                    ],
                    "actions": [
                        {
                            "assign_title": "Action New Title",
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workflow = Workflow.objects.get(id=response.data["id"])
        self.assertEqual(workflow.name, "Workflow Updated")
        self.assertEqual(workflow.triggers.first().filter_has_tags.first(), self.t1)
        self.assertEqual(workflow.actions.first().assign_title, "Action New Title")

    def test_api_auto_remove_orphaned_triggers_actions(self):
        """
        GIVEN:
            - Existing trigger and action
        WHEN:
            - API request is made which creates new trigger / actions
        THEN:
            - "Orphaned" triggers and actions are removed
        """

        response = self.client.patch(
            f"{self.ENDPOINT}{self.workflow.id}/",
            json.dumps(
                {
                    "name": "Workflow Updated",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
                            "filter_has_tags": [self.t1.id],
                            "filter_has_correspondent": self.c.id,
                            "filter_has_document_type": self.dt.id,
                        },
                    ],
                    "actions": [
                        {
                            "assign_title": "Action New Title",
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workflow = Workflow.objects.get(id=response.data["id"])
        self.assertEqual(WorkflowTrigger.objects.all().count(), 1)
        self.assertNotEqual(workflow.triggers.first().id, self.trigger.id)
        self.assertEqual(WorkflowAction.objects.all().count(), 1)
        self.assertNotEqual(workflow.actions.first().id, self.action.id)

    def test_email_action_validation(self):
        """
        GIVEN:
            - API request to create a workflow with an email action
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "sources": [DocumentSource.ApiUpload],
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [
                        {
                            "type": WorkflowAction.WorkflowActionType.EMAIL,
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        # Notification action requires to, subject and body
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "sources": [DocumentSource.ApiUpload],
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [
                        {
                            "type": WorkflowAction.WorkflowActionType.EMAIL,
                            "email": {
                                "subject": "Subject",
                                "body": "Body",
                            },
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        # Notification action requires destination emails or url
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "sources": [DocumentSource.ApiUpload],
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [
                        {
                            "type": WorkflowAction.WorkflowActionType.EMAIL,
                            "email": {
                                "subject": "Subject",
                                "body": "Body",
                                "to": "me@example.com",
                                "include_document": False,
                            },
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_webhook_action_validation(self):
        """
        GIVEN:
            - API request to create a workflow with a notification action
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "sources": [DocumentSource.ApiUpload],
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [
                        {
                            "type": WorkflowAction.WorkflowActionType.WEBHOOK,
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        # Notification action requires url
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 2",
                    "order": 1,
                    "triggers": [
                        {
                            "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                            "sources": [DocumentSource.ApiUpload],
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [
                        {
                            "type": WorkflowAction.WorkflowActionType.WEBHOOK,
                            "webhook": {
                                "url": "https://example.com",
                                "include_document": False,
                            },
                        },
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
