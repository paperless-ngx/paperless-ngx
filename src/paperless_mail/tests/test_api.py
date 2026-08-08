import json
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import TagFactory
from documents.tests.utils import DirectoriesMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail
from paperless_mail.serialisers import MailRuleSerializer
from paperless_mail.tests.factories import MailAccountFactory
from paperless_mail.tests.factories import MailRuleFactory
from paperless_mail.tests.factories import ProcessedMailFactory
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

        account1 = MailAccountFactory(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
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

        account1 = MailAccountFactory()

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

        account1 = MailAccountFactory()

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
        account = MailAccountFactory(
            username="admin",
            password="secret",
            imap_server="server.example.com",
            imap_port=443,
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

    def test_mail_account_test_existing_nonexistent_id_forbidden(self) -> None:
        response = self.client.post(
            f"{self.ENDPOINT}test/",
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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.content.decode(), "Insufficient permissions")

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

        account1 = MailAccountFactory(name="Email1")
        account2 = MailAccountFactory(name="Email2", owner=self.user)
        _account3 = MailAccountFactory(name="Email3", owner=user2)
        account4 = MailAccountFactory(name="Email4", owner=user2)
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

        account1 = MailAccountFactory()
        subject_field = CustomField.objects.create(
            name="subject_cf",
            data_type=CustomField.FieldDataType.STRING,
        )
        sender_field = CustomField.objects.create(
            name="sender_cf",
            data_type=CustomField.FieldDataType.STRING,
        )
        recipient_field = CustomField.objects.create(
            name="recipient_cf",
            data_type=CustomField.FieldDataType.STRING,
        )
        date_field = CustomField.objects.create(
            name="date_cf",
            data_type=CustomField.FieldDataType.DATE,
        )
        rule1 = MailRuleFactory(
            name="Rule1",
            account=account1,
            filter_from="from@example.com",
            filter_to="someone@somewhere.com",
            filter_subject="subject",
            filter_body="body",
            filter_attachment_filename_include="file.pdf",
            assign_created_from=MailRule.CreatedSource.FROM_MESSAGE_DATE,
            assign_subject_to=subject_field,
            assign_sender_to=sender_field,
            assign_recipient_to=recipient_field,
            assign_message_date_to=date_field,
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

        self.assertIsInstance(returned_rule1["assign_created_from"], int)
        self.assertEqual(
            returned_rule1["assign_created_from"],
            MailRule.CreatedSource.FROM_MESSAGE_DATE,
        )
        self.assertEqual(returned_rule1["assign_subject_to"], subject_field.pk)
        self.assertEqual(returned_rule1["assign_sender_to"], sender_field.pk)
        self.assertEqual(returned_rule1["assign_recipient_to"], recipient_field.pk)
        self.assertEqual(returned_rule1["assign_message_date_to"], date_field.pk)
        for fk in (
            "assign_subject_to",
            "assign_sender_to",
            "assign_recipient_to",
            "assign_message_date_to",
        ):
            self.assertIsInstance(returned_rule1[fk], int)

    def test_create_mail_rule(self) -> None:
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

        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1)

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

        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1)

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

    def test_update_mail_rule_rejects_data_type_mismatched_email_metadata_fk(
        self,
    ) -> None:
        """
        GIVEN:
            - The four assign_*_to FKs each accept exactly one data_type
        WHEN:
            - A PATCH request tries to set each FK to a CustomField of the
              *wrong* data_type
        THEN:
            - The API rejects every mismatch with a per-field error
        """
        string_field = CustomField.objects.create(
            name="Some string",
            data_type=CustomField.FieldDataType.STRING,
        )
        date_field = CustomField.objects.create(
            name="Some date",
            data_type=CustomField.FieldDataType.DATE,
        )

        # Seed the rule with valid FKs so a "silent no-op then null" bug can't
        # masquerade as a rejection: the pre-existing FK id must survive the
        # rejected PATCH.
        seed_string_field = CustomField.objects.create(
            name="Seed string",
            data_type=CustomField.FieldDataType.STRING,
        )
        seed_date_field = CustomField.objects.create(
            name="Seed date",
            data_type=CustomField.FieldDataType.DATE,
        )
        seed_fks = {
            "assign_subject_to": seed_string_field,
            "assign_sender_to": seed_string_field,
            "assign_recipient_to": seed_string_field,
            "assign_message_date_to": seed_date_field,
        }

        # (rule field name, wrong-type CustomField) pairs.
        mismatches = [
            ("assign_subject_to", date_field),
            ("assign_sender_to", date_field),
            ("assign_recipient_to", date_field),
            ("assign_message_date_to", string_field),
        ]

        for field_name, wrong_field in mismatches:
            with self.subTest(field=field_name):
                account = MailAccountFactory()
                rule = MailRuleFactory(
                    account=account,
                    **{field_name: seed_fks[field_name]},
                )
                response = self.client.patch(
                    f"{self.ENDPOINT}{rule.pk}/",
                    data={field_name: wrong_field.pk},
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    response.content,
                )
                self.assertIn(field_name, response.json())
                rule.refresh_from_db()
                self.assertEqual(
                    getattr(rule, f"{field_name}_id"),
                    seed_fks[field_name].pk,
                )

    def test_update_mail_rule_accepts_matching_email_metadata_fk(self) -> None:
        """
        GIVEN:
            - A STRING-typed CustomField
        WHEN:
            - A PATCH request sets assign_subject_to to that field
        THEN:
            - The API accepts the request and the FK is persisted
        """
        account = MailAccountFactory()
        rule = MailRuleFactory(account=account)
        string_field = CustomField.objects.create(
            name="Some subject",
            data_type=CustomField.FieldDataType.STRING,
        )

        response = self.client.patch(
            f"{self.ENDPOINT}{rule.pk}/",
            data={"assign_subject_to": string_field.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertEqual(rule.assign_subject_to_id, string_field.pk)

    def test_update_mail_rule_clears_email_metadata_fk_with_null(self) -> None:
        """
        GIVEN:
            - A MailRule with assign_subject_to pointing at a CustomField
        WHEN:
            - A PATCH request sets assign_subject_to to null
        THEN:
            - The API accepts the request and the FK is cleared
        """
        account = MailAccountFactory()
        string_field = CustomField.objects.create(
            name="Some subject",
            data_type=CustomField.FieldDataType.STRING,
        )
        rule = MailRuleFactory(account=account, assign_subject_to=string_field)

        response = self.client.patch(
            f"{self.ENDPOINT}{rule.pk}/",
            data={"assign_subject_to": None},
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.content,
        )
        rule.refresh_from_db()
        self.assertIsNone(rule.assign_subject_to_id)

    def test_create_mail_rule_rejects_data_type_mismatched_email_metadata_fk(
        self,
    ) -> None:
        """
        GIVEN:
            - A DATE-typed CustomField
        WHEN:
            - A POST create sets assign_subject_to (STRING-only) to that DATE
              field
        THEN:
            - The API rejects with a per-field error and no rule is created
        """
        account = MailAccountFactory()
        date_field = CustomField.objects.create(
            name="Some date",
            data_type=CustomField.FieldDataType.DATE,
        )

        existing_count = MailRule.objects.count()
        response = self.client.post(
            self.ENDPOINT,
            data={
                "name": "created via api",
                "account": account.pk,
                "folder": "INBOX",
                "action": MailRule.MailAction.MARK_READ,
                "assign_subject_to": date_field.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.content,
        )
        self.assertIn("assign_subject_to", response.json())
        self.assertEqual(MailRule.objects.count(), existing_count)

    def test_mail_rule_serializer_validate_accumulates_data_type_errors(
        self,
    ) -> None:
        """
        GIVEN:
            - CustomFields resolved directly into serializer attrs, bypassing
              the field-level ``limit_choices_to`` queryset filter that
              normally rejects wrong-type FKs before ``validate`` runs
        WHEN:
            - Multiple mail-metadata FKs point at CustomFields of the wrong
              data_type (a STRING-only FK with a DATE field and a DATE-only
              FK with a STRING field)
        THEN:
            - ``MailRuleSerializer.validate`` raises a ValidationError with
              one per-field entry, and each entry renders both the expected
              and the got FieldDataType labels
        """
        string_field = CustomField.objects.create(
            name="Str",
            data_type=CustomField.FieldDataType.STRING,
        )
        date_field = CustomField.objects.create(
            name="Dt",
            data_type=CustomField.FieldDataType.DATE,
        )
        attrs = {
            # STRING-typed FK receiving a DATE field
            "assign_subject_to": date_field,
            # DATE-typed FK receiving a STRING field
            "assign_message_date_to": string_field,
        }

        with self.assertRaises(drf_serializers.ValidationError) as ctx:
            MailRuleSerializer().validate(attrs)

        detail = ctx.exception.detail
        self.assertIn("assign_subject_to", detail)
        self.assertIn("assign_message_date_to", detail)
        string_label = str(CustomField.FieldDataType.STRING.label)
        date_label = str(CustomField.FieldDataType.DATE.label)
        subject_msg = str(detail["assign_subject_to"])
        message_date_msg = str(detail["assign_message_date_to"])
        self.assertIn(string_label, subject_msg)
        self.assertIn(date_label, subject_msg)
        self.assertIn(date_label, message_date_msg)
        self.assertIn(string_label, message_date_msg)

    def test_create_mail_rule_scopes_accounts(self) -> None:
        other_user = User.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(name="ForeignEmail", owner=other_user)

        response = self.client.post(
            self.ENDPOINT,
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
        missing_response = self.client.post(
            self.ENDPOINT,
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["account"][0].code, "does_not_exist")
        self.assertEqual(missing_response.data["account"][0].code, "does_not_exist")
        self.assertEqual(MailRule.objects.count(), 0)

    def test_create_mail_rule_allowed_for_granted_account_change_permission(
        self,
    ) -> None:
        other_user = User.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(name="ForeignEmail", owner=other_user)
        assign_perm("change_mailaccount", self.user, foreign_account)

        response = self.client.post(
            self.ENDPOINT,
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MailRule.objects.get().account, foreign_account)

    def test_update_mail_rule_forbidden_for_unpermitted_account(self) -> None:
        own_account = MailAccountFactory()
        other_user = User.objects.create_user(username="mail-owner")
        foreign_account = MailAccountFactory(owner=other_user)
        rule1 = MailRuleFactory(account=own_account)

        response = self.client.patch(
            f"{self.ENDPOINT}{rule1.pk}/",
            data={"account": foreign_account.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        rule1.refresh_from_db()
        self.assertEqual(rule1.account, own_account)

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
        account1 = MailAccountFactory()
        rule1 = MailRuleFactory(account=account1, order=0)
        rule2 = MailRuleFactory(account=account1, order=1, owner=self.user)
        MailRuleFactory(account=account1, order=2, owner=user2)
        rule4 = MailRuleFactory(account=account1, order=3, owner=user2)
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
        rule = MailRuleFactory()
        pm1 = ProcessedMailFactory(rule=rule)
        pm2 = ProcessedMailFactory(
            rule=rule,
            status="FAILED",
            error="err",
            owner=self.user,
        )
        ProcessedMailFactory(rule=rule, owner=user2)
        pm4 = ProcessedMailFactory(rule=rule, owner=user2)
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
        account = MailAccountFactory()
        rule1 = MailRuleFactory(account=account)
        rule2 = MailRuleFactory(account=account)
        pm1 = ProcessedMailFactory(rule=rule1, owner=self.user)
        pm2 = ProcessedMailFactory(rule=rule1, status="FAILED", error="e")
        ProcessedMailFactory(rule=rule2)

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
        rule = MailRuleFactory()
        # unowned, owned by self, and one with explicit object perm
        pm_unowned = ProcessedMailFactory(rule=rule)
        pm_owned = ProcessedMailFactory(
            rule=rule,
            status="FAILED",
            error="e",
            owner=self.user,
        )
        pm_granted = ProcessedMailFactory(rule=rule, owner=user2)
        assign_perm("delete_processedmail", self.user, pm_granted)
        pm_forbidden = ProcessedMailFactory(rule=rule, owner=user2)

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
