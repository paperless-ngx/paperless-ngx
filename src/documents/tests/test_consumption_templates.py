from pathlib import Path
from unittest import TestCase
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.contrib.auth.models import User

from documents import tasks
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.models import ConsumptionTemplate
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


@pytest.mark.django_db
class TestConsumptionTemplates(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_DIR = Path(__file__).parent / "samples"

    def setUp(self) -> None:
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

        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")
        self.group1 = Group.objects.create(name="group1")

        account1 = MailAccount.objects.create(
            name="Email1",
            username="username1",
            password="password1",
            imap_server="server.example.com",
            imap_port=443,
            imap_security=MailAccount.ImapSecurity.SSL,
            character_set="UTF-8",
        )
        self.rule1 = MailRule.objects.create(
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
            assign_title_from=MailRule.TitleSource.NONE,
            assign_correspondent_from=MailRule.CorrespondentSource.FROM_NOTHING,
            order=0,
            attachment_type=MailRule.AttachmentProcessing.ATTACHMENTS_ONLY,
            assign_owner_from_rule=False,
        )

        return super().setUp()

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_match(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that matches is consumed
        THEN:
            - Template overrides are applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        ct.assign_tags.add(self.t1)
        ct.assign_tags.add(self.t2)
        ct.assign_tags.add(self.t3)
        ct.assign_view_users.add(self.user3.pk)
        ct.assign_view_groups.add(self.group1.pk)
        ct.assign_change_users.add(self.user3.pk)
        ct.assign_change_groups.add(self.group1.pk)
        ct.assign_custom_fields.add(self.cf1.pk)
        ct.assign_custom_fields.add(self.cf2.pk)
        ct.save()

        self.assertEqual(ct.__str__(), "Template 1")

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertEqual(overrides["override_correspondent_id"], self.c.pk)
                self.assertEqual(overrides["override_document_type_id"], self.dt.pk)
                self.assertEqual(
                    overrides["override_tag_ids"],
                    [self.t1.pk, self.t2.pk, self.t3.pk],
                )
                self.assertEqual(overrides["override_storage_path_id"], self.sp.pk)
                self.assertEqual(overrides["override_owner_id"], self.user2.pk)
                self.assertEqual(overrides["override_view_users"], [self.user3.pk])
                self.assertEqual(overrides["override_view_groups"], [self.group1.pk])
                self.assertEqual(overrides["override_change_users"], [self.user3.pk])
                self.assertEqual(overrides["override_change_groups"], [self.group1.pk])
                self.assertEqual(
                    overrides["override_title"],
                    "Doc from {correspondent}",
                )
                self.assertEqual(
                    overrides["override_custom_field_ids"],
                    [self.cf1.pk, self.cf2.pk],
                )

        info = cm.output[0]
        expected_str = f"Document matched template {ct}"
        self.assertIn(expected_str, info)

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_match_mailrule(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that matches is consumed via mail rule
        THEN:
            - Template overrides are applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_mailrule=self.rule1,
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        ct.assign_tags.add(self.t1)
        ct.assign_tags.add(self.t2)
        ct.assign_tags.add(self.t3)
        ct.assign_view_users.add(self.user3.pk)
        ct.assign_view_groups.add(self.group1.pk)
        ct.assign_change_users.add(self.user3.pk)
        ct.assign_change_groups.add(self.group1.pk)
        ct.save()

        self.assertEqual(ct.__str__(), "Template 1")

        test_file = self.SAMPLE_DIR / "simple.pdf"
        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                        mailrule_id=self.rule1.pk,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertEqual(overrides["override_correspondent_id"], self.c.pk)
                self.assertEqual(overrides["override_document_type_id"], self.dt.pk)
                self.assertEqual(
                    overrides["override_tag_ids"],
                    [self.t1.pk, self.t2.pk, self.t3.pk],
                )
                self.assertEqual(overrides["override_storage_path_id"], self.sp.pk)
                self.assertEqual(overrides["override_owner_id"], self.user2.pk)
                self.assertEqual(overrides["override_view_users"], [self.user3.pk])
                self.assertEqual(overrides["override_view_groups"], [self.group1.pk])
                self.assertEqual(overrides["override_change_users"], [self.user3.pk])
                self.assertEqual(overrides["override_change_groups"], [self.group1.pk])
                self.assertEqual(
                    overrides["override_title"],
                    "Doc from {correspondent}",
                )

        info = cm.output[0]
        expected_str = f"Document matched template {ct}"
        self.assertIn(expected_str, info)

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_match_multiple(self, m):
        """
        GIVEN:
            - Multiple existing consumption template
        WHEN:
            - File that matches is consumed
        THEN:
            - Template overrides are applied with subsequent templates only overwriting empty values
            or merging if multiple
        """
        ct1 = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*/samples/*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
        )
        ct1.assign_tags.add(self.t1)
        ct1.assign_tags.add(self.t2)
        ct1.assign_view_users.add(self.user2)
        ct1.save()
        ct2 = ConsumptionTemplate.objects.create(
            name="Template 2",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c2,
            assign_storage_path=self.sp,
        )
        ct2.assign_tags.add(self.t3)
        ct1.assign_view_users.add(self.user3)
        ct2.save()

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                # template 1
                self.assertEqual(overrides["override_correspondent_id"], self.c.pk)
                self.assertEqual(overrides["override_document_type_id"], self.dt.pk)
                # template 2
                self.assertEqual(overrides["override_storage_path_id"], self.sp.pk)
                # template 1 & 2
                self.assertEqual(
                    overrides["override_tag_ids"],
                    [self.t1.pk, self.t2.pk, self.t3.pk],
                )
                self.assertEqual(
                    overrides["override_view_users"],
                    [self.user2.pk, self.user3.pk],
                )

        expected_str = f"Document matched template {ct1}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document matched template {ct2}"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_no_match_filename(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that does not match on filename is consumed
        THEN:
            - Template overrides are not applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*foobar*",
            filter_path=None,
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertIsNone(overrides["override_correspondent_id"])
                self.assertIsNone(overrides["override_document_type_id"])
                self.assertIsNone(overrides["override_tag_ids"])
                self.assertIsNone(overrides["override_storage_path_id"])
                self.assertIsNone(overrides["override_owner_id"])
                self.assertIsNone(overrides["override_view_users"])
                self.assertIsNone(overrides["override_view_groups"])
                self.assertIsNone(overrides["override_change_users"])
                self.assertIsNone(overrides["override_change_groups"])
                self.assertIsNone(overrides["override_title"])

        expected_str = f"Document did not match template {ct}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document filename {test_file.name} does not match"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_no_match_path(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that does not match on path is consumed
        THEN:
            - Template overrides are not applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*foo/bar*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertIsNone(overrides["override_correspondent_id"])
                self.assertIsNone(overrides["override_document_type_id"])
                self.assertIsNone(overrides["override_tag_ids"])
                self.assertIsNone(overrides["override_storage_path_id"])
                self.assertIsNone(overrides["override_owner_id"])
                self.assertIsNone(overrides["override_view_users"])
                self.assertIsNone(overrides["override_view_groups"])
                self.assertIsNone(overrides["override_change_users"])
                self.assertIsNone(overrides["override_change_groups"])
                self.assertIsNone(overrides["override_title"])

        expected_str = f"Document did not match template {ct}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document path {test_file} does not match"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_no_match_mail_rule(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that does not match on source is consumed
        THEN:
            - Template overrides are not applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_mailrule=self.rule1,
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                        mailrule_id=99,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertIsNone(overrides["override_correspondent_id"])
                self.assertIsNone(overrides["override_document_type_id"])
                self.assertIsNone(overrides["override_tag_ids"])
                self.assertIsNone(overrides["override_storage_path_id"])
                self.assertIsNone(overrides["override_owner_id"])
                self.assertIsNone(overrides["override_view_users"])
                self.assertIsNone(overrides["override_view_groups"])
                self.assertIsNone(overrides["override_change_users"])
                self.assertIsNone(overrides["override_change_groups"])
                self.assertIsNone(overrides["override_title"])

        expected_str = f"Document did not match template {ct}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = "Document mail rule 99 !="
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_no_match_source(self, m):
        """
        GIVEN:
            - Existing consumption template
        WHEN:
            - File that does not match on source is consumed
        THEN:
            - Template overrides are not applied
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*",
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ApiUpload,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertIsNone(overrides["override_correspondent_id"])
                self.assertIsNone(overrides["override_document_type_id"])
                self.assertIsNone(overrides["override_tag_ids"])
                self.assertIsNone(overrides["override_storage_path_id"])
                self.assertIsNone(overrides["override_owner_id"])
                self.assertIsNone(overrides["override_view_users"])
                self.assertIsNone(overrides["override_view_groups"])
                self.assertIsNone(overrides["override_change_users"])
                self.assertIsNone(overrides["override_change_groups"])
                self.assertIsNone(overrides["override_title"])

        expected_str = f"Document did not match template {ct}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document source {DocumentSource.ApiUpload.name} not in ['{DocumentSource.ConsumeFolder.name}', '{DocumentSource.MailFetch.name}']"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consumption_template_repeat_custom_fields(self, m):
        """
        GIVEN:
            - Existing consumption templates which assign the same custom field
        WHEN:
            - File that matches is consumed
        THEN:
            - Custom field is added the first time successfully
        """
        ct = ConsumptionTemplate.objects.create(
            name="Template 1",
            order=0,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
        )
        ct.assign_custom_fields.add(self.cf1.pk)
        ct.save()

        ct2 = ConsumptionTemplate.objects.create(
            name="Template 2",
            order=1,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
        )
        ct2.assign_custom_fields.add(self.cf1.pk)
        ct2.save()

        test_file = self.SAMPLE_DIR / "simple.pdf"

        with mock.patch("documents.tasks.async_to_sync"):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                m.assert_called_once()
                _, overrides = m.call_args
                self.assertEqual(
                    overrides["override_custom_field_ids"],
                    [self.cf1.pk],
                )

        expected_str = f"Document matched template {ct}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document matched template {ct2}"
        self.assertIn(expected_str, cm.output[1])
