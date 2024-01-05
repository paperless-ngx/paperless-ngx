from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from documents import tasks
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.matching import document_matches_workflow
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.signals import document_consumption_finished
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestWorkflows(DirectoriesMixin, FileSystemAssertsMixin, APITestCase):
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
    def test_workflow_match(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that matches is consumed
        THEN:
            - Template overrides are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
            filter_path="*/samples/*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.assign_tags.add(self.t1)
        action.assign_tags.add(self.t2)
        action.assign_tags.add(self.t3)
        action.assign_view_users.add(self.user3.pk)
        action.assign_view_groups.add(self.group1.pk)
        action.assign_change_users.add(self.user3.pk)
        action.assign_change_groups.add(self.group1.pk)
        action.assign_custom_fields.add(self.cf1.pk)
        action.assign_custom_fields.add(self.cf2.pk)
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        self.assertEqual(w.__str__(), "Workflow: Workflow 1")
        self.assertEqual(trigger.__str__(), "WorkflowTrigger 1")
        self.assertEqual(action.__str__(), "WorkflowAction 1")

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
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_match_mailrule(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that matches is consumed via mail rule
        THEN:
            - Template overrides are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_mailrule=self.rule1,
        )

        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.assign_tags.add(self.t1)
        action.assign_tags.add(self.t2)
        action.assign_tags.add(self.t3)
        action.assign_view_users.add(self.user3.pk)
        action.assign_view_groups.add(self.group1.pk)
        action.assign_change_users.add(self.user3.pk)
        action.assign_change_groups.add(self.group1.pk)
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_match_multiple(self, m):
        """
        GIVEN:
            - Multiple existing workflow
        WHEN:
            - File that matches is consumed
        THEN:
            - Template overrides are applied with subsequent templates overwriting previous values
            or merging if multiple
        """
        trigger1 = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*/samples/*",
        )
        action1 = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
        )
        action1.assign_tags.add(self.t1)
        action1.assign_tags.add(self.t2)
        action1.assign_view_users.add(self.user2)
        action1.save()

        w1 = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w1.triggers.add(trigger1)
        w1.actions.add(action1)
        w1.save()

        trigger2 = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
        )
        action2 = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c2,
            assign_storage_path=self.sp,
        )
        action2.assign_tags.add(self.t3)
        action2.assign_view_users.add(self.user3)
        action2.save()

        w2 = Workflow.objects.create(
            name="Workflow 2",
            order=0,
        )
        w2.triggers.add(trigger2)
        w2.actions.add(action2)
        w2.save()

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
                self.assertEqual(overrides["override_document_type_id"], self.dt.pk)
                # template 2
                self.assertEqual(overrides["override_correspondent_id"], self.c2.pk)
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

        expected_str = f"Document matched {trigger1} from {w1}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document matched {trigger2} from {w2}"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_fnmatch_path(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that matches using fnmatch on path is consumed
        THEN:
            - Template overrides are applied
            - Note: Test was added when path matching changed from pathlib.match to fnmatch
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*sample*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc fnmatch title",
        )
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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
                self.assertEqual(overrides["override_title"], "Doc fnmatch title")

        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, cm.output[0])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_no_match_filename(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that does not match on filename is consumed
        THEN:
            - Template overrides are not applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*foobar*",
            filter_path=None,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document filename {test_file.name} does not match"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_no_match_path(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that does not match on path is consumed
        THEN:
            - Template overrides are not applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*foo/bar*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document path {test_file} does not match"
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_no_match_mail_rule(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that does not match on source is consumed
        THEN:
            - Template overrides are not applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_mailrule=self.rule1,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = "Document mail rule 99 !="
        self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_no_match_source(self, m):
        """
        GIVEN:
            - Existing workflow
        WHEN:
            - File that does not match on source is consumed
        THEN:
            - Template overrides are not applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path="*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc from {correspondent}",
            assign_correspondent=self.c,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

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

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document source {DocumentSource.ApiUpload.name} not in ['{DocumentSource.ConsumeFolder.name}', '{DocumentSource.MailFetch.name}']"
        self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_trigger_type(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )
        doc.save()

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_matches_workflow(
                doc,
                w,
                WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"No matching triggers with type {WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED} found"
            self.assertIn(expected_str, cm.output[1])

    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_workflow_repeat_custom_fields(self, m):
        """
        GIVEN:
            - Existing workflows which assign the same custom field
        WHEN:
            - File that matches is consumed
        THEN:
            - Custom field is added the first time successfully
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_filename="*simple*",
        )
        action1 = WorkflowAction.objects.create()
        action1.assign_custom_fields.add(self.cf1.pk)
        action1.save()

        action2 = WorkflowAction.objects.create()
        action2.assign_custom_fields.add(self.cf1.pk)
        action2.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action1, action2)
        w.save()

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

        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, cm.output[0])

    def test_document_added_workflow(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*sample*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc created in {created_year}",
            assign_correspondent=self.c2,
            assign_document_type=self.dt,
            assign_storage_path=self.sp,
            assign_owner=self.user2,
        )
        action.assign_tags.add(self.t1)
        action.assign_tags.add(self.t2)
        action.assign_tags.add(self.t3)
        action.assign_view_users.add(self.user3.pk)
        action.assign_view_groups.add(self.group1.pk)
        action.assign_change_users.add(self.user3.pk)
        action.assign_change_groups.add(self.group1.pk)
        action.assign_custom_fields.add(self.cf1.pk)
        action.assign_custom_fields.add(self.cf2.pk)
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        now = timezone.localtime(timezone.now())
        created = now - timedelta(weeks=520)
        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            added=now,
            created=created,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )

        self.assertEqual(doc.correspondent, self.c2)
        self.assertEqual(doc.title, f"Doc created in {created.year}")

    def test_document_added_no_match_filename(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*foobar*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )
        doc.tags.set([self.t3])
        doc.save()

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document filename {doc.original_filename} does not match"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_match_content_matching(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            matching_algorithm=MatchingModel.MATCH_LITERAL,
            match="foo",
            is_insensitive=True,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc content matching worked",
            assign_owner=self.user2,
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            content="Hello world foo bar",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"WorkflowTrigger {trigger} matched on document"
            expected_str2 = 'because it contains this string: "foo"'
            self.assertIn(expected_str, cm.output[0])
            self.assertIn(expected_str2, cm.output[0])
            expected_str = f"Document matched {trigger} from {w}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_content_matching(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            matching_algorithm=MatchingModel.MATCH_LITERAL,
            match="foo",
            is_insensitive=True,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc content matching worked",
            assign_owner=self.user2,
        )
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            content="Hello world bar",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document content matching settings for algorithm '{trigger.matching_algorithm}' did not match"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_tags(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_tags.set([self.t1, self.t2])
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )
        doc.tags.set([self.t3])
        doc.save()

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document tags {doc.tags.all()} do not include {trigger.filter_has_tags.all()}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_doctype(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_has_document_type=self.dt,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            original_filename="sample.pdf",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document doc type {doc.document_type} does not match {trigger.filter_has_document_type}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_correspondent(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_has_correspondent=self.c,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        action.save()
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c2,
            original_filename="sample.pdf",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document correspondent {doc.correspondent} does not match {trigger.filter_has_correspondent}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_updated_workflow(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_has_document_type=self.dt,
        )
        action = WorkflowAction.objects.create()
        action.assign_custom_fields.add(self.cf1)
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"document_type": self.dt.id},
            format="json",
        )

        self.assertEqual(doc.custom_fields.all().count(), 1)

    def test_workflow_enabled_disabled(self):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*sample*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Title assign correspondent",
            assign_correspondent=self.c2,
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
            enabled=False,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        action2 = WorkflowAction.objects.create(
            assign_title="Title assign owner",
            assign_owner=self.user2,
        )
        w2 = Workflow.objects.create(
            name="Workflow 2",
            order=0,
            enabled=True,
        )
        w2.triggers.add(trigger)
        w2.actions.add(action2)
        w2.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )

        self.assertEqual(doc.correspondent, self.c)
        self.assertEqual(doc.title, "Title assign owner")
        self.assertEqual(doc.owner, self.user2)

    def test_new_trigger_type_raises_exception(self):
        trigger = WorkflowTrigger.objects.create(
            type=4,
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        doc = Document.objects.create(
            title="test",
        )
        self.assertRaises(Exception, document_matches_workflow, doc, w, 4)
