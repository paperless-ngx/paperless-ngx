import json

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.models import ConsumptionTemplate
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestApiConsumptionTemplates(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/consumption_templates/"

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
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.t3 = Tag.objects.create(name="t3")
        self.sp = StoragePath.objects.create(path="/test/")
        self.cf1 = CustomField.objects.create(name="Custom Field 1", data_type="string")
        self.cf2 = CustomField.objects.create(
            name="Custom Field 2",
            data_type="integer",
        )

        self.ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{int(DocumentSource.ApiUpload)},{int(DocumentSource.ConsumeFolder)},{int(DocumentSource.MailFetch)}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        self.ct.assign_tags.add(self.t1)
        self.ct.assign_tags.add(self.t2)
        self.ct.assign_tags.add(self.t3)
        self.ct.assign_view_users.add(self.user3.pk)
        self.ct.assign_view_groups.add(self.group1.pk)
        self.ct.assign_change_users.add(self.user3.pk)
        self.ct.assign_change_groups.add(self.group1.pk)
        self.ct.assign_custom_fields.add(self.cf1.pk)
        self.ct.assign_custom_fields.add(self.cf2.pk)
        self.ct.save()

    def test_api_get_consumption_template(self):
        """
        GIVEN:
            - API request to get all consumption template
        WHEN:
            - API is called
        THEN:
            - Existing consumption templates are returned
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        resp_consumption_template = response.data["results"][0]
        self.assertEqual(resp_consumption_template["id"], self.ct.id)
        self.assertEqual(
            resp_consumption_template["assign_correspondent"],
            self.ct.assign_correspondent.pk,
        )

    def test_api_create_consumption_template(self):
        """
        GIVEN:
            - API request to create a consumption template
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - New template is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*test*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ConsumptionTemplate.objects.count(), 2)

    def test_api_create_invalid_consumption_template(self):
        """
        GIVEN:
            - API request to create a consumption template
            - Neither file name nor path filter are specified
        WHEN:
            - API is called
        THEN:
            - Correct HTTP 400 response
            - No template is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ConsumptionTemplate.objects.count(), 1)

    def test_api_create_consumption_template_empty_fields(self):
        """
        GIVEN:
            - API request to create a consumption template
            - Path or filename filter or assign title are empty string
        WHEN:
            - API is called
        THEN:
            - Template is created but filter or title assignment is not set if ""
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "*test*",
                    "filter_path": "",
                    "assign_title": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct = ConsumptionTemplate.objects.get(name="Template 2")
        self.assertEqual(ct.filter_filename, "*test*")
        self.assertIsNone(ct.filter_path)
        self.assertIsNone(ct.assign_title)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 3",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_filename": "",
                    "filter_path": "*/test/*",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct2 = ConsumptionTemplate.objects.get(name="Template 3")
        self.assertEqual(ct2.filter_path, "*/test/*")
        self.assertIsNone(ct2.filter_filename)

    def test_api_create_consumption_template_with_mailrule(self):
        """
        GIVEN:
            - API request to create a consumption template with a mail rule but no MailFetch source
        WHEN:
            - API is called
        THEN:
            - New template is created with MailFetch as source
        """
        account1 = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        rule1 = MailRule.objects.create(
            name="Rule1",
            account=account1,
            folder="INBOX",
            filter_from="from@example.com",
            filter_to="someone@somewhere.com",
            filter_subject="subject",
            filter_body="body",
            filter_attachment_filename_include="file.pdf",
            maximum_age=30,
            action=MailRule.MailAction.MARK_READ,
            assign_title_from=MailRule.TitleSource.FROM_SUBJECT,
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_NOTHING,
            order=0,
            attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
        )
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Template 2",
                    "order": 1,
                    "sources": [DocumentSource.ApiUpload],
                    "filter_mailrule": rule1.pk,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ConsumptionTemplate.objects.count(), 2)
        ct = ConsumptionTemplate.objects.get(name="Template 2")
        self.assertEqual(ct.sources, [int(DocumentSource.MailFetch).__str__()])
