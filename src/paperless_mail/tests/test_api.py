import json
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.tests.test_mail import BogusMailBox


class TestAPIMailAccounts(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/mail_accounts/"

    def setUp(self) -> None:
        self.bogus_mailbox = BogusMailBox()

        patcher = mock.patch("paperless_mail.mail.MailBox")
        m = patcher.start()
        m.return_value = self.bogus_mailbox
        self.addCleanup(patcher.stop)

        super().setUp()

        self.user = User.objects.create_user(username="temp_admin")
        self.user.user_permissions.add(*Permission.objects.all())
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_get_mail_accounts(self) -> None:
        """
        GIVEN:
            - Configured mail accounts
        WHEN:
            - API call is made to get mail accounts
        THEN:
            - Configured mail accounts are provided
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

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        returned_account1 = response.data["results"][0]

        self.assertEqual(returned_account1["name"], account1.name)
        self.assertEqual(returned_account1["username"], account1.username)
        self.assertEqual(
            returned_account1["password"],
            "**********",
        )
        self.assertEqual(returned_account1["imap_server"], account1.imap_server)
        self.assertEqual(returned_account1["imap_port"], account1.imap_port)
        self.assertEqual(returned_account1["imap_security"], account1.imap_security)
        self.assertEqual(returned_account1["character_set"], account1.character_set)

    def test_create_mail_account(self) -> None:
        """
        WHEN:
            - API request is made to add a mail account
        THEN:
            - A new mail account is created
        """

        account1 = {
            "name": "Email1",
            "username": "username1",
            "password": "password1",
            "imap_server": "server.example.com",
            "imap_port": 443,
            "imap_security": MailAccount.ImapSecurity.SSL,
            "character_set": "UTF-8",
        }

        response = self.client.post(
            self.ENDPOINT,
            data=account1,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        returned_account1 = MailAccount.objects.get(name="Email1")

        self.assertEqual(returned_account1.name, account1["name"])
        self.assertEqual(returned_account1.username, account1["username"])
        self.assertEqual(returned_account1.password, account1["password"])
        self.assertEqual(returned_account1.imap_server, account1["imap_server"])
        self.assertEqual(returned_account1.imap_port, account1["imap_port"])
        self.assertEqual(returned_account1.imap_security, account1["imap_security"])
        self.assertEqual(returned_account1.character_set, account1["character_set"])

    def test_delete_mail_account(self) -> None:
        """
        GIVEN:
            - Existing mail account
        WHEN:
            - API request is made to delete a mail account
        THEN:
            - Account is deleted
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

        response = self.client.delete(
            f"{self.ENDPOINT}{account1.pk}/",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(len(MailAccount.objects.all()), 0)

    def test_update_mail_account(self) -> None:
        """
        GIVEN:
            - Existing mail accounts
        WHEN:
            - API request is made to update mail account
        THEN:
            - The mail account is updated, password only updated if not '****'
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

        response = self.client.patch(
            f"{self.ENDPOINT}{account1.pk}/",
            data={
                "name": "Updated Name 1",
                "password": "******",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_account1 = MailAccount.objects.get(pk=account1.pk)
        self.assertEqual(returned_account1.name, "Updated Name 1")
        self.assertEqual(returned_account1.password, account1.password)

        response = self.client.patch(
            f"{self.ENDPOINT}{account1.pk}/",
            data={
                "name": "Updated Name 2",
                "password": "123xyz",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_account2 = MailAccount.objects.get(pk=account1.pk)
        self.assertEqual(returned_account2.name, "Updated Name 2")
        self.assertEqual(returned_account2.password, "123xyz")

    def test_mail_account_test_fail(self) -> None:
        """
        GIVEN:
            - Errnoeous mail account details
        WHEN:
            - API call is made to test account
        THEN:
            - API returns 400 bad request
        """

        response = self.client.post(
            f"{self.ENDPOINT}test/",
            json.dumps(
                {
                    "imap_server": "server.example.com",
                    "imap_port": 443,
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "username": "admin",
                    "password": "notcorrect",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mail_account_test_success(self) -> None:
        """
        GIVEN:
            - Working mail account details
        WHEN:
            - API call is made to test account
        THEN:
            - API returns success
        """

        response = self.client.post(
            f"{self.ENDPOINT}test/",
            json.dumps(
                {
                    "imap_server": "server.example.com",
                    "imap_port": 443,
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "username": "admin",
                    "password": "secret",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)

    def test_mail_account_test_existing(self) -> None:
        """
        GIVEN:
            - Testing server details for an existing account with obfuscated password (***)
        WHEN:
            - API call is made to test account
        THEN:
            - API returns success
        """
        account = MailAccount.objects.create(
            name="Email1",
            username="admin",
            password="secret",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )

        response = self.client.post(
            f"{self.ENDPOINT}test/",
            json.dumps(
                {
                    "id": account.pk,
                    "imap_server": "server.example.com",
                    "imap_port": 443,
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "username": "admin",
                    "password": "******",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)

    def test_get_mail_accounts_owner_aware(self) -> None:
        """
        GIVEN:
            - Configured accounts with different users
        WHEN:
            - API call is made to get mail accounts
        THEN:
            - Only unowned, owned by user or granted accounts are provided
        """

        user2 = User.objects.create_user(username="temp_admin2")

        account1 = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )

        account2 = MailAccount.objects.create(
            name="Email2",
            username="username2",
            password="password2",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        account2.owner = self.user
        account2.save()

        account3 = MailAccount.objects.create(
            name="Email3",
            username="username3",
            password="password3",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        account3.owner = user2
        account3.save()

        account4 = MailAccount.objects.create(
            name="Email4",
            username="username4",
            password="password4",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        account4.owner = user2
        account4.save()
        assign_perm("view_mailaccount", self.user, account4)

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["results"][0]["name"], account1.name)
        self.assertEqual(response.data["results"][1]["name"], account2.name)
        self.assertEqual(response.data["results"][2]["name"], account4.name)


class TestAPIMailRules(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/mail_rules/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_user(username="temp_admin")
        self.user.user_permissions.add(*Permission.objects.all())
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_get_mail_rules(self) -> None:
        """
        GIVEN:
            - Configured mail accounts and rules
        WHEN:
            - API call is made to get mail rules
        THEN:
            - Configured mail rules are provided
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

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        returned_rule1 = response.data["results"][0]

        self.assertEqual(returned_rule1["name"], rule1.name)
        self.assertEqual(returned_rule1["account"], account1.pk)
        self.assertEqual(returned_rule1["folder"], rule1.folder)
        self.assertEqual(returned_rule1["filter_from"], rule1.filter_from)
        self.assertEqual(returned_rule1["filter_to"], rule1.filter_to)
        self.assertEqual(returned_rule1["filter_subject"], rule1.filter_subject)
        self.assertEqual(returned_rule1["filter_body"], rule1.filter_body)
        self.assertEqual(
            returned_rule1["filter_attachment_filename_include"],
            rule1.filter_attachment_filename_include,
        )
        self.assertEqual(returned_rule1["maximum_age"], rule1.maximum_age)
        self.assertEqual(returned_rule1["action"], rule1.action)
        self.assertEqual(returned_rule1["assign_title_from"], rule1.assign_title_from)
        self.assertEqual(
            returned_rule1["assign_correspondent_from"],
            rule1.assign_correspondent_from,
        )
        self.assertEqual(returned_rule1["order"], rule1.order)
        self.assertEqual(returned_rule1["attachment_type"], rule1.attachment_type)

    def test_create_mail_rule(self) -> None:
        """
        GIVEN:
            - Configured mail account exists
        WHEN:
            - API request is made to add a mail rule
        THEN:
            - A new mail rule is created
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

        tag = Tag.objects.create(
            name="t",
        )

        correspondent = Correspondent.objects.create(
            name="c",
        )

        document_type = DocumentType.objects.create(
            name="dt",
        )

        rule1 = {
            "name": "Rule1",
            "account": account1.pk,
            "folder": "INBOX",
            "filter_from": "from@example.com",
            "filter_to": "aperson@aplace.com",
            "filter_subject": "subject",
            "filter_body": "body",
            "filter_attachment_filename_include": "file.pdf",
            "maximum_age": 30,
            "action": MailRule.MailAction.MARK_READ,
            "assign_title_from": MailRule.TitleSource.FROM_SUBJECT,
            "assign_correspondent_from": MailRule.CorrespondentSource.FROM_NOTHING,
            "order": 0,
            "attachment_type": MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
            "action_parameter": "parameter",
            "assign_tags": [tag.pk],
            "assign_correspondent": correspondent.pk,
            "assign_document_type": document_type.pk,
            "assign_owner_from_rule": True,
        }

        response = self.client.post(
            self.ENDPOINT,
            data=rule1,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        returned_rule1 = response.data["results"][0]

        self.assertEqual(returned_rule1["name"], rule1["name"])
        self.assertEqual(returned_rule1["account"], account1.pk)
        self.assertEqual(returned_rule1["folder"], rule1["folder"])
        self.assertEqual(returned_rule1["filter_from"], rule1["filter_from"])
        self.assertEqual(returned_rule1["filter_to"], rule1["filter_to"])
        self.assertEqual(returned_rule1["filter_subject"], rule1["filter_subject"])
        self.assertEqual(returned_rule1["filter_body"], rule1["filter_body"])
        self.assertEqual(
            returned_rule1["filter_attachment_filename_include"],
            rule1["filter_attachment_filename_include"],
        )
        self.assertEqual(returned_rule1["maximum_age"], rule1["maximum_age"])
        self.assertEqual(returned_rule1["action"], rule1["action"])
        self.assertEqual(
            returned_rule1["assign_title_from"],
            rule1["assign_title_from"],
        )
        self.assertEqual(
            returned_rule1["assign_correspondent_from"],
            rule1["assign_correspondent_from"],
        )
        self.assertEqual(returned_rule1["order"], rule1["order"])
        self.assertEqual(returned_rule1["attachment_type"], rule1["attachment_type"])
        self.assertEqual(returned_rule1["action_parameter"], rule1["action_parameter"])
        self.assertEqual(
            returned_rule1["assign_correspondent"],
            rule1["assign_correspondent"],
        )
        self.assertEqual(
            returned_rule1["assign_document_type"],
            rule1["assign_document_type"],
        )
        self.assertEqual(returned_rule1["assign_tags"], rule1["assign_tags"])
        self.assertEqual(
            returned_rule1["assign_owner_from_rule"],
            rule1["assign_owner_from_rule"],
        )

    def test_delete_mail_rule(self) -> None:
        """
        GIVEN:
            - Existing mail rule
        WHEN:
            - API request is made to delete a mail rule
        THEN:
            - Rule is deleted
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

        response = self.client.delete(
            f"{self.ENDPOINT}{rule1.pk}/",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(len(MailRule.objects.all()), 0)

    def test_update_mail_rule(self) -> None:
        """
        GIVEN:
            - Existing mail rule
        WHEN:
            - API request is made to update mail rule
        THEN:
            - The mail rule is updated
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

        response = self.client.patch(
            f"{self.ENDPOINT}{rule1.pk}/",
            data={
                "name": "Updated Name 1",
                "action": MailRule.MailAction.DELETE,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_rule1 = MailRule.objects.get(pk=rule1.pk)
        self.assertEqual(returned_rule1.name, "Updated Name 1")
        self.assertEqual(returned_rule1.action, MailRule.MailAction.DELETE)

    def test_get_mail_rules_owner_aware(self) -> None:
        """
        GIVEN:
            - Configured rules with different users
        WHEN:
            - API call is made to get mail rules
        THEN:
            - Only unowned, owned by user or granted mail rules are provided
        """

        user2 = User.objects.create_user(username="temp_admin2")

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
            filter_from="from@example1.com",
            order=0,
        )

        rule2 = MailRule.objects.create(
            name="Rule2",
            account=account1,
            folder="INBOX",
            filter_from="from@example2.com",
            order=1,
        )
        rule2.owner = self.user
        rule2.save()

        rule3 = MailRule.objects.create(
            name="Rule3",
            account=account1,
            folder="INBOX",
            filter_from="from@example3.com",
            order=2,
        )
        rule3.owner = user2
        rule3.save()

        rule4 = MailRule.objects.create(
            name="Rule4",
            account=account1,
            folder="INBOX",
            filter_from="from@example4.com",
            order=3,
        )
        rule4.owner = user2
        rule4.save()
        assign_perm("view_mailrule", self.user, rule4)

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["results"][0]["name"], rule1.name)
        self.assertEqual(response.data["results"][1]["name"], rule2.name)
        self.assertEqual(response.data["results"][2]["name"], rule4.name)

    def test_mailrule_maxage_validation(self) -> None:
        """
        GIVEN:
            - An existing mail account
        WHEN:
            - The user submits a mail rule with an excessively large maximum_age
        THEN:
            - The API should reject the request
        """
        account = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )

        rule_data = {
            "name": "Rule1",
            "account": account.pk,
            "folder": "INBOX",
            "filter_from": "from@example.com",
            "filter_to": "aperson@aplace.com",
            "filter_subject": "subject",
            "filter_body": "body",
            "filter_attachment_filename_include": "file.pdf",
            "maximum_age": 9000000,
            "action": MailRule.MailAction.MARK_READ,
            "assign_title_from": MailRule.TitleSource.FROM_SUBJECT,
            "assign_correspondent_from": MailRule.CorrespondentSource.FROM_NOTHING,
            "order": 0,
            "attachment_type": MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
        }

        response = self.client.post(self.ENDPOINT, data=rule_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum_age", response.data)


class TestAPIProcessedMails(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/processed_mail/"

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_user(username="temp_admin")
        self.user.user_permissions.add(*Permission.objects.all())
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_get_processed_mails_owner_aware(self) -> None:
        """
        GIVEN:
            - Configured processed mails with different users
        WHEN:
            - API call is made to get processed mails
        THEN:
            - Only unowned, owned by user or granted processed mails are provided
        """
        user2 = User.objects.create_user(username="temp_admin2")

        account = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )

        rule = MailRule.objects.create(
            name="Rule1",
            account=account,
            folder="INBOX",
            filter_from="from@example.com",
            order=0,
        )

        pm1 = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="1",
            subject="Subj1",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
        )

        pm2 = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="2",
            subject="Subj2",
            received=timezone.now(),
            processed=timezone.now(),
            status="FAILED",
            error="err",
            owner=self.user,
        )

        ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="3",
            subject="Subj3",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
            owner=user2,
        )

        pm4 = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="4",
            subject="Subj4",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
        )
        pm4.owner = user2
        pm4.save()
        assign_perm("view_processedmail", self.user, pm4)

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        returned_ids = {r["id"] for r in response.data["results"]}
        self.assertSetEqual(returned_ids, {pm1.id, pm2.id, pm4.id})

    def test_get_processed_mails_filter_by_rule(self) -> None:
        """
        GIVEN:
            - Processed mails belonging to two different rules
        WHEN:
            - API call is made with rule filter
        THEN:
            - Only processed mails for that rule are returned
        """
        account = MailAccount.objects.create(
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
            account=account,
            folder="INBOX",
            filter_from="from1@example.com",
            order=0,
        )
        rule2 = MailRule.objects.create(
            name="Rule2",
            account=account,
            folder="INBOX",
            filter_from="from2@example.com",
            order=1,
        )

        pm1 = ProcessedMail.objects.create(
            rule=rule1,
            folder="INBOX",
            uid="r1-1",
            subject="R1-A",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
            owner=self.user,
        )
        pm2 = ProcessedMail.objects.create(
            rule=rule1,
            folder="INBOX",
            uid="r1-2",
            subject="R1-B",
            received=timezone.now(),
            processed=timezone.now(),
            status="FAILED",
            error="e",
        )
        ProcessedMail.objects.create(
            rule=rule2,
            folder="INBOX",
            uid="r2-1",
            subject="R2-A",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
        )

        response = self.client.get(f"{self.ENDPOINT}?rule={rule1.pk}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {r["id"] for r in response.data["results"]}
        self.assertSetEqual(returned_ids, {pm1.id, pm2.id})

    def test_bulk_delete_processed_mails(self) -> None:
        """
        GIVEN:
            - Processed mails belonging to two different rules and different users
        WHEN:
            - API call is made to bulk delete some of the processed mails
        THEN:
            - Only the specified processed mails are deleted, respecting ownership and permissions
        """
        user2 = User.objects.create_user(username="temp_admin2")

        account = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )

        rule = MailRule.objects.create(
            name="Rule1",
            account=account,
            folder="INBOX",
            filter_from="from@example.com",
            order=0,
        )

        # unowned and owned by self, and one with explicit object perm
        pm_unowned = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="u1",
            subject="Unowned",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
        )
        pm_owned = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="u2",
            subject="Owned",
            received=timezone.now(),
            processed=timezone.now(),
            status="FAILED",
            error="e",
            owner=self.user,
        )
        pm_granted = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="u3",
            subject="Granted",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
            owner=user2,
        )
        assign_perm("delete_processedmail", self.user, pm_granted)
        pm_forbidden = ProcessedMail.objects.create(
            rule=rule,
            folder="INBOX",
            uid="u4",
            subject="Forbidden",
            received=timezone.now(),
            processed=timezone.now(),
            status="SUCCESS",
            error=None,
            owner=user2,
        )

        # Success for allowed items
        response = self.client.post(
            f"{self.ENDPOINT}bulk_delete/",
            data={
                "mail_ids": [pm_unowned.id, pm_owned.id, pm_granted.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["result"], "OK")
        self.assertSetEqual(
            set(response.data["deleted_mail_ids"]),
            {pm_unowned.id, pm_owned.id, pm_granted.id},
        )
        self.assertFalse(ProcessedMail.objects.filter(id=pm_unowned.id).exists())
        self.assertFalse(ProcessedMail.objects.filter(id=pm_owned.id).exists())
        self.assertFalse(ProcessedMail.objects.filter(id=pm_granted.id).exists())
        self.assertTrue(ProcessedMail.objects.filter(id=pm_forbidden.id).exists())

        # 403 and not deleted
        response = self.client.post(
            f"{self.ENDPOINT}bulk_delete/",
            data={
                "mail_ids": [pm_forbidden.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ProcessedMail.objects.filter(id=pm_forbidden.id).exists())

        # missing mail_ids
        response = self.client.post(
            f"{self.ENDPOINT}bulk_delete/",
            data={"mail_ids": "not-a-list"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
