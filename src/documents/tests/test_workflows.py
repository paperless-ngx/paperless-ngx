import shutil
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest import mock

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_groups_with_perms
from guardian.shortcuts import get_users_with_perms
from httpx import HTTPStatusError
from rest_framework.test import APITestCase

from documents.signals.handlers import run_workflows
from documents.signals.handlers import send_webhook

if TYPE_CHECKING:
    from django.db.models import QuerySet


from documents import tasks
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.matching import document_matches_workflow
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowActionEmail
from documents.models import WorkflowActionWebhook
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from documents.signals import document_consumption_finished
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DummyProgressManager
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import SampleDirMixin
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestWorkflows(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    APITestCase,
):
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
        self.group2 = Group.objects.create(name="group2")

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

    def test_workflow_match(self):
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
            filter_path=f"*/{self.dirs.scratch_dir.parts[-1]}/*",
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )

                document = Document.objects.first()
                self.assertEqual(document.correspondent, self.c)
                self.assertEqual(document.document_type, self.dt)
                self.assertEqual(list(document.tags.all()), [self.t1, self.t2, self.t3])
                self.assertEqual(document.storage_path, self.sp)
                self.assertEqual(document.owner, self.user2)
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["view_document"],
                        ),
                    ),
                    [self.user3],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group1],
                )
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["change_document"],
                        ),
                    ),
                    [self.user3],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group1],
                )
                self.assertEqual(
                    document.title,
                    f"Doc from {self.c.name}",
                )
                self.assertEqual(
                    list(document.custom_fields.all().values_list("field", flat=True)),
                    [self.cf1.pk, self.cf2.pk],
                )

        info = cm.output[0]
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    def test_workflow_match_mailrule(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                        mailrule_id=self.rule1.pk,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertEqual(document.correspondent, self.c)
                self.assertEqual(document.document_type, self.dt)
                self.assertEqual(list(document.tags.all()), [self.t1, self.t2, self.t3])
                self.assertEqual(document.storage_path, self.sp)
                self.assertEqual(document.owner, self.user2)
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["view_document"],
                        ),
                    ),
                    [self.user3],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group1],
                )
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["change_document"],
                        ),
                    ),
                    [self.user3],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group1],
                )
                self.assertEqual(
                    document.title,
                    f"Doc from {self.c.name}",
                )
        info = cm.output[0]
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    def test_workflow_match_multiple(self):
        """
        GIVEN:
            - Multiple existing workflows
        WHEN:
            - File that matches is consumed
        THEN:
            - Workflow overrides are applied with subsequent workflows overwriting previous values
            or merging if multiple
        """
        trigger1 = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload},{DocumentSource.ConsumeFolder},{DocumentSource.MailFetch}",
            filter_path=f"*/{self.dirs.scratch_dir.parts[-1]}/*",
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                # workflow 1
                self.assertEqual(document.document_type, self.dt)
                # workflow 2
                self.assertEqual(document.correspondent, self.c2)
                self.assertEqual(document.storage_path, self.sp)
                # workflow 1 & 2
                self.assertEqual(
                    list(document.tags.all()),
                    [self.t1, self.t2, self.t3],
                )
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["view_document"],
                        ),
                    ),
                    [self.user2, self.user3],
                )

        expected_str = f"Document matched {trigger1} from {w1}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document matched {trigger2} from {w2}"
        self.assertIn(expected_str, cm.output[1])

    def test_workflow_fnmatch_path(self):
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
            filter_path=f"*{self.dirs.scratch_dir.parts[-1]}*",
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertEqual(document.title, "Doc fnmatch title")

        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, cm.output[0])

    def test_workflow_no_match_filename(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(document.tags.all().count(), 0)
                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["view_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(get_groups_with_perms(document).count(), 0)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["change_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(get_groups_with_perms(document).count(), 0)
                self.assertEqual(document.title, "simple")

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document filename {test_file.name} does not match"
        self.assertIn(expected_str, cm.output[1])

    def test_workflow_no_match_path(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(document.tags.all().count(), 0)
                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["view_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["change_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(document.title, "simple")

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = f"Document path {test_file} does not match"
        self.assertIn(expected_str, cm.output[1])

    def test_workflow_no_match_mail_rule(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                        mailrule_id=99,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(document.tags.all().count(), 0)
                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["view_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["change_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(document.title, "simple")

        expected_str = f"Document did not match {w}"
        self.assertIn(expected_str, cm.output[0])
        expected_str = "Document mail rule 99 !="
        self.assertIn(expected_str, cm.output[1])

    def test_workflow_no_match_source(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="DEBUG") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ApiUpload,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(document.tags.all().count(), 0)
                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["view_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["change_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(document.title, "simple")

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

    def test_workflow_repeat_custom_fields(self):
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertEqual(
                    list(document.custom_fields.all().values_list("field", flat=True)),
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

    def test_document_added_invalid_title_placeholders(self):
        """
        GIVEN:
            - Existing workflow with added trigger type
            - Assign title field has an error
        WHEN:
            - File that matches is added
        THEN:
            - Title is not updated, error is output
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*sample*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc {created_year]",
        )
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
            original_filename="sample.pdf",
            title="sample test",
            content="Hello world bar",
            created=created,
        )

        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Error occurred parsing title assignment '{action.assign_title}', falling back to original"
            self.assertIn(expected_str, cm.output[0])

        self.assertEqual(doc.title, "sample test")

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

    def test_document_updated_workflow_existing_custom_field(self):
        """
        GIVEN:
            - Existing workflow with UPDATED trigger and action that adds a custom field
        WHEN:
            - Document is updated that already contains the field
        THEN:
            - Document update succeeds without trying to re-create the field
        """
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
        CustomFieldInstance.objects.create(document=doc, field=self.cf1)

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"document_type": self.dt.id},
            format="json",
        )

    def test_document_updated_workflow_merge_permissions(self):
        """
        GIVEN:
            - Existing workflow with UPDATED trigger and action that sets permissions
        WHEN:
            - Document is updated that already has permissions
        THEN:
            - Permissions are merged
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_has_document_type=self.dt,
        )
        action = WorkflowAction.objects.create()
        action.assign_view_users.add(self.user3)
        action.assign_change_users.add(self.user3)
        action.assign_view_groups.add(self.group2)
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

        assign_perm("documents.view_document", self.user2, doc)
        assign_perm("documents.change_document", self.user2, doc)
        assign_perm("documents.view_document", self.group1, doc)
        assign_perm("documents.change_document", self.group1, doc)

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"document_type": self.dt.id},
            format="json",
        )

        view_users_perms: QuerySet = get_users_with_perms(
            doc,
            only_with_perms_in=["view_document"],
        )
        change_users_perms: QuerySet = get_users_with_perms(
            doc,
            only_with_perms_in=["change_document"],
        )
        # user2 should still have permissions
        self.assertIn(self.user2, view_users_perms)
        self.assertIn(self.user2, change_users_perms)
        # user3 should have been added
        self.assertIn(self.user3, view_users_perms)
        self.assertIn(self.user3, change_users_perms)

        group_perms: QuerySet = get_groups_with_perms(doc)
        # group1 should still have permissions
        self.assertIn(self.group1, group_perms)
        # group2 should have been added
        self.assertIn(self.group2, group_perms)

    def test_workflow_scheduled_trigger_created(self):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the created field and action that assigns owner
            - Existing doc that matches the trigger
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow runs, document owner is updated
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=1,
            schedule_date_field="created",
        )
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

        now = timezone.localtime(timezone.now())
        created = now - timedelta(weeks=520)
        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            created=created,
        )

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    def test_workflow_scheduled_trigger_added(self):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the added field and action that assigns owner
            - Existing doc that matches the trigger
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow runs, document owner is updated
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=1,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.ADDED,
        )
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

        added = timezone.now() - timedelta(days=365)
        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            added=added,
        )

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    @mock.patch("documents.models.Document.objects.filter", autospec=True)
    def test_workflow_scheduled_trigger_modified(self, mock_filter):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the modified field and action that assigns owner
            - Existing doc that matches the trigger
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow runs, document owner is updated
        """
        # we have to mock because modified field is auto_now
        mock_filter.return_value = Document.objects.all()
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=1,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.MODIFIED,
        )
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

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    def test_workflow_scheduled_trigger_custom_field(self):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against a custom field and action that assigns owner
            - Existing doc that matches the trigger
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow runs, document owner is updated
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=1,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CUSTOM_FIELD,
            schedule_date_custom_field=self.cf1,
        )
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
        CustomFieldInstance.objects.create(
            document=doc,
            field=self.cf1,
            value_date=timezone.now() - timedelta(days=2),
        )

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    def test_workflow_scheduled_already_run(self):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger
            - Existing doc that has already had the workflow run
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow does not run again
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=1,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CREATED,
        )
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
            created=timezone.now() - timedelta(days=2),
        )

        wr = WorkflowRun.objects.create(
            workflow=w,
            document=doc,
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            run_at=timezone.now(),
        )
        self.assertEqual(
            str(wr),
            f"WorkflowRun of {w} at {wr.run_at} on {doc}",
        )  # coverage

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertIsNone(doc.owner)

    def test_workflow_scheduled_trigger_too_early(self):
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger and recurring interval of 7 days
            - Workflow run date is 6 days ago
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - Workflow does not run as the offset is not met
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=30,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CREATED,
            schedule_is_recurring=True,
            schedule_recurring_interval_days=7,
        )
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
            created=timezone.now() - timedelta(days=40),
        )

        WorkflowRun.objects.create(
            workflow=w,
            document=doc,
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            run_at=timezone.now() - timedelta(days=6),
        )

        with self.assertLogs(level="DEBUG") as cm:
            tasks.check_scheduled_workflows()
            self.assertIn(
                "last run was within the recurring interval",
                " ".join(cm.output),
            )

            doc.refresh_from_db()
            self.assertIsNone(doc.owner)

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
            type=99,
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
        self.assertRaises(Exception, document_matches_workflow, doc, w, 99)

    def test_removal_action_document_updated_workflow(self):
        """
        GIVEN:
            - Workflow with removal action
        WHEN:
            - File that matches is updated
        THEN:
            - Action removals are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_path="*",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        action.remove_correspondents.add(self.c)
        action.remove_tags.add(self.t1)
        action.remove_document_types.add(self.dt)
        action.remove_storage_paths.add(self.sp)
        action.remove_owners.add(self.user2)
        action.remove_custom_fields.add(self.cf1)
        action.remove_view_users.add(self.user3)
        action.remove_view_groups.add(self.group1)
        action.remove_change_users.add(self.user3)
        action.remove_change_groups.add(self.group1)
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
            document_type=self.dt,
            storage_path=self.sp,
            owner=self.user2,
            original_filename="sample.pdf",
        )
        doc.tags.set([self.t1, self.t2])
        CustomFieldInstance.objects.create(document=doc, field=self.cf1)
        doc.save()
        assign_perm("documents.view_document", self.user3, doc)
        assign_perm("documents.change_document", self.user3, doc)
        assign_perm("documents.view_document", self.group1, doc)
        assign_perm("documents.change_document", self.group1, doc)

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"title": "new title"},
            format="json",
        )
        doc.refresh_from_db()

        self.assertIsNone(doc.document_type)
        self.assertIsNone(doc.correspondent)
        self.assertIsNone(doc.storage_path)
        self.assertEqual(doc.tags.all().count(), 1)
        self.assertIn(self.t2, doc.tags.all())
        self.assertIsNone(doc.owner)
        self.assertEqual(doc.custom_fields.all().count(), 0)
        self.assertFalse(self.user3.has_perm("documents.view_document", doc))
        self.assertFalse(self.user3.has_perm("documents.change_document", doc))
        group_perms: QuerySet = get_groups_with_perms(doc)
        self.assertNotIn(self.group1, group_perms)

    def test_removal_action_document_updated_removeall(self):
        """
        GIVEN:
            - Workflow with removal action with remove all fields set
        WHEN:
            - File that matches is updated
        THEN:
            - Action removals are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_path="*",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
            remove_all_correspondents=True,
            remove_all_tags=True,
            remove_all_document_types=True,
            remove_all_storage_paths=True,
            remove_all_custom_fields=True,
            remove_all_owners=True,
            remove_all_permissions=True,
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
            document_type=self.dt,
            storage_path=self.sp,
            owner=self.user2,
            original_filename="sample.pdf",
        )
        doc.tags.set([self.t1, self.t2])
        CustomFieldInstance.objects.create(document=doc, field=self.cf1)
        doc.save()
        assign_perm("documents.view_document", self.user3, doc)
        assign_perm("documents.change_document", self.user3, doc)
        assign_perm("documents.view_document", self.group1, doc)
        assign_perm("documents.change_document", self.group1, doc)

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"title": "new title"},
            format="json",
        )
        doc.refresh_from_db()

        self.assertIsNone(doc.document_type)
        self.assertIsNone(doc.correspondent)
        self.assertIsNone(doc.storage_path)
        self.assertEqual(doc.tags.all().count(), 0)
        self.assertEqual(doc.tags.all().count(), 0)
        self.assertIsNone(doc.owner)
        self.assertEqual(doc.custom_fields.all().count(), 0)
        self.assertFalse(self.user3.has_perm("documents.view_document", doc))
        self.assertFalse(self.user3.has_perm("documents.change_document", doc))
        group_perms: QuerySet = get_groups_with_perms(doc)
        self.assertNotIn(self.group1, group_perms)

    def test_removal_action_document_consumed(self):
        """
        GIVEN:
            - Workflow with assignment and removal actions
        WHEN:
            - File that matches is consumed
        THEN:
            - Action removals are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            filter_filename="*simple*",
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
        action.assign_view_users.add(self.user2)
        action.assign_view_users.add(self.user3)
        action.assign_view_groups.add(self.group1)
        action.assign_view_groups.add(self.group2)
        action.assign_change_users.add(self.user2)
        action.assign_change_users.add(self.user3)
        action.assign_change_groups.add(self.group1)
        action.assign_change_groups.add(self.group2)
        action.assign_custom_fields.add(self.cf1)
        action.assign_custom_fields.add(self.cf2)
        action.save()

        action2 = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        action2.remove_correspondents.add(self.c)
        action2.remove_tags.add(self.t1)
        action2.remove_document_types.add(self.dt)
        action2.remove_storage_paths.add(self.sp)
        action2.remove_owners.add(self.user2)
        action2.remove_custom_fields.add(self.cf1)
        action2.remove_view_users.add(self.user3)
        action2.remove_change_users.add(self.user3)
        action2.remove_view_groups.add(self.group1)
        action2.remove_change_groups.add(self.group1)
        action2.save()

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.actions.add(action2)
        w.save()

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )

                document = Document.objects.first()

                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(
                    list(document.tags.all()),
                    [self.t2, self.t3],
                )
                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["view_document"],
                        ),
                    ),
                    [self.user2],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group2],
                )
                self.assertEqual(
                    list(
                        get_users_with_perms(
                            document,
                            only_with_perms_in=["change_document"],
                        ),
                    ),
                    [self.user2],
                )
                self.assertEqual(
                    list(
                        get_groups_with_perms(
                            document,
                        ),
                    ),
                    [self.group2],
                )
                self.assertEqual(
                    document.title,
                    "Doc from None",
                )
                self.assertEqual(
                    list(document.custom_fields.all().values_list("field", flat=True)),
                    [self.cf2.pk],
                )

        info = cm.output[0]
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    def test_removal_action_document_consumed_remove_all(self):
        """
        GIVEN:
            - Workflow with assignment and removal actions with remove all fields set
        WHEN:
            - File that matches is consumed
        THEN:
            - Action removals are applied
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            filter_filename="*simple*",
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

        action2 = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
            remove_all_correspondents=True,
            remove_all_tags=True,
            remove_all_document_types=True,
            remove_all_storage_paths=True,
            remove_all_custom_fields=True,
            remove_all_owners=True,
            remove_all_permissions=True,
        )

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.actions.add(action2)
        w.save()

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO") as cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )
                document = Document.objects.first()
                self.assertIsNone(document.correspondent)
                self.assertIsNone(document.document_type)
                self.assertEqual(document.tags.all().count(), 0)

                self.assertIsNone(document.storage_path)
                self.assertIsNone(document.owner)
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["view_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_users_with_perms(
                        document,
                        only_with_perms_in=["change_document"],
                    ).count(),
                    0,
                )
                self.assertEqual(
                    get_groups_with_perms(
                        document,
                    ).count(),
                    0,
                )
                self.assertEqual(
                    document.custom_fields.all()
                    .values_list(
                        "field",
                    )
                    .count(),
                    0,
                )

        info = cm.output[0]
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    def test_workflow_with_tag_actions_doesnt_overwrite_other_actions(self):
        """
        GIVEN:
            - Document updated workflow filtered by has tag with two actions, first adds owner, second removes a tag
        WHEN:
            - File that matches is consumed
        THEN:
            - Both actions are applied correctly
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        trigger.filter_has_tags.add(self.t1)
        action1 = WorkflowAction.objects.create(
            assign_owner=self.user2,
        )
        action2 = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        action2.remove_tags.add(self.t1)
        w = Workflow.objects.create(
            name="Workflow Add Owner and Remove Tag",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action1)
        w.actions.add(action2)
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
            {"tags": [self.t1.id, self.t2.id]},
            format="json",
        )

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)
        self.assertEqual(doc.tags.all().count(), 1)
        self.assertIn(self.t2, doc.tags.all())

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("httpx.post")
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_action(self, mock_email_send, mock_post):
        """
        GIVEN:
            - Document updated workflow with email action
        WHEN:
            - Document that matches is updated
        THEN:
            - email is sent
        """
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
        )
        mock_email_send.return_value = 1

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        email_action = WorkflowActionEmail.objects.create(
            subject="Test Notification: {doc_title}",
            body="Test message: {doc_url}",
            to="user@example.com",
            include_document=False,
        )
        self.assertEqual(str(email_action), f"Workflow Email Action {email_action.id}")
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EMAIL,
            email=email_action,
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

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

        mock_email_send.assert_called_once()

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("httpx.post")
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_include_file(self, mock_email_send, mock_post):
        """
        GIVEN:
            - Document updated workflow with email action
            - Include document is set to True
        WHEN:
            - Document that matches is updated
        THEN:
            - Notification includes document file
        """

        # move the file
        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        email_action = WorkflowActionEmail.objects.create(
            subject="Test Notification: {doc_title}",
            body="Test message: {doc_url}",
            to="me@example.com",
            include_document=True,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EMAIL,
            email=email_action,
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
            filename=test_file,
        )

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

        mock_email_send.assert_called_once()

    @override_settings(
        EMAIL_ENABLED=False,
    )
    def test_workflow_email_action_no_email_setup(self):
        """
        GIVEN:
            - Document updated workflow with email action
            - Email is not enabled
        WHEN:
            - Document that matches is updated
        THEN:
            - Error is logged
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        email_action = WorkflowActionEmail.objects.create(
            subject="Test Notification: {doc_title}",
            body="Test message: {doc_url}",
            to="me@example.com",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EMAIL,
            email=email_action,
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

        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Email backend has not been configured"
            self.assertIn(expected_str, cm.output[0])

    @override_settings(
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_action_fail(self, mock_email_send):
        """
        GIVEN:
            - Document updated workflow with email action
        WHEN:
            - Document that matches is updated
            - An error occurs during email send
        THEN:
            - Error is logged
        """
        mock_email_send.side_effect = Exception("Error occurred sending email")
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        email_action = WorkflowActionEmail.objects.create(
            subject="Test Notification: {doc_title}",
            body="Test message: {doc_url}",
            to="me@example.com",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EMAIL,
            email=email_action,
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

        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred sending email"
            self.assertIn(expected_str, cm.output[0])

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("documents.signals.handlers.send_webhook.delay")
    def test_workflow_webhook_action_body(self, mock_post):
        """
        GIVEN:
            - Document updated workflow with webhook action which uses body
        WHEN:
            - Document that matches is updated
        THEN:
            - Webhook is sent with body
        """
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
        )

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        webhook_action = WorkflowActionWebhook.objects.create(
            use_params=False,
            body="Test message: {doc_url}",
            url="http://paperless-ngx.com",
            include_document=False,
        )
        self.assertEqual(
            str(webhook_action),
            f"Workflow Webhook Action {webhook_action.id}",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.WEBHOOK,
            webhook=webhook_action,
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

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

        mock_post.assert_called_once_with(
            url="http://paperless-ngx.com",
            data=f"Test message: http://localhost:8000/documents/{doc.id}/",
            headers={},
            files=None,
        )

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("documents.signals.handlers.send_webhook.delay")
    def test_workflow_webhook_action_w_files(self, mock_post):
        """
        GIVEN:
            - Document updated workflow with webhook action which includes document
        WHEN:
            - Document that matches is updated
        THEN:
            - Webhook is sent with file
        """
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
        )

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        webhook_action = WorkflowActionWebhook.objects.create(
            use_params=False,
            body="Test message: {doc_url}",
            url="http://paperless-ngx.com",
            include_document=True,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.WEBHOOK,
            webhook=webhook_action,
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="simple.pdf",
            filename=test_file,
            mime_type="application/pdf",
        )

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

        mock_post.assert_called_once_with(
            url="http://paperless-ngx.com",
            data=f"Test message: http://localhost:8000/documents/{doc.id}/",
            headers={},
            files={"file": ("simple.pdf", mock.ANY, "application/pdf")},
        )

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    def test_workflow_webhook_action_fail(self):
        """
        GIVEN:
            - Document updated workflow with webhook action
        WHEN:
            - Document that matches is updated
            - An error occurs during webhook
        THEN:
            - Error is logged
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        webhook_action = WorkflowActionWebhook.objects.create(
            use_params=True,
            params={
                "title": "Test webhook: {doc_title}",
                "body": "Test message: {doc_url}",
            },
            url="http://paperless-ngx.com",
            include_document=True,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.WEBHOOK,
            webhook=webhook_action,
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

        # fails because no file
        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred sending webhook"
            self.assertIn(expected_str, cm.output[0])

    def test_workflow_webhook_action_url_invalid_params_headers(self):
        """
        GIVEN:
            - Document updated workflow with webhook action
            - Invalid params and headers JSON
        WHEN:
            - Document that matches is updated
        THEN:
            - Error is logged
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        webhook_action = WorkflowActionWebhook.objects.create(
            url="http://paperless-ngx.com",
            use_params=True,
            params="invalid",
            headers="invalid",
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.WEBHOOK,
            webhook=webhook_action,
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

        with self.assertLogs("paperless.handlers", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred parsing webhook params"
            self.assertIn(expected_str, cm.output[0])
            expected_str = "Error occurred parsing webhook headers"
            self.assertIn(expected_str, cm.output[1])

    @mock.patch("httpx.post")
    def test_workflow_webhook_send_webhook_task(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
            raise_for_status=mock.Mock(),
        )

        with self.assertLogs("paperless.handlers") as cm:
            send_webhook(
                url="http://paperless-ngx.com",
                data="Test message",
                headers={},
                files=None,
            )

            mock_post.assert_called_once_with(
                "http://paperless-ngx.com",
                data="Test message",
                headers={},
                files=None,
            )

            expected_str = "Webhook sent to http://paperless-ngx.com"
            self.assertIn(expected_str, cm.output[0])

    @mock.patch("httpx.post")
    def test_workflow_webhook_send_webhook_retry(self, mock_http):
        mock_http.return_value.raise_for_status = mock.Mock(
            side_effect=HTTPStatusError(
                "Error",
                request=mock.Mock(),
                response=mock.Mock(),
            ),
        )

        with self.assertLogs("paperless.handlers") as cm:
            with self.assertRaises(HTTPStatusError):
                send_webhook(
                    url="http://paperless-ngx.com",
                    data="Test message",
                    headers={},
                    files=None,
                )

                self.assertEqual(mock_http.call_count, 1)

                expected_str = (
                    "Failed attempt sending webhook to http://paperless-ngx.com"
                )
                self.assertIn(expected_str, cm.output[0])
