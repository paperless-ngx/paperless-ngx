import datetime
import json
import shutil
import socket
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_groups_with_perms
from guardian.shortcuts import get_users_with_perms
from httpx import ConnectError
from httpx import HTTPError
from httpx import HTTPStatusError
from pytest_httpx import HTTPXMock
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.signals.handlers import run_workflows
from documents.workflows.webhooks import send_webhook

if TYPE_CHECKING:
    from django.db.models import QuerySet
from pytest_django.fixtures import SettingsWrapper

from documents import tasks
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.matching import document_matches_workflow
from documents.matching import existing_document_matches_workflow
from documents.matching import prefilter_documents_by_workflowtrigger
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
from documents.serialisers import WorkflowTriggerSerializer
from documents.signals import document_consumption_finished
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DummyProgressManager
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import SampleDirMixin
from documents.workflows.actions import execute_password_removal_action
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

    def test_workflow_match(self) -> None:
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
            assign_title="Doc from {{correspondent}}",
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
        action.assign_custom_fields_values = {
            self.cf2.pk: 42,
        }
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
                self.assertEqual(
                    document.custom_fields.get(field=self.cf2.pk).value,
                    42,
                )

        info = cm.output[0]
        expected_str = f"Document matched {trigger} from {w}"
        self.assertIn(expected_str, info)

    def test_workflow_match_mailrule(self) -> None:
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
            assign_title="Doc from {{correspondent}}",
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

    def test_workflow_match_multiple(self) -> None:
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

    def test_workflow_fnmatch_path(self) -> None:
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

    def test_workflow_no_match_filename(self) -> None:
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

    def test_workflow_no_match_path(self) -> None:
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

    def test_workflow_no_match_mail_rule(self) -> None:
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

    def test_workflow_no_match_source(self) -> None:
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

    def test_document_added_no_match_trigger_type(self) -> None:
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

    def test_workflow_repeat_custom_fields(self) -> None:
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

    def test_document_added_workflow(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*sample*",
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc created in {{created_year}}",
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

    def test_document_added_no_match_filename(self) -> None:
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

    def test_document_added_match_content_matching(self) -> None:
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

    def test_document_added_no_match_content_matching(self) -> None:
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

    def test_document_added_no_match_tags(self) -> None:
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
            expected_str = f"Document tags {list(doc.tags.all())} do not include {list(trigger.filter_has_tags.all())}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_no_match_all_tags(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_all_tags.set([self.t1, self.t2])
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
        doc.tags.set([self.t1])
        doc.save()

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = (
                f"Document tags {list(doc.tags.all())} do not contain all of"
                f" {list(trigger.filter_has_all_tags.all())}"
            )
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_excluded_tags(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_not_tags.set([self.t3])
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
            expected_str = (
                f"Document tags {list(doc.tags.all())} include excluded tags"
                f" {list(trigger.filter_has_not_tags.all())}"
            )
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_excluded_correspondent(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_not_correspondents.set([self.c])
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

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = (
                f"Document correspondent {doc.correspondent} is excluded by"
                f" {list(trigger.filter_has_not_correspondents.all())}"
            )
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_excluded_document_types(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_not_document_types.set([self.dt])
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
            document_type=self.dt,
            original_filename="sample.pdf",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = (
                f"Document doc type {doc.document_type} is excluded by"
                f" {list(trigger.filter_has_not_document_types.all())}"
            )
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_excluded_storage_paths(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_not_storage_paths.set([self.sp])
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
            storage_path=self.sp,
            original_filename="sample.pdf",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = (
                f"Document storage path {doc.storage_path} is excluded by"
                f" {list(trigger.filter_has_not_storage_paths.all())}"
            )
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_any_filters(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_any_correspondents.set([self.c])
        trigger.filter_has_any_document_types.set([self.dt])
        trigger.filter_has_any_storage_paths.set([self.sp])

        matching_doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            document_type=self.dt,
            storage_path=self.sp,
            original_filename="sample.pdf",
            checksum="checksum-any-match",
        )

        matched, reason = existing_document_matches_workflow(matching_doc, trigger)
        self.assertTrue(matched)
        self.assertIsNone(reason)

        wrong_correspondent = Document.objects.create(
            title="wrong correspondent",
            correspondent=self.c2,
            document_type=self.dt,
            storage_path=self.sp,
            original_filename="sample2.pdf",
        )
        matched, reason = existing_document_matches_workflow(
            wrong_correspondent,
            trigger,
        )
        self.assertFalse(matched)
        self.assertIn("correspondent", reason)

        other_document_type = DocumentType.objects.create(name="Other")
        wrong_document_type = Document.objects.create(
            title="wrong doc type",
            correspondent=self.c,
            document_type=other_document_type,
            storage_path=self.sp,
            original_filename="sample3.pdf",
            checksum="checksum-wrong-doc-type",
        )
        matched, reason = existing_document_matches_workflow(
            wrong_document_type,
            trigger,
        )
        self.assertFalse(matched)
        self.assertIn("doc type", reason)

        other_storage_path = StoragePath.objects.create(
            name="Other path",
            path="/other/",
        )
        wrong_storage_path = Document.objects.create(
            title="wrong storage",
            correspondent=self.c,
            document_type=self.dt,
            storage_path=other_storage_path,
            original_filename="sample4.pdf",
            checksum="checksum-wrong-storage-path",
        )
        matched, reason = existing_document_matches_workflow(
            wrong_storage_path,
            trigger,
        )
        self.assertFalse(matched)
        self.assertIn("storage path", reason)

    def test_document_added_custom_field_query_no_match(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query=json.dumps(
                [
                    "AND",
                    [[self.cf1.id, "exact", "expected"]],
                ],
            ),
        )
        action = WorkflowAction.objects.create(
            assign_title="Doc assign owner",
            assign_owner=self.user2,
        )
        workflow = Workflow.objects.create(name="Workflow 1", order=0)
        workflow.triggers.add(trigger)
        workflow.actions.add(action)
        workflow.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=self.cf1,
            value_text="other",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {workflow}"
            self.assertIn(expected_str, cm.output[0])
            self.assertIn(
                "Document custom fields do not match the configured custom field query",
                cm.output[1],
            )

    def test_document_added_custom_field_query_match(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query=json.dumps(
                [
                    "AND",
                    [[self.cf1.id, "exact", "expected"]],
                ],
            ),
        )
        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=self.cf1,
            value_text="expected",
        )

        matched, reason = existing_document_matches_workflow(doc, trigger)
        self.assertTrue(matched)
        self.assertIsNone(reason)

    def test_prefilter_documents_custom_field_query(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query=json.dumps(
                [
                    "AND",
                    [[self.cf1.id, "exact", "match"]],
                ],
            ),
        )
        doc1 = Document.objects.create(
            title="doc 1",
            correspondent=self.c,
            original_filename="doc1.pdf",
            checksum="checksum1",
        )
        CustomFieldInstance.objects.create(
            document=doc1,
            field=self.cf1,
            value_text="match",
        )

        doc2 = Document.objects.create(
            title="doc 2",
            correspondent=self.c,
            original_filename="doc2.pdf",
            checksum="checksum2",
        )
        CustomFieldInstance.objects.create(
            document=doc2,
            field=self.cf1,
            value_text="different",
        )

        filtered = prefilter_documents_by_workflowtrigger(
            Document.objects.all(),
            trigger,
        )
        self.assertIn(doc1, filtered)
        self.assertNotIn(doc2, filtered)

    def test_prefilter_documents_any_filters(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        trigger.filter_has_any_correspondents.set([self.c])
        trigger.filter_has_any_document_types.set([self.dt])
        trigger.filter_has_any_storage_paths.set([self.sp])

        allowed_document = Document.objects.create(
            title="allowed",
            correspondent=self.c,
            document_type=self.dt,
            storage_path=self.sp,
            original_filename="doc-allowed.pdf",
            checksum="checksum-any-allowed",
        )
        blocked_document = Document.objects.create(
            title="blocked",
            correspondent=self.c2,
            document_type=self.dt,
            storage_path=self.sp,
            original_filename="doc-blocked.pdf",
            checksum="checksum-any-blocked",
        )

        filtered = prefilter_documents_by_workflowtrigger(
            Document.objects.all(),
            trigger,
        )

        self.assertIn(allowed_document, filtered)
        self.assertNotIn(blocked_document, filtered)

    def test_consumption_trigger_requires_filter_configuration(self) -> None:
        serializer = WorkflowTriggerSerializer(
            data={
                "type": WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            },
        )

        self.assertFalse(serializer.is_valid())
        errors = serializer.errors.get("non_field_errors", [])
        self.assertIn(
            "File name, path or mail rule filter are required",
            [str(error) for error in errors],
        )

    def test_workflow_trigger_serializer_clears_empty_custom_field_query(self) -> None:
        serializer = WorkflowTriggerSerializer(
            data={
                "type": WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
                "filter_custom_field_query": "",
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("filter_custom_field_query"))

    def test_existing_document_invalid_custom_field_query_configuration(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query="{ not json",
        )

        document = Document.objects.create(
            title="doc invalid query",
            original_filename="invalid.pdf",
            checksum="checksum-invalid-query",
        )

        matched, reason = existing_document_matches_workflow(document, trigger)
        self.assertFalse(matched)
        self.assertEqual(reason, "Invalid custom field query configuration")

    def test_prefilter_documents_returns_none_for_invalid_custom_field_query(
        self,
    ) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query="{ not json",
        )

        Document.objects.create(
            title="doc",
            original_filename="doc.pdf",
            checksum="checksum-prefilter-invalid",
        )

        filtered = prefilter_documents_by_workflowtrigger(
            Document.objects.all(),
            trigger,
        )

        self.assertEqual(list(filtered), [])

    def test_prefilter_documents_applies_all_filters(self) -> None:
        other_document_type = DocumentType.objects.create(name="Other Type")
        other_storage_path = StoragePath.objects.create(
            name="Blocked path",
            path="/blocked/",
        )

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_has_correspondent=self.c,
            filter_has_document_type=self.dt,
            filter_has_storage_path=self.sp,
        )
        trigger.filter_has_tags.set([self.t1])
        trigger.filter_has_all_tags.set([self.t1, self.t2])
        trigger.filter_has_not_tags.set([self.t3])
        trigger.filter_has_not_correspondents.set([self.c2])
        trigger.filter_has_not_document_types.set([other_document_type])
        trigger.filter_has_not_storage_paths.set([other_storage_path])

        allowed_document = Document.objects.create(
            title="allowed",
            correspondent=self.c,
            document_type=self.dt,
            storage_path=self.sp,
            original_filename="allow.pdf",
            checksum="checksum-prefilter-allowed",
        )
        allowed_document.tags.set([self.t1, self.t2])

        blocked_document = Document.objects.create(
            title="blocked",
            correspondent=self.c2,
            document_type=other_document_type,
            storage_path=other_storage_path,
            original_filename="block.pdf",
            checksum="checksum-prefilter-blocked",
        )
        blocked_document.tags.set([self.t1, self.t3])

        filtered = prefilter_documents_by_workflowtrigger(
            Document.objects.all(),
            trigger,
        )

        self.assertIn(allowed_document, filtered)
        self.assertNotIn(blocked_document, filtered)

    def test_document_added_no_match_doctype(self) -> None:
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

    def test_document_added_no_match_correspondent(self) -> None:
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

    def test_document_added_no_match_storage_path(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_has_storage_path=self.sp,
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
            original_filename="sample.pdf",
        )

        with self.assertLogs("paperless.matching", level="DEBUG") as cm:
            document_consumption_finished.send(
                sender=self.__class__,
                document=doc,
            )
            expected_str = f"Document did not match {w}"
            self.assertIn(expected_str, cm.output[0])
            expected_str = f"Document storage path {doc.storage_path} does not match {trigger.filter_has_storage_path}"
            self.assertIn(expected_str, cm.output[1])

    def test_document_added_invalid_title_placeholders(self) -> None:
        """
        GIVEN:
            - Existing workflow with added trigger type
            - Assign title field has an error
        WHEN:
            - File that matches is added
        THEN:
            - Title is updated but the placeholder isn't replaced
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

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )

        self.assertEqual(doc.title, "Doc {created_year]")

    def test_document_updated_workflow(self) -> None:
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

    def test_document_consumption_workflow_month_placeholder_addded(self) -> None:
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload}",
            filter_filename="simple*",
        )

        action = WorkflowAction.objects.create(
            assign_title="Doc added in {{added_month_name_short}}",
        )

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)
        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )
        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ApiUpload,
                    original_file=test_file,
                ),
                None,
            )
            document = Document.objects.first()
            self.assertRegex(
                document.title,
                r"Doc added in \w{3,}",
            )  # Match any 3-letter month name

    def test_document_updated_workflow_existing_custom_field(self) -> None:
        """
        GIVEN:
            - Existing workflow with UPDATED trigger and action that assigns a custom field with a value
        WHEN:
            - Document is updated that already contains the field
        THEN:
            - Document update succeeds and updates the field
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_has_document_type=self.dt,
        )
        action = WorkflowAction.objects.create()
        action.assign_custom_fields.add(self.cf1)
        action.assign_custom_fields_values = {self.cf1.pk: "new value"}
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
        CustomFieldInstance.objects.create(document=doc, field=self.cf1)

        superuser = User.objects.create_superuser("superuser")
        self.client.force_authenticate(user=superuser)

        self.client.patch(
            f"/api/documents/{doc.id}/",
            {"document_type": self.dt.id},
            format="json",
        )

        doc.refresh_from_db()
        self.assertEqual(doc.custom_fields.get(field=self.cf1).value, "new value")

    def test_document_updated_workflow_merge_permissions(self) -> None:
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

    def test_workflow_scheduled_trigger_created(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the created field and action that assigns owner
            - Existing doc that matches the trigger
            - Workflow set to trigger at (now - offset) = now - 1 day
            - Document created date is 2 days ago → trigger condition met
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
        created = now - timedelta(days=2)
        doc = Document.objects.create(
            title="sample test",
            correspondent=self.c,
            original_filename="sample.pdf",
            created=created,
        )

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    def test_workflow_scheduled_trigger_added(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the added field and action that assigns owner
            - Existing doc that matches the trigger
            - Workflow set to trigger at (now - offset) = now - 1 day
            - Document added date is 365 days ago
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
    def test_workflow_scheduled_trigger_modified(self, mock_filter) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against the modified field and action that assigns owner
            - Existing doc that matches the trigger
            - Workflow set to trigger at (now - offset) = now - 1 day
            - Document modified date is mocked as sufficiently in the past
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

    def test_workflow_scheduled_trigger_custom_field(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger against a custom field and action that assigns owner
            - Existing doc that matches the trigger
            - Workflow set to trigger at (now - offset) = now - 1 day
            - Custom field date is 2 days ago
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

    def test_workflow_scheduled_already_run(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger
            - Existing doc that has already had the workflow run
            - Document created 2 days ago, workflow offset = 1 day → trigger time = yesterday
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

    def test_workflow_scheduled_trigger_too_early(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger and recurring interval of 7 days
            - Workflow run date is 6 days ago
            - Document created 40 days ago, offset = 30 → trigger time = 10 days ago
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

    def test_workflow_scheduled_recurring_respects_latest_run(self) -> None:
        """
        GIVEN:
            - Scheduled workflow marked as recurring with a 1-day interval
            - Document that matches the trigger
            - Two prior runs exist: one 2 days ago and one 1 hour ago
        WHEN:
            - Scheduled workflows are checked again
        THEN:
            - Workflow does not run because the most recent run is inside the interval
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CREATED,
            schedule_is_recurring=True,
            schedule_recurring_interval_days=1,
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
            created=timezone.now().date() - timedelta(days=3),
        )

        WorkflowRun.objects.create(
            workflow=w,
            document=doc,
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            run_at=timezone.now() - timedelta(days=2),
        )
        WorkflowRun.objects.create(
            workflow=w,
            document=doc,
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            run_at=timezone.now() - timedelta(hours=1),
        )

        tasks.check_scheduled_workflows()

        doc.refresh_from_db()
        self.assertIsNone(doc.owner)
        self.assertEqual(
            WorkflowRun.objects.filter(
                workflow=w,
                document=doc,
                type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            ).count(),
            2,
        )

    def test_workflow_scheduled_trigger_negative_offset_customfield(self) -> None:
        """
        GIVEN:
            - Workflow with offset -7 (i.e., 7 days *before* the date)
            - doc1: value_date = 5 days ago → trigger time = 12 days ago → triggers
            - doc2: value_date = 9 days in future → trigger time = 2 days in future → does NOT trigger
        WHEN:
            - Scheduled workflows are checked
        THEN:
            - doc1 has owner assigned
            - doc2 remains untouched
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=-7,
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

        doc1 = Document.objects.create(
            title="doc1",
            correspondent=self.c,
            original_filename="doc1.pdf",
            checksum="doc1-checksum",
        )
        CustomFieldInstance.objects.create(
            document=doc1,
            field=self.cf1,
            value_date=timezone.now().date() - timedelta(days=5),
        )

        doc2 = Document.objects.create(
            title="doc2",
            correspondent=self.c,
            original_filename="doc2.pdf",
            checksum="doc2-checksum",
        )
        CustomFieldInstance.objects.create(
            document=doc2,
            field=self.cf1,
            value_date=timezone.now().date() + timedelta(days=9),
        )

        tasks.check_scheduled_workflows()

        doc1.refresh_from_db()
        self.assertEqual(doc1.owner, self.user2)

        doc2.refresh_from_db()
        self.assertIsNone(doc2.owner)

    def test_workflow_scheduled_trigger_negative_offset_created(self) -> None:
        """
        GIVEN:
            - Existing workflow with SCHEDULED trigger and negative offset of -7 days (so 7 days before date)
            - doc created 8 days ago → trigger time = 15 days ago → triggers
            - doc2 created 8 days *in the future* → trigger time = 1 day in future → does NOT trigger
        WHEN:
            - Scheduled workflows are checked for document
        THEN:
            - doc is matched and owner updated
            - doc2 is untouched
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=-7,
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
            checksum="1",
            created=timezone.now().date() - timedelta(days=8),
        )

        doc2 = Document.objects.create(
            title="sample test 2",
            correspondent=self.c,
            original_filename="sample2.pdf",
            checksum="2",
            created=timezone.now().date() + timedelta(days=8),
        )

        tasks.check_scheduled_workflows()
        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)
        doc2.refresh_from_db()
        self.assertIsNone(doc2.owner)  # has not triggered yet

    def test_offset_positive_means_after(self) -> None:
        """
        GIVEN:
            - Document created 30 days ago
            - Workflow with offset +10
        EXPECT:
            - It triggers now, because created + 10 = 20 days ago < now
        """
        doc = Document.objects.create(
            title="Test doc",
            created=timezone.now() - timedelta(days=30),
            correspondent=self.c,
            original_filename="test.pdf",
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CREATED,
            schedule_offset_days=10,
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
        tasks.check_scheduled_workflows()
        doc.refresh_from_db()
        self.assertEqual(doc.owner, self.user2)

    def test_workflow_scheduled_filters_queryset(self) -> None:
        """
        GIVEN:
            - Existing workflow with scheduled trigger
        WHEN:
            - Workflows run and matching documents are found
        THEN:
            - prefilter_documents_by_workflowtrigger appropriately filters
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            schedule_offset_days=-7,
            schedule_date_field=WorkflowTrigger.ScheduleDateField.CREATED,
            filter_filename="*sample*",
            filter_has_document_type=self.dt,
            filter_has_correspondent=self.c,
            filter_has_storage_path=self.sp,
        )
        trigger.filter_has_tags.set([self.t1])
        trigger.save()
        action = WorkflowAction.objects.create(
            assign_owner=self.user2,
        )
        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        # create 10 docs with half having the document type
        for i in range(10):
            doc = Document.objects.create(
                title=f"sample test {i}",
                checksum=f"checksum{i}",
                correspondent=self.c,
                storage_path=self.sp,
                original_filename=f"sample_{i}.pdf",
                document_type=self.dt if i % 2 == 0 else None,
            )
            doc.tags.set([self.t1])
            doc.save()

        documents = Document.objects.all()
        filtered_docs = prefilter_documents_by_workflowtrigger(
            documents,
            trigger,
        )
        self.assertEqual(filtered_docs.count(), 5)

    def test_workflow_enabled_disabled(self) -> None:
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

    def test_new_trigger_type_raises_exception(self) -> None:
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

    def test_removal_action_document_updated_workflow(self) -> None:
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

    def test_removal_action_document_updated_removeall(self) -> None:
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

    def test_removal_action_document_consumed(self) -> None:
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
            assign_title="Doc from {{correspondent}}",
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

    def test_removal_action_document_consumed_remove_all(self) -> None:
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

    def test_workflow_with_tag_actions_doesnt_overwrite_other_actions(self) -> None:
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
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_assignment_then_email_includes_attachment(self, mock_email_send):
        """
        GIVEN:
            - Workflow with assignment and email actions
            - Email action configured to include the document
        WHEN:
            - Workflow is run on a newly created document
        THEN:
            - Email action sends the document as an attachment
        """

        storage_path = StoragePath.objects.create(
            name="sp2",
            path="workflow/{{ document.pk }}",
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        assignment_action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
            assign_storage_path=storage_path,
            assign_owner=self.user2,
        )
        assignment_action.assign_tags.add(self.t1)

        email_action_config = WorkflowActionEmail.objects.create(
            subject="Doc ready {doc_title}",
            body="Document URL: {doc_url}",
            to="owner@example.com",
            include_document=True,
        )
        email_action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EMAIL,
            email=email_action_config,
        )

        workflow = Workflow.objects.create(name="Assignment then email", order=0)
        workflow.triggers.add(trigger)
        workflow.actions.set([assignment_action, email_action])

        temp_working_copy = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "working-copy.pdf",
        )

        Document.objects.create(
            title="workflow doc",
            correspondent=self.c,
            checksum="wf-assignment-email",
            mime_type="application/pdf",
        )

        consumable_document = ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=temp_working_copy,
        )

        mock_email_send.return_value = 1

        with self.assertNoLogs("paperless.workflows", level="ERROR"):
            run_workflows(
                WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                consumable_document,
                overrides=DocumentMetadataOverrides(),
            )

        mock_email_send.assert_called_once()

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("httpx.post")
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_action(self, mock_email_send, mock_post) -> None:
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
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_include_file(self, mock_email_send) -> None:
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

        mock_email_send.reset_mock()
        # test with .eml file
        test_file2 = shutil.copy(
            self.SAMPLE_DIR / "eml_with_umlaut.eml",
            self.dirs.scratch_dir / "eml_with_umlaut.eml",
        )

        doc2 = Document.objects.create(
            title="sample eml",
            checksum="123456",
            filename=test_file2,
            mime_type="message/rfc822",
        )

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc2)

        mock_email_send.assert_called_once()

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_workflow_email_attachment_uses_storage_filename(self) -> None:
        """
        GIVEN:
            - Document updated workflow with include document action
            - Document stored with formatted storage-path filename
        WHEN:
            - Workflow sends an email
        THEN:
            - Attachment filename matches the stored filename
        """

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
        workflow = Workflow.objects.create(
            name="Workflow attachment filename",
            order=0,
        )
        workflow.triggers.add(trigger)
        workflow.actions.add(action)
        workflow.save()

        storage_path = StoragePath.objects.create(
            name="Fancy Path",
            path="formatted/{{ document.pk }}/{{ title }}",
        )
        doc = Document.objects.create(
            title="workflow doc",
            correspondent=self.c,
            checksum="workflow-email-attachment",
            mime_type="application/pdf",
            storage_path=storage_path,
            original_filename="workflow-orig.pdf",
        )

        # eg what happens in update_filename_and_move_files
        generated = generate_unique_filename(doc)
        destination = (settings.ORIGINALS_DIR / generated).resolve()
        create_source_path_directory(destination)
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", destination)
        Document.objects.filter(pk=doc.pk).update(filename=generated.as_posix())

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

        self.assertEqual(len(mail.outbox), 1)
        attachment_names = [att[0] for att in mail.outbox[0].attachments]
        self.assertEqual(attachment_names, [Path(generated).name])

    @override_settings(
        EMAIL_ENABLED=False,
    )
    def test_workflow_email_action_no_email_setup(self) -> None:
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

        with self.assertLogs("paperless.workflows.actions", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Email backend has not been configured"
            self.assertIn(expected_str, cm.output[0])

    @override_settings(
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_action_fail(self, mock_email_send) -> None:
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

        with self.assertLogs("paperless.workflows", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred sending email"
            self.assertIn(expected_str, cm.output[0])

    @override_settings(
        PAPERLESS_EMAIL_HOST="localhost",
        EMAIL_ENABLED=True,
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("httpx.post")
    @mock.patch("django.core.mail.message.EmailMessage.send")
    def test_workflow_email_consumption_started(
        self,
        mock_email_send,
        mock_post,
    ) -> None:
        """
        GIVEN:
            - Workflow with email action and consumption trigger
        WHEN:
            - Document is consumed
        THEN:
            - Email is sent
        """
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
        )
        mock_email_send.return_value = 1

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        email_action = WorkflowActionEmail.objects.create(
            subject="Test Notification: {doc_title}",
            body="Test message: {doc_url}",
            to="user@example.com",
            include_document=False,
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

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            self.dirs.scratch_dir / "simple.pdf",
        )

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO"):
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )

        mock_email_send.assert_called_once()

    @override_settings(
        PAPERLESS_URL="http://localhost:8000",
        PAPERLESS_FORCE_SCRIPT_NAME="/paperless",
        BASE_URL="/paperless/",
    )
    @mock.patch("documents.workflows.webhooks.send_webhook.delay")
    def test_workflow_webhook_action_body(self, mock_post) -> None:
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
            body="Test message: {{doc_url}} with id {{doc_id}}",
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
            data=(
                f"Test message: http://localhost:8000/paperless/documents/{doc.id}/"
                f" with id {doc.id}"
            ),
            headers={},
            files=None,
            as_json=False,
        )

    @override_settings(
        PAPERLESS_URL="http://localhost:8000",
    )
    @mock.patch("documents.workflows.webhooks.send_webhook.delay")
    def test_workflow_webhook_action_w_files(self, mock_post) -> None:
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
            body="Test message: {{doc_url}}",
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
            as_json=False,
        )

    @override_settings(
        PAPERLESS_URL="http://localhost:8000",
    )
    def test_workflow_webhook_action_fail(self) -> None:
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
        with self.assertLogs("paperless.workflows", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred sending webhook"
            self.assertIn(expected_str, cm.output[0])

    def test_workflow_webhook_action_url_invalid_params_headers(self) -> None:
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

        with self.assertLogs("paperless.workflows", level="ERROR") as cm:
            run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, doc)

            expected_str = "Error occurred parsing webhook params"
            self.assertIn(expected_str, cm.output[0])
            expected_str = "Error occurred parsing webhook headers"
            self.assertIn(expected_str, cm.output[1])

    @mock.patch("httpx.Client.post")
    def test_workflow_webhook_send_webhook_task(self, mock_post) -> None:
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
            raise_for_status=mock.Mock(),
        )

        with self.assertLogs("paperless.workflows") as cm:
            send_webhook(
                url="http://paperless-ngx.com",
                data="Test message",
                headers={},
                files=None,
            )

            mock_post.assert_called_once_with(
                url="http://paperless-ngx.com",
                content="Test message",
                headers={},
                files=None,
            )

            expected_str = "Webhook sent to http://paperless-ngx.com"
            self.assertIn(expected_str, cm.output[0])

            # with dict
            send_webhook(
                url="http://paperless-ngx.com",
                data={"message": "Test message"},
                headers={},
                files=None,
            )
            mock_post.assert_called_with(
                url="http://paperless-ngx.com",
                data={"message": "Test message"},
                headers={},
                files=None,
            )

    @mock.patch("httpx.Client.post")
    def test_workflow_webhook_send_webhook_retry(self, mock_http) -> None:
        mock_http.return_value.raise_for_status = mock.Mock(
            side_effect=HTTPStatusError(
                "Error",
                request=mock.Mock(),
                response=mock.Mock(),
            ),
        )

        with self.assertLogs("paperless.workflows") as cm:
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

    @mock.patch("documents.workflows.webhooks.send_webhook.delay")
    def test_workflow_webhook_action_consumption(self, mock_post) -> None:
        """
        GIVEN:
            - Workflow with webhook action and consumption trigger
        WHEN:
            - Document is consumed
        THEN:
            - Webhook is sent
        """
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"status": "ok"}),
        )

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        webhook_action = WorkflowActionWebhook.objects.create(
            use_params=False,
            body="Test message: {doc_url}",
            url="http://paperless-ngx.com",
            include_document=False,
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

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            with self.assertLogs("paperless.matching", level="INFO"):
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=test_file,
                    ),
                    None,
                )

        mock_post.assert_called_once()

    @mock.patch("documents.bulk_edit.remove_password")
    def test_password_removal_action_attempts_multiple_passwords(
        self,
        mock_remove_password,
    ):
        """
        GIVEN:
            - Workflow password removal action
            - Multiple passwords provided
        WHEN:
            - Document updated triggering the workflow
        THEN:
            - Password removal is attempted until one succeeds
        """
        doc = Document.objects.create(
            title="Protected",
            checksum="pw-checksum",
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL,
            passwords="wrong, right\n extra ",
        )
        workflow = Workflow.objects.create(name="Password workflow")
        workflow.triggers.add(trigger)
        workflow.actions.add(action)

        mock_remove_password.side_effect = [
            ValueError("wrong password"),
            "OK",
        ]

        run_workflows(trigger.type, doc)

        assert mock_remove_password.call_count == 2
        mock_remove_password.assert_has_calls(
            [
                mock.call(
                    [doc.id],
                    password="wrong",
                    update_document=True,
                    user=doc.owner,
                ),
                mock.call(
                    [doc.id],
                    password="right",
                    update_document=True,
                    user=doc.owner,
                ),
            ],
        )

    @mock.patch("documents.bulk_edit.remove_password")
    def test_password_removal_action_fails_without_correct_password(
        self,
        mock_remove_password,
    ):
        """
        GIVEN:
            - Workflow password removal action
            - No correct password provided
        WHEN:
            - Document updated triggering the workflow
        THEN:
            - Password removal is attempted for all passwords and fails
        """
        doc = Document.objects.create(
            title="Protected",
            checksum="pw-checksum-2",
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL,
            passwords=" \n , ",
        )
        workflow = Workflow.objects.create(name="Password workflow missing passwords")
        workflow.triggers.add(trigger)
        workflow.actions.add(action)

        run_workflows(trigger.type, doc)

        mock_remove_password.assert_not_called()

    @mock.patch("documents.bulk_edit.remove_password")
    def test_password_removal_action_skips_without_passwords(
        self,
        mock_remove_password,
    ):
        """
        GIVEN:
            - Workflow password removal action with no passwords
        WHEN:
            - Workflow is run
        THEN:
            - Password removal is not attempted
        """
        doc = Document.objects.create(
            title="Protected",
            checksum="pw-checksum-2",
        )
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL,
            passwords="",
        )
        workflow = Workflow.objects.create(name="Password workflow missing passwords")
        workflow.triggers.add(trigger)
        workflow.actions.add(action)

        run_workflows(trigger.type, doc)

        mock_remove_password.assert_not_called()

    @mock.patch("documents.bulk_edit.remove_password")
    def test_password_removal_consumable_document_deferred(
        self,
        mock_remove_password,
    ):
        """
        GIVEN:
            - Workflow password removal action
            - Simulated consumption trigger (a ConsumableDocument is used)
        WHEN:
            - Document consumption is finished
        THEN:
            - Password removal is attempted
        """
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL,
            passwords="first, second",
        )

        temp_dir = Path(tempfile.mkdtemp())
        original_file = temp_dir / "file.pdf"
        original_file.write_bytes(b"pdf content")
        consumable = ConsumableDocument(
            source=DocumentSource.ApiUpload,
            original_file=original_file,
        )

        execute_password_removal_action(action, consumable, logging_group=None)

        mock_remove_password.assert_not_called()

        mock_remove_password.side_effect = [
            ValueError("bad password"),
            "OK",
        ]

        doc = Document.objects.create(
            checksum="pw-checksum-consumed",
            title="Protected",
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )

        assert mock_remove_password.call_count == 2
        mock_remove_password.assert_has_calls(
            [
                mock.call(
                    [doc.id],
                    password="first",
                    update_document=True,
                    user=doc.owner,
                ),
                mock.call(
                    [doc.id],
                    password="second",
                    update_document=True,
                    user=doc.owner,
                ),
            ],
        )

        # ensure handler disconnected after first run
        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )
        assert mock_remove_password.call_count == 2


class TestWebhookSend:
    def test_send_webhook_data_or_json(
        self,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - Nothing
        WHEN:
            - send_webhook is called with data or dict
        THEN:
            - data is sent as form-encoded and json, respectively
        """
        httpx_mock.add_response(
            content=b"ok",
        )

        send_webhook(
            url="http://paperless-ngx.com",
            data="Test message",
            headers={},
            files=None,
            as_json=False,
        )
        assert httpx_mock.get_request().headers.get("Content-Type") is None
        httpx_mock.reset()

        httpx_mock.add_response(
            json={"status": "ok"},
        )
        send_webhook(
            url="http://paperless-ngx.com",
            data={"message": "Test message"},
            headers={},
            files=None,
            as_json=True,
        )
        assert httpx_mock.get_request().headers["Content-Type"] == "application/json"


@pytest.fixture
def resolve_to(monkeypatch):
    """
    Force DNS resolution to a specific IP for any hostname.
    """

    def _set(ip: str):
        def fake_getaddrinfo(host, *_args, **_kwargs):
            return [(socket.AF_INET, None, None, "", (ip, 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    return _set


class TestWebhookSecurity:
    def test_blocks_invalid_scheme_or_hostname(self, httpx_mock: HTTPXMock) -> None:
        """
        GIVEN:
            - Invalid URL schemes or hostnames
        WHEN:
            - send_webhook is called with such URLs
        THEN:
            - ValueError is raised
        """
        with pytest.raises(ValueError):
            send_webhook(
                "ftp://example.com",
                data="",
                headers={},
                files=None,
                as_json=False,
            )

        with pytest.raises(ValueError):
            send_webhook(
                "http:///nohost",
                data="",
                headers={},
                files=None,
                as_json=False,
            )

    @override_settings(WEBHOOKS_ALLOWED_PORTS=[80, 443])
    def test_blocks_disallowed_port(self, httpx_mock: HTTPXMock) -> None:
        """
        GIVEN:
            - URL with a disallowed port
        WHEN:
            - send_webhook is called with such URL
        THEN:
            - ValueError is raised
        """
        with pytest.raises(ValueError):
            send_webhook(
                "http://paperless-ngx.com:8080",
                data="",
                headers={},
                files=None,
                as_json=False,
            )

        assert httpx_mock.get_request() is None

    @override_settings(WEBHOOKS_ALLOW_INTERNAL_REQUESTS=False)
    def test_blocks_private_loopback_linklocal(
        self,
        httpx_mock: HTTPXMock,
        resolve_to,
    ) -> None:
        """
        GIVEN:
            - URL with a private, loopback, or link-local IP address
            - WEBHOOKS_ALLOW_INTERNAL_REQUESTS is False
        WHEN:
            - send_webhook is called with such URL
        THEN:
            - ValueError is raised
        """
        resolve_to("127.0.0.1")
        with pytest.raises(ConnectError):
            send_webhook(
                "http://paperless-ngx.com",
                data="",
                headers={},
                files=None,
                as_json=False,
            )

    def test_allows_public_ip_and_sends(
        self,
        httpx_mock: HTTPXMock,
        resolve_to,
    ) -> None:
        """
        GIVEN:
            - URL with a public IP address
        WHEN:
            - send_webhook is called with such URL
        THEN:
            - Request is sent successfully
        """
        resolve_to("52.207.186.75")
        httpx_mock.add_response(content=b"ok")

        send_webhook(
            url="http://paperless-ngx.com",
            data="hi",
            headers={},
            files=None,
            as_json=False,
        )

        req = httpx_mock.get_request()
        assert req.url.host == "52.207.186.75"
        assert req.headers["host"] == "paperless-ngx.com"

    def test_follow_redirects_disabled(self, httpx_mock: HTTPXMock, resolve_to) -> None:
        """
        GIVEN:
            - A URL that redirects
        WHEN:
            - send_webhook is called with follow_redirects=False
        THEN:
            - Request is made to the original URL and does not follow the redirect
        """
        resolve_to("52.207.186.75")
        # Return a redirect and ensure we don't follow it (only one request recorded)
        httpx_mock.add_response(
            status_code=302,
            headers={"location": "http://internal-service.local"},
            content=b"",
        )

        with pytest.raises(HTTPError):
            send_webhook(
                "http://paperless-ngx.com",
                data="",
                headers={},
                files=None,
                as_json=False,
            )

        assert len(httpx_mock.get_requests()) == 1

    def test_strips_user_supplied_host_header(
        self,
        httpx_mock: HTTPXMock,
        resolve_to,
    ) -> None:
        """
        GIVEN:
            - A URL with a user-supplied Host header
        WHEN:
            - send_webhook is called with a malicious Host header
        THEN:
            - The Host header is stripped and replaced with the resolved hostname
        """
        resolve_to("52.207.186.75")
        httpx_mock.add_response(content=b"ok")

        send_webhook(
            url="http://paperless-ngx.com",
            data="ok",
            headers={"Host": "evil.test"},
            files=None,
            as_json=False,
        )

        req = httpx_mock.get_request()
        assert req.headers["Host"] == "paperless-ngx.com"
        assert "evil.test" not in req.headers.get("Host", "")


@pytest.mark.django_db
class TestDateWorkflowLocalization(
    SampleDirMixin,
):
    """Test cases for workflows that use date localization in templates."""

    TEST_DATETIME = datetime.datetime(
        2023,
        6,
        26,
        14,
        30,
        5,
        tzinfo=datetime.timezone.utc,
    )

    @pytest.mark.parametrize(
        "title_template,expected_title",
        [
            pytest.param(
                "Created at {{ created | localize_date('MMMM', 'es_ES') }}",
                "Created at junio",
                id="spanish_month",
            ),
            pytest.param(
                "Created at {{ created | localize_date('MMMM', 'de_DE') }}",
                "Created at Juni",  # codespell:ignore
                id="german_month",
            ),
            pytest.param(
                "Created at {{ created | localize_date('dd/MM/yyyy', 'en_GB') }}",
                "Created at 26/06/2023",
                id="british_date_format",
            ),
        ],
    )
    def test_document_added_workflow_localization(
        self,
        title_template: str,
        expected_title: str,
    ):
        """
        GIVEN:
            - Document added workflow with title template using localize_date filter
        WHEN:
            - Document is consumed
        THEN:
            - Document title is set with localized date
        """
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename="*sample*",
        )

        action = WorkflowAction.objects.create(
            assign_title=title_template,
        )

        workflow = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        workflow.triggers.add(trigger)
        workflow.actions.add(action)
        workflow.save()

        doc = Document.objects.create(
            title="sample test",
            correspondent=None,
            original_filename="sample.pdf",
            created=self.TEST_DATETIME,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc,
        )

        doc.refresh_from_db()
        assert doc.title == expected_title

    @pytest.mark.parametrize(
        "title_template,expected_title",
        [
            pytest.param(
                "Created at {{ created | localize_date('MMMM', 'es_ES') }}",
                "Created at junio",
                id="spanish_month",
            ),
            pytest.param(
                "Created at {{ created | localize_date('MMMM', 'de_DE') }}",
                "Created at Juni",  # codespell:ignore
                id="german_month",
            ),
            pytest.param(
                "Created at {{ created | localize_date('dd/MM/yyyy', 'en_GB') }}",
                "Created at 26/06/2023",
                id="british_date_format",
            ),
        ],
    )
    def test_document_updated_workflow_localization(
        self,
        title_template: str,
        expected_title: str,
    ):
        """
        GIVEN:
            - Document updated workflow with title template using localize_date filter
        WHEN:
            - Document is updated via API
        THEN:
            - Document title is set with localized date
        """
        # Setup test data
        dt = DocumentType.objects.create(name="DocType Name")
        c = Correspondent.objects.create(name="Correspondent Name")

        client = APIClient()
        superuser = User.objects.create_superuser("superuser")
        client.force_authenticate(user=superuser)

        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            filter_has_document_type=dt,
        )

        doc = Document.objects.create(
            title="sample test",
            correspondent=c,
            original_filename="sample.pdf",
            created=self.TEST_DATETIME,
        )

        action = WorkflowAction.objects.create(
            assign_title=title_template,
        )

        workflow = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        workflow.triggers.add(trigger)
        workflow.actions.add(action)
        workflow.save()

        client.patch(
            f"/api/documents/{doc.id}/",
            {"document_type": dt.id},
            format="json",
        )

        doc.refresh_from_db()
        assert doc.title == expected_title

    @pytest.mark.parametrize(
        "title_template,expected_title",
        [
            pytest.param(
                "Added at {{ added | localize_date('MMMM', 'es_ES') }}",
                "Added at junio",
                id="spanish_month",
            ),
            pytest.param(
                "Added at {{ added | localize_date('MMMM', 'de_DE') }}",
                "Added at Juni",  # codespell:ignore
                id="german_month",
            ),
            pytest.param(
                "Added at {{ added | localize_date('dd/MM/yyyy', 'en_GB') }}",
                "Added at 26/06/2023",
                id="british_date_format",
            ),
        ],
    )
    def test_document_consumption_workflow_localization(
        self,
        tmp_path: Path,
        settings: SettingsWrapper,
        title_template: str,
        expected_title: str,
    ):
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=f"{DocumentSource.ApiUpload}",
            filter_filename="simple*",
        )

        test_file = shutil.copy(
            self.SAMPLE_DIR / "simple.pdf",
            tmp_path / "simple.pdf",
        )

        action = WorkflowAction.objects.create(
            assign_title=title_template,
        )

        w = Workflow.objects.create(
            name="Workflow 1",
            order=0,
        )
        w.triggers.add(trigger)
        w.actions.add(action)
        w.save()

        (tmp_path / "scratch").mkdir(parents=True, exist_ok=True)
        (tmp_path / "thumbnails").mkdir(parents=True, exist_ok=True)

        # Temporarily override "now" for the environment so templates using
        # added/created placeholders behave as if it's a different system date.
        with (
            mock.patch(
                "documents.tasks.ProgressManager",
                DummyProgressManager,
            ),
            mock.patch(
                "django.utils.timezone.now",
                return_value=self.TEST_DATETIME,
            ),
            override_settings(
                SCRATCH_DIR=tmp_path / "scratch",
                THUMBNAIL_DIR=tmp_path / "thumbnails",
            ),
        ):
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ApiUpload,
                    original_file=test_file,
                ),
                None,
            )
            document = Document.objects.first()
            assert document.title == expected_title
