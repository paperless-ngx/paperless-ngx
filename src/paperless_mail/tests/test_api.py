import json
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import TagFactory
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.factories import MailRuleFactory
from paperless_mail.tests.factories import ProcessedMailFactory

if TYPE_CHECKING:
    from paperless_mail.tests.test_mail import BogusMailBox


MAIL_ACCOUNTS_ENDPOINT = "/api/mail_accounts/"
MAIL_RULES_ENDPOINT = "/api/mail_rules/"
PROCESSED_MAIL_ENDPOINT = "/api/processed_mail/"


@pytest.mark.django_db
class TestAPIMailAccounts:
    def test_get_mail_accounts(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Configured mail accounts
        WHEN:
            - API call is made to get mail accounts
        THEN:
            - Configured mail accounts are provided
        """
        account1 = MailAccountFactory(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
        )

        response = mail_api_client.get(MAIL_ACCOUNTS_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        returned_account1 = response.data["results"][0]

        assert returned_account1["name"] == account1.name
        assert returned_account1["username"] == account1.username
        assert returned_account1["password"] == "**********"
        assert returned_account1["imap_server"] == account1.imap_server
        assert returned_account1["imap_port"] == account1.imap_port
        assert returned_account1["imap_security"] == account1.imap_security
        assert returned_account1["character_set"] == account1.character_set

    def test_create_mail_account(
        self,
        mail_api_client: APIClient,
    ) -> None:
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

        response = mail_api_client.post(
            MAIL_ACCOUNTS_ENDPOINT,
            data=account1,
        )

        assert response.status_code == status.HTTP_201_CREATED

        returned_account1 = MailAccount.objects.get(name="Email1")

        assert returned_account1.name == account1["name"]
        assert returned_account1.username == account1["username"]
        assert returned_account1.password == account1["password"]
        assert returned_account1.imap_server == account1["imap_server"]
        assert returned_account1.imap_port == account1["imap_port"]
        assert returned_account1.imap_security == account1["imap_security"]
        assert returned_account1.character_set == account1["character_set"]

    def test_delete_mail_account(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Existing mail account
        WHEN:
            - API request is made to delete a mail account
        THEN:
            - Account is deleted
        """
        account1 = MailAccountFactory()

        response = mail_api_client.delete(
            f"{MAIL_ACCOUNTS_ENDPOINT}{account1.pk}/",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert len(MailAccount.objects.all()) == 0

    def test_update_mail_account(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Existing mail accounts
        WHEN:
            - API request is made to update mail account
        THEN:
            - The mail account is updated, password only updated if not '****'
        """
        account1 = MailAccountFactory()

        response = mail_api_client.patch(
            f"{MAIL_ACCOUNTS_ENDPOINT}{account1.pk}/",
            data={
                "name": "Updated Name 1",
                "password": "******",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        returned_account1 = MailAccount.objects.get(pk=account1.pk)
        assert returned_account1.name == "Updated Name 1"
        assert returned_account1.password == account1.password

        response = mail_api_client.patch(
            f"{MAIL_ACCOUNTS_ENDPOINT}{account1.pk}/",
            data={
                "name": "Updated Name 2",
                "password": "123xyz",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        returned_account2 = MailAccount.objects.get(pk=account1.pk)
        assert returned_account2.name == "Updated Name 2"
        assert returned_account2.password == "123xyz"

    def test_mail_account_test_fail(
        self,
        mail_api_client: APIClient,
        bogus_mailbox: "BogusMailBox",
    ) -> None:
        """
        GIVEN:
            - Errnoeous mail account details
        WHEN:
            - API call is made to test account
        THEN:
            - API returns 400 bad request
        """
        response = mail_api_client.post(
            f"{MAIL_ACCOUNTS_ENDPOINT}test/",
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

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_mail_account_test_success(
        self,
        mail_api_client: APIClient,
        bogus_mailbox: "BogusMailBox",
    ) -> None:
        """
        GIVEN:
            - Working mail account details
        WHEN:
            - API call is made to test account
        THEN:
            - API returns success
        """
        response = mail_api_client.post(
            f"{MAIL_ACCOUNTS_ENDPOINT}test/",
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True

    def test_mail_account_test_existing(
        self,
        mail_api_client: APIClient,
        bogus_mailbox: "BogusMailBox",
    ) -> None:
        """
        GIVEN:
            - Testing server details for an existing account with obfuscated password (***)
        WHEN:
            - API call is made to test account
        THEN:
            - API returns success
        """
        account = MailAccountFactory(
            username="admin",
            password="secret",
            imap_server="server.example.com",
            imap_port=443,
        )

        response = mail_api_client.post(
            f"{MAIL_ACCOUNTS_ENDPOINT}test/",
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True

    def test_mail_account_test_existing_nonexistent_id_forbidden(
        self,
        mail_api_client: APIClient,
        bogus_mailbox: "BogusMailBox",
    ) -> None:
        response = mail_api_client.post(
            f"{MAIL_ACCOUNTS_ENDPOINT}test/",
            json.dumps(
                {
                    "id": 999999,
                    "imap_server": "server.example.com",
                    "imap_port": 443,
                    "imap_security": MailAccount.ImapSecurity.SSL,
                    "username": "admin",
                    "password": "******",
                },
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.content.decode() == "Insufficient permissions"

    def test_get_mail_accounts_owner_aware(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
        django_user_model: type[User],
    ) -> None:
        """
        GIVEN:
            - Configured accounts with different users
        WHEN:
            - API call is made to get mail accounts
        THEN:
            - Only unowned, owned by user or granted accounts are provided
        """
        user2 = django_user_model.objects.create_user(username="temp_admin2")

        account1 = MailAccountFactory(name="Email1")
        account2 = MailAccountFactory(name="Email2", owner=mail_api_user)
        _account3 = MailAccountFactory(name="Email3", owner=user2)
        account4 = MailAccountFactory(name="Email4", owner=user2)
        assign_perm("view_mailaccount", mail_api_user, account4)

        response = mail_api_client.get(MAIL_ACCOUNTS_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert response.data["results"][0]["name"] == account1.name
        assert response.data["results"][1]["name"] == account2.name
        assert response.data["results"][2]["name"] == account4.name


@pytest.mark.django_db
class TestAPIMailRules:
    def test_get_mail_rules(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Configured mail accounts and rules
        WHEN:
            - API call is made to get mail rules
        THEN:
            - Configured mail rules are provided
        """
        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(
            name="Rule1",
            account=account1,
            filter_from="from@example.com",
            filter_to="someone@somewhere.com",
            filter_subject="subject",
            filter_body="body",
            filter_attachment_filename_include="file.pdf",
        )

        response = mail_api_client.get(MAIL_RULES_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        returned_rule1 = response.data["results"][0]

        assert returned_rule1["name"] == rule1.name
        assert returned_rule1["account"] == account1.pk
        assert returned_rule1["folder"] == rule1.folder
        assert returned_rule1["filter_from"] == rule1.filter_from
        assert returned_rule1["filter_to"] == rule1.filter_to
        assert returned_rule1["filter_subject"] == rule1.filter_subject
        assert returned_rule1["filter_body"] == rule1.filter_body
        assert (
            returned_rule1["filter_attachment_filename_include"]
            == rule1.filter_attachment_filename_include
        )
        assert returned_rule1["maximum_age"] == rule1.maximum_age
        assert returned_rule1["action"] == rule1.action
        assert returned_rule1["assign_title_from"] == rule1.assign_title_from
        assert (
            returned_rule1["assign_correspondent_from"]
            == rule1.assign_correspondent_from
        )
        assert returned_rule1["order"] == rule1.order
        assert returned_rule1["attachment_type"] == rule1.attachment_type

    def test_create_mail_rule(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Configured mail account exists
        WHEN:
            - API request is made to add a mail rule
        THEN:
            - A new mail rule is created
        """
        account1 = MailAccountFactory()
        tag = TagFactory(name="t")
        correspondent = CorrespondentFactory(name="c")
        document_type = DocumentTypeFactory(name="dt")

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

        response = mail_api_client.post(
            MAIL_RULES_ENDPOINT,
            data=rule1,
        )

        assert response.status_code == status.HTTP_201_CREATED

        response = mail_api_client.get(MAIL_RULES_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        returned_rule1 = response.data["results"][0]

        assert returned_rule1["name"] == rule1["name"]
        assert returned_rule1["account"] == account1.pk
        assert returned_rule1["folder"] == rule1["folder"]
        assert returned_rule1["filter_from"] == rule1["filter_from"]
        assert returned_rule1["filter_to"] == rule1["filter_to"]
        assert returned_rule1["filter_subject"] == rule1["filter_subject"]
        assert returned_rule1["filter_body"] == rule1["filter_body"]
        assert (
            returned_rule1["filter_attachment_filename_include"]
            == rule1["filter_attachment_filename_include"]
        )
        assert returned_rule1["maximum_age"] == rule1["maximum_age"]
        assert returned_rule1["action"] == rule1["action"]
        assert returned_rule1["assign_title_from"] == rule1["assign_title_from"]
        assert (
            returned_rule1["assign_correspondent_from"]
            == rule1["assign_correspondent_from"]
        )
        assert returned_rule1["order"] == rule1["order"]
        assert returned_rule1["attachment_type"] == rule1["attachment_type"]
        assert returned_rule1["action_parameter"] == rule1["action_parameter"]
        assert returned_rule1["assign_correspondent"] == rule1["assign_correspondent"]
        assert returned_rule1["assign_document_type"] == rule1["assign_document_type"]
        assert returned_rule1["assign_tags"] == rule1["assign_tags"]
        assert (
            returned_rule1["assign_owner_from_rule"] == rule1["assign_owner_from_rule"]
        )

    def test_delete_mail_rule(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Existing mail rule
        WHEN:
            - API request is made to delete a mail rule
        THEN:
            - Rule is deleted
        """
        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1)

        response = mail_api_client.delete(
            f"{MAIL_RULES_ENDPOINT}{rule1.pk}/",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert len(MailRule.objects.all()) == 0

    def test_update_mail_rule(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Existing mail rule
        WHEN:
            - API request is made to update mail rule
        THEN:
            - The mail rule is updated
        """
        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1)

        response = mail_api_client.patch(
            f"{MAIL_RULES_ENDPOINT}{rule1.pk}/",
            data={
                "name": "Updated Name 1",
                "action": MailRule.MailAction.DELETE,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        returned_rule1 = MailRule.objects.get(pk=rule1.pk)
        assert returned_rule1.name == "Updated Name 1"
        assert returned_rule1.action == MailRule.MailAction.DELETE

    def test_create_mail_rule_scopes_accounts(
        self,
        mail_api_client: APIClient,
        django_user_model: type[User],
    ) -> None:
        other_user = django_user_model.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(name="ForeignEmail", owner=other_user)

        response = mail_api_client.post(
            MAIL_RULES_ENDPOINT,
            data={
                "name": "Rule1",
                "account": foreign_account.pk,
                "folder": "INBOX",
                "filter_from": "from@example.com",
                "maximum_age": 30,
                "action": MailRule.MailAction.MARK_READ,
                "assign_title_from": MailRule.TitleSource.FROM_SUBJECT,
                "assign_correspondent_from": MailRule.CorrespondentSource.FROM_NOTHING,
                "order": 0,
                "attachment_type": MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
            },
        )
        missing_response = mail_api_client.post(
            MAIL_RULES_ENDPOINT,
            data={
                "name": "Rule1",
                "account": foreign_account.pk + 1000,
                "folder": "INBOX",
                "filter_from": "from@example.com",
                "maximum_age": 30,
                "action": MailRule.MailAction.MARK_READ,
                "assign_title_from": MailRule.TitleSource.FROM_SUBJECT,
                "assign_correspondent_from": MailRule.CorrespondentSource.FROM_NOTHING,
                "order": 0,
                "attachment_type": MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert missing_response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["account"][0].code == "does_not_exist"
        assert missing_response.data["account"][0].code == "does_not_exist"
        assert MailRule.objects.count() == 0

    def test_create_mail_rule_allowed_for_granted_account_change_permission(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
        django_user_model: type[User],
    ) -> None:
        other_user = django_user_model.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(name="ForeignEmail", owner=other_user)
        assign_perm("change_mailaccount", mail_api_user, foreign_account)

        response = mail_api_client.post(
            MAIL_RULES_ENDPOINT,
            data={
                "name": "Rule1",
                "account": foreign_account.pk,
                "folder": "INBOX",
                "filter_from": "from@example.com",
                "maximum_age": 30,
                "action": MailRule.MailAction.MARK_READ,
                "assign_title_from": MailRule.TitleSource.FROM_SUBJECT,
                "assign_correspondent_from": MailRule.CorrespondentSource.FROM_NOTHING,
                "order": 0,
                "attachment_type": MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert MailRule.objects.get().account == foreign_account

    def test_update_mail_rule_forbidden_for_unpermitted_account(
        self,
        mail_api_client: APIClient,
        django_user_model: type[User],
    ) -> None:
        own_account = MailAccountFactory()
        other_user = django_user_model.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(owner=other_user)
        rule1 = MailRuleFactory(account=own_account)

        response = mail_api_client.patch(
            f"{MAIL_RULES_ENDPOINT}{rule1.pk}/",
            data={"account": foreign_account.pk},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        rule1.refresh_from_db()
        assert rule1.account == own_account

    def test_get_mail_rules_owner_aware(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
        django_user_model: type[User],
    ) -> None:
        """
        GIVEN:
            - Configured rules with different users
        WHEN:
            - API call is made to get mail rules
        THEN:
            - Only unowned, owned by user or granted mail rules are provided
        """
        user2 = django_user_model.objects.create_user(username="temp_admin2")
        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1, order=0)
        rule2 = MailRuleFactory(account=account1, order=1, owner=mail_api_user)
        MailRuleFactory(account=account1, order=2, owner=user2)
        rule4 = MailRuleFactory(account=account1, order=3, owner=user2)
        assign_perm("view_mailrule", mail_api_user, rule4)

        response = mail_api_client.get(MAIL_RULES_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert response.data["results"][0]["name"] == rule1.name
        assert response.data["results"][1]["name"] == rule2.name
        assert response.data["results"][2]["name"] == rule4.name

    def test_mailrule_maxage_validation(
        self,
        mail_api_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - An existing mail account
        WHEN:
            - The user submits a mail rule with an excessively large maximum_age
        THEN:
            - The API should reject the request
        """
        account = MailAccountFactory()

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

        response = mail_api_client.post(
            MAIL_RULES_ENDPOINT,
            data=rule_data,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "maximum_age" in response.data


@pytest.mark.django_db
class TestAPIProcessedMails:
    def test_get_processed_mails_owner_aware(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
        django_user_model: type[User],
    ) -> None:
        """
        GIVEN:
            - Configured processed mails with different users
        WHEN:
            - API call is made to get processed mails
        THEN:
            - Only unowned, owned by user or granted processed mails are provided
        """
        user2 = django_user_model.objects.create_user(username="temp_admin2")
        rule = MailRuleFactory()
        pm1 = ProcessedMailFactory(rule=rule)
        pm2 = ProcessedMailFactory(
            rule=rule,
            status="FAILED",
            error="err",
            owner=mail_api_user,
        )
        ProcessedMailFactory(rule=rule, owner=user2)
        pm4 = ProcessedMailFactory(rule=rule, owner=user2)
        assign_perm("view_processedmail", mail_api_user, pm4)

        response = mail_api_client.get(PROCESSED_MAIL_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        returned_ids = {r["id"] for r in response.data["results"]}
        assert returned_ids == {pm1.id, pm2.id, pm4.id}

    def test_get_processed_mails_filter_by_rule(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
    ) -> None:
        """
        GIVEN:
            - Processed mails belonging to two different rules
        WHEN:
            - API call is made with rule filter
        THEN:
            - Only processed mails for that rule are returned
        """
        account = MailAccountFactory()
        rule1 = MailRuleFactory(account=account)
        rule2 = MailRuleFactory(account=account)
        pm1 = ProcessedMailFactory(rule=rule1, owner=mail_api_user)
        pm2 = ProcessedMailFactory(rule=rule1, status="FAILED", error="e")
        ProcessedMailFactory(rule=rule2)

        response = mail_api_client.get(f"{PROCESSED_MAIL_ENDPOINT}?rule={rule1.pk}")

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {r["id"] for r in response.data["results"]}
        assert returned_ids == {pm1.id, pm2.id}

    def test_bulk_delete_processed_mails(
        self,
        mail_api_client: APIClient,
        mail_api_user: User,
        django_user_model: type[User],
    ) -> None:
        """
        GIVEN:
            - Processed mails belonging to two different rules and different users
        WHEN:
            - API call is made to bulk delete some of the processed mails
        THEN:
            - Only the specified processed mails are deleted, respecting ownership and permissions
        """
        user2 = django_user_model.objects.create_user(username="temp_admin2")
        rule = MailRuleFactory()
        # unowned, owned by self, and one with explicit object perm
        pm_unowned = ProcessedMailFactory(rule=rule)
        pm_owned = ProcessedMailFactory(
            rule=rule,
            status="FAILED",
            error="e",
            owner=mail_api_user,
        )
        pm_granted = ProcessedMailFactory(rule=rule, owner=user2)
        assign_perm("delete_processedmail", mail_api_user, pm_granted)
        pm_forbidden = ProcessedMailFactory(rule=rule, owner=user2)

        # Success for allowed items
        response = mail_api_client.post(
            f"{PROCESSED_MAIL_ENDPOINT}bulk_delete/",
            data={
                "mail_ids": [pm_unowned.id, pm_owned.id, pm_granted.id],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] == "OK"
        assert set(response.data["deleted_mail_ids"]) == {
            pm_unowned.id,
            pm_owned.id,
            pm_granted.id,
        }
        assert not ProcessedMail.objects.filter(id=pm_unowned.id).exists()
        assert not ProcessedMail.objects.filter(id=pm_owned.id).exists()
        assert not ProcessedMail.objects.filter(id=pm_granted.id).exists()
        assert ProcessedMail.objects.filter(id=pm_forbidden.id).exists()

        # 403 and not deleted
        response = mail_api_client.post(
            f"{PROCESSED_MAIL_ENDPOINT}bulk_delete/",
            data={
                "mail_ids": [pm_forbidden.id],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ProcessedMail.objects.filter(id=pm_forbidden.id).exists()

        # missing mail_ids
        response = mail_api_client.post(
            f"{PROCESSED_MAIL_ENDPOINT}bulk_delete/",
            data={"mail_ids": "not-a-list"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
