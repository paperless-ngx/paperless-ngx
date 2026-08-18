import json
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.export.delivery import _put_file
from documents.export.delivery import deliver_export_record
from documents.export.sinks import DirectoryExportSink
from documents.export.sinks import ExportSinkError
from documents.models import Document
from documents.models import ExportRecord
from documents.models import ExportTarget
from documents.models import PaperlessTask
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowActionExport
from documents.models import WorkflowTrigger
from documents.signals.handlers import run_workflows
from documents.tests.utils import DirectoriesMixin


class RefusingSink(DirectoryExportSink):
    """A sink whose first ``add_file`` fails, to exercise the retry path.

    It subclasses the real ``DirectoryExportSink`` so it inherits the genuine
    ``refuses_overwrite`` implementation: a test cannot accidentally assert
    behaviour the contract does not actually have.
    """

    def __init__(self, error: Exception, *, exists: bool) -> None:
        super().__init__(
            Path(tempfile.mkdtemp()),
            compare_checksums=False,
            compare_json=False,
            delete=False,
        )
        self._error = error
        self._exists = exists
        self.calls: list[str] = []

    def add_file(self, source, arcname, *, checksum=None) -> None:
        self.calls.append(arcname)
        if len(self.calls) == 1:
            raise self._error

    def exists(self, arcname: str) -> bool:
        return self._exists


class TestExportDelivery(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.export_dir = Path(tempfile.mkdtemp())
        self.target = ExportTarget.objects.create(
            name="Local target",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": str(self.export_dir)},
        )
        self.doc = Document.objects.create(
            title="Invoice",
            mime_type="application/pdf",
            checksum="abc123",
            filename="invoice.pdf",
        )
        self.doc.source_path.write_bytes(b"PDF-CONTENT")

    def _record(self, action=None) -> ExportRecord:
        return ExportRecord.objects.create(
            target=self.target,
            action=action,
            document=self.doc,
            document_pk=self.doc.pk,
        )

    def test_deliver_original_and_sidecar(self) -> None:
        """
        GIVEN:
            - A pending export record for a local target
        WHEN:
            - The record is delivered
        THEN:
            - The original file and metadata sidecar exist at the destination
            - The record is complete with key, checksum and size
        """
        record = self._record()
        deliver_export_record(record)

        # Without a path template the export mirrors the media filename
        expected_key = f"{self.doc.pk:07}.pdf"
        stem = expected_key.rsplit(".", 1)[0]
        self.assertTrue((self.export_dir / expected_key).exists())
        sidecar_path = self.export_dir / f"{stem}.metadata.json"
        self.assertTrue(sidecar_path.exists())
        sidecar = json.loads(sidecar_path.read_text())
        self.assertEqual(sidecar["id"], self.doc.pk)
        self.assertEqual(sidecar["title"], "Invoice")
        self.assertEqual(sidecar["original_checksum"], "abc123")

        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        self.assertEqual(record.object_key, expected_key)
        self.assertEqual(record.checksum, "abc123")
        self.assertEqual(record.size_bytes, len(b"PDF-CONTENT"))
        self.assertIsNotNone(record.finished_at)

    def test_deliver_archive_only(self) -> None:
        """
        GIVEN:
            - An export action configured for the archive version only
        WHEN:
            - A document with an archive version is delivered
        THEN:
            - Only the archive file is delivered, without a sidecar
        """
        self.doc.archive_filename = "invoice-archive.pdf"
        self.doc.archive_checksum = "def456"
        self.doc.save()
        self.doc.archive_path.write_bytes(b"ARCHIVE-CONTENT")

        action = WorkflowActionExport.objects.create(
            target=self.target,
            include_original=False,
            include_archive=True,
            write_metadata_sidecar=False,
        )
        record = self._record(action=action)
        deliver_export_record(record)

        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        self.assertEqual(record.checksum, "def456")
        self.assertTrue(record.object_key.endswith(".pdf"))
        self.assertTrue((self.export_dir / record.object_key).exists())
        self.assertEqual(
            len(list(self.export_dir.glob("*.metadata.json"))),
            0,
        )

    def test_path_template_overrides_filename(self) -> None:
        """
        GIVEN:
            - An export action with a path template using storage path
              placeholders
        WHEN:
            - A document is delivered
        THEN:
            - The rendered template is the full path and filename, with the
              extension appended, and the sidecar sits next to it
        """
        from datetime import date

        from documents.models import DocumentType

        self.doc.document_type = DocumentType.objects.create(name="Invoices")
        self.doc.created = date(2024, 5, 12)
        self.doc.save()

        action = WorkflowActionExport.objects.create(
            target=self.target,
            path="{{ created_year }}/{{ document_type }}/{{ title }}",
        )
        record = self._record(action=action)
        deliver_export_record(record)

        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        expected_key = "2024/Invoices/Invoice.pdf"
        self.assertEqual(record.object_key, expected_key)
        self.assertTrue((self.export_dir / expected_key).exists())
        self.assertTrue(
            (self.export_dir / "2024/Invoices/Invoice.metadata.json").exists(),
        )

    def test_path_render_failure_falls_back_to_media_filename(self) -> None:
        """
        GIVEN:
            - An export action whose path template references an unknown
              variable
        WHEN:
            - A document is delivered
        THEN:
            - The export still completes, named as in the media directory
        """
        action = WorkflowActionExport.objects.create(
            target=self.target,
            path="{{ definitely_not_a_variable }}",
        )
        record = self._record(action=action)
        deliver_export_record(record)

        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        expected_key = f"{self.doc.pk:07}.pdf"
        self.assertEqual(record.object_key, expected_key)
        self.assertTrue((self.export_dir / expected_key).exists())

    def test_deliver_archive_only_without_archive_fails(self) -> None:
        action = WorkflowActionExport.objects.create(
            target=self.target,
            include_original=False,
            include_archive=True,
        )
        record = self._record(action=action)
        with self.assertRaises(ExportSinkError):
            deliver_export_record(record)

    def test_deliver_document_deleted(self) -> None:
        record = self._record()
        record.document = None
        record.save()
        with self.assertRaises(ExportSinkError):
            deliver_export_record(record)

    def test_locked_object_gets_version_suffixed_copy(self) -> None:
        """
        GIVEN:
            - A destination that refuses to overwrite an existing object
        WHEN:
            - The same key is delivered again
        THEN:
            - A second, version-suffixed copy is written instead of failing
        """

        sink = RefusingSink(PermissionError("object locked"), exists=True)
        key = _put_file(
            sink,
            Path("/tmp/x"),
            "0000001_invoice.pdf",
            "abc",
            WorkflowActionExport.ConflictPolicy.OVERWRITE,
        )
        self.assertEqual(len(sink.calls), 2)
        self.assertTrue(key.startswith("0000001_invoice.v"))
        self.assertTrue(key.endswith(".pdf"))

    def test_put_failure_without_existing_object_raises(self) -> None:
        sink = RefusingSink(PermissionError("denied"), exists=False)
        with self.assertRaises(PermissionError):
            _put_file(
                sink,
                Path("/tmp/x"),
                "key.pdf",
                None,
                WorkflowActionExport.ConflictPolicy.OVERWRITE,
            )
        self.assertEqual(len(sink.calls), 1)

    def test_transient_failure_on_existing_object_is_not_duplicated(self) -> None:
        """
        GIVEN:
            - A delivery to a key that already exists at the destination
        WHEN:
            - The upload fails for a reason unrelated to the object being there
        THEN:
            - The failure propagates so the task retries it, rather than a
              version-suffixed duplicate being written on every hiccup
        """
        sink = RefusingSink(ConnectionResetError("connection reset"), exists=True)
        with self.assertRaises(ConnectionResetError):
            _put_file(
                sink,
                Path("/tmp/x"),
                "0000001_invoice.pdf",
                "abc",
                WorkflowActionExport.ConflictPolicy.OVERWRITE,
            )
        self.assertEqual(sink.calls, ["0000001_invoice.pdf"])

    def test_skip_policy_does_not_touch_existing_object(self) -> None:
        sink = RefusingSink(PermissionError("unused"), exists=True)
        key = _put_file(
            sink,
            Path("/tmp/x"),
            "0000001.pdf",
            "abc",
            WorkflowActionExport.ConflictPolicy.SKIP,
        )
        self.assertEqual(sink.calls, [])
        self.assertEqual(key, "0000001.pdf")

    def test_overwrite_policy_replaces_existing_object(self) -> None:
        """
        GIVEN:
            - A completed delivery whose destination copy was since modified
        WHEN:
            - The record is delivered again with the default overwrite policy
        THEN:
            - The destination copy is replaced and no duplicate appears
        """
        deliver_export_record(self._record())
        exported = self.export_dir / f"{self.doc.pk:07}.pdf"
        exported.write_bytes(b"TAMPERED-LONGER-CONTENT")

        deliver_export_record(self._record())
        self.assertEqual(exported.read_bytes(), b"PDF-CONTENT")
        self.assertEqual(len(list(self.export_dir.glob("*.pdf"))), 1)

    def test_skip_policy_leaves_existing_delivery_alone(self) -> None:
        action = WorkflowActionExport.objects.create(
            target=self.target,
            on_conflict=WorkflowActionExport.ConflictPolicy.SKIP,
        )
        deliver_export_record(self._record(action=action))
        exported = self.export_dir / f"{self.doc.pk:07}.pdf"
        exported.write_bytes(b"TAMPERED-LONGER-CONTENT")

        record = self._record(action=action)
        deliver_export_record(record)
        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        self.assertEqual(exported.read_bytes(), b"TAMPERED-LONGER-CONTENT")
        self.assertEqual(len(list(self.export_dir.glob("*.pdf"))), 1)
        self.assertEqual(len(list(self.export_dir.glob("*.metadata.json"))), 1)

    def test_suffix_policy_writes_matching_versioned_set(self) -> None:
        """
        GIVEN:
            - A completed delivery under the "keep both" policy
        WHEN:
            - The same document is delivered again
        THEN:
            - A second, version-suffixed copy of both the file and its
              sidecar is written; the first set stays untouched
        """
        action = WorkflowActionExport.objects.create(
            target=self.target,
            on_conflict=WorkflowActionExport.ConflictPolicy.SUFFIX,
        )
        deliver_export_record(self._record(action=action))

        record = self._record(action=action)
        deliver_export_record(record)
        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.COMPLETE)
        base = f"{self.doc.pk:07}"
        self.assertTrue((self.export_dir / f"{base}.pdf").exists())
        self.assertTrue((self.export_dir / f"{base}.metadata.json").exists())
        suffixed = list(self.export_dir.glob(f"{base}.v*.pdf"))
        self.assertEqual(len(suffixed), 1)
        self.assertEqual(record.object_key, suffixed[0].name)
        stamp = suffixed[0].name.removeprefix(f"{base}.v").removesuffix(".pdf")
        self.assertTrue(
            (self.export_dir / f"{base}.v{stamp}.metadata.json").exists(),
        )

    def test_record_outlives_document(self) -> None:
        record = self._record()
        deliver_export_record(record)
        doc_pk = self.doc.pk
        self.doc.delete()
        self.doc.hard_delete()
        record.refresh_from_db()
        self.assertIsNone(record.document)
        self.assertEqual(record.document_pk, doc_pk)


class TestExportWorkflowAction(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = ExportTarget.objects.create(
            name="Local target",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": tempfile.mkdtemp()},
        )
        self.export_action = WorkflowActionExport.objects.create(
            target=self.target,
        )
        self.action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EXPORT,
            export=self.export_action,
        )
        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        )
        self.workflow = Workflow.objects.create(name="Workflow 1", order=0)
        self.workflow.triggers.add(self.trigger)
        self.workflow.actions.add(self.action)
        self.doc = Document.objects.create(
            title="sample test",
            mime_type="application/pdf",
            checksum="abc123",
            filename="sample.pdf",
        )
        self.doc.source_path.write_bytes(b"PDF-CONTENT")

    @mock.patch("documents.workflows.actions.export_document.apply_async")
    def test_workflow_export_action_creates_record_and_queues_task(
        self,
        mock_apply,
    ) -> None:
        """
        GIVEN:
            - Document updated workflow with an export action
        WHEN:
            - A matching document is updated
        THEN:
            - A pending export record exists and delivery is queued once the
              record has actually been committed
        """
        with self.captureOnCommitCallbacks(execute=True):
            run_workflows(
                WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
                self.doc,
            )
            self.assertFalse(mock_apply.called)

        record = ExportRecord.objects.get()
        self.assertEqual(record.status, ExportRecord.Status.PENDING)
        self.assertEqual(record.target, self.target)
        self.assertEqual(record.action, self.export_action)
        self.assertEqual(record.document_pk, self.doc.pk)
        mock_apply.assert_called_once_with(
            kwargs={"record_id": record.pk},
            headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
        )

    @mock.patch("documents.workflows.actions.export_document.apply_async")
    def test_workflow_export_action_disabled_target(self, mock_apply) -> None:
        self.target.enabled = False
        self.target.save()

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, self.doc)

        self.assertEqual(ExportRecord.objects.count(), 0)
        mock_apply.assert_not_called()

    @mock.patch("documents.workflows.actions.export_document.apply_async")
    def test_workflow_export_action_without_settings(self, mock_apply) -> None:
        self.action.export = None
        self.action.save()

        run_workflows(WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED, self.doc)

        self.assertEqual(ExportRecord.objects.count(), 0)
        mock_apply.assert_not_called()


class TestExportWorkflowAPI(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/workflows/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        self.target = ExportTarget.objects.create(
            name="Local target",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": tempfile.mkdtemp()},
        )

    def _post_workflow(self, trigger_type, action):
        return self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "name": "Workflow 1",
                    "order": 0,
                    "triggers": [
                        {
                            "type": trigger_type,
                            "filter_filename": "*",
                        },
                    ],
                    "actions": [action],
                },
            ),
            content_type="application/json",
        )

    def test_export_action_requires_export_data(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {"type": WorkflowAction.WorkflowActionType.EXPORT},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_action_valid(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {
                    "target": self.target.pk,
                    "include_original": True,
                    "include_archive": False,
                },
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        action = Workflow.objects.get().actions.first()
        self.assertIsNotNone(action.export)
        self.assertEqual(action.export.target, self.target)

    def test_export_action_path_saved(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {
                    "target": self.target.pk,
                    "path": "{{ created_year }}/{{ title }}",
                },
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        action = Workflow.objects.get().actions.first()
        self.assertEqual(
            action.export.path,
            "{{ created_year }}/{{ title }}",
        )

    def test_export_action_path_invalid_variable(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {
                    "target": self.target.pk,
                    "path": "{{ not_a_real_variable }}",
                },
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_action_rejected_for_consumption_trigger(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {"target": self.target.pk},
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_action_requires_a_file_type(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {
                    "target": self.target.pk,
                    "include_original": False,
                    "include_archive": False,
                },
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_settings_pruned_with_action(self) -> None:
        response = self._post_workflow(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            {
                "type": WorkflowAction.WorkflowActionType.EXPORT,
                "export": {"target": self.target.pk},
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        workflow_id = response.data["id"]

        response = self.client.patch(
            f"{self.ENDPOINT}{workflow_id}/",
            json.dumps(
                {
                    "actions": [
                        {"type": WorkflowAction.WorkflowActionType.ASSIGNMENT},
                    ],
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WorkflowActionExport.objects.count(), 0)
        # The standalone target is not pruned
        self.assertEqual(ExportTarget.objects.count(), 1)


class TestExportTargetAPI(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/export_targets/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        self.export_dir = tempfile.mkdtemp()

    def test_create_local_target_runs_probe(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {
                "name": "NAS",
                "kind": "local",
                "config": {"path": self.export_dir},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ExportTarget.objects.count(), 1)
        # The probe object was cleaned up
        self.assertEqual(len(list(Path(self.export_dir).glob("*"))), 0)

    def test_create_local_target_requires_path(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {"name": "NAS", "kind": "local", "config": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_target_failing_probe_is_not_saved(self) -> None:
        blocking_file = Path(self.export_dir) / "file"
        blocking_file.write_text("not a directory")
        response = self.client.post(
            self.ENDPOINT,
            {
                "name": "NAS",
                "kind": "local",
                "config": {"path": str(blocking_file / "sub")},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ExportTarget.objects.count(), 0)

    def test_s3_target_requires_bucket(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {"name": "Bucket", "kind": "s3", "config": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retention_only_on_s3(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {
                "name": "NAS",
                "kind": "local",
                "config": {"path": self.export_dir},
                "retention_days": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_secrets_are_obfuscated(self) -> None:
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
            secret_key="topsecret",
        )
        response = self.client.get(f"{self.ENDPOINT}{target.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data["secret_key"]), {"*"})

    def test_update_with_obfuscated_secret_keeps_stored_value(self) -> None:
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
            secret_key="topsecret",
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{target.pk}/",
            {"secret_key": "**********"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertEqual(target.secret_key, "topsecret")

    def test_unrelated_edit_does_not_probe(self) -> None:
        """
        GIVEN:
            - A saved target whose destination has since become unreachable
        WHEN:
            - Something unrelated to the connection is edited (a rename, an
              owner change, pausing it)
        THEN:
            - The edit succeeds without probing the destination
        """
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
        )
        with mock.patch("documents.views.probe_target") as probe:
            response = self.client.patch(
                f"{self.ENDPOINT}{target.pk}/",
                {"name": "Renamed NAS", "enabled": False},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        probe.assert_not_called()
        target.refresh_from_db()
        self.assertEqual(target.name, "Renamed NAS")
        self.assertFalse(target.enabled)

    def test_changing_the_destination_probes_again(self) -> None:
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
        )
        with mock.patch("documents.views.probe_target") as probe:
            response = self.client.patch(
                f"{self.ENDPOINT}{target.pk}/",
                {"config": {"path": tempfile.mkdtemp()}},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        probe.assert_called_once()

    def test_failing_probe_leaves_the_stored_target_untouched(self) -> None:
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
        )
        blocking_file = Path(self.export_dir) / "file"
        blocking_file.write_text("not a directory")
        response = self.client.patch(
            f"{self.ENDPOINT}{target.pk}/",
            {"config": {"path": str(blocking_file / "sub")}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        target.refresh_from_db()
        self.assertEqual(target.config, {"path": self.export_dir})

    def test_delete_refused_while_a_workflow_uses_the_target(self) -> None:
        """
        GIVEN:
            - A target referenced by a workflow export action
        WHEN:
            - The target is deleted
        THEN:
            - The deletion is refused, naming the workflow, rather than
              leaving an export action behind with nothing to export
        """
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
        )
        workflow = Workflow.objects.create(name="Archive", order=0)
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.EXPORT,
            export=WorkflowActionExport.objects.create(target=target),
        )
        workflow.actions.add(action)

        response = self.client.delete(f"{self.ENDPOINT}{target.pk}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Archive", str(response.data))
        self.assertTrue(ExportTarget.objects.filter(pk=target.pk).exists())

    def test_delete_unused_target(self) -> None:
        target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": self.export_dir},
        )
        response = self.client.delete(f"{self.ENDPOINT}{target.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExportTarget.objects.filter(pk=target.pk).exists())

    def test_test_endpoint(self) -> None:
        response = self.client.post(
            f"{self.ENDPOINT}test/",
            {
                "kind": "local",
                "config": {"path": self.export_dir},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        blocking_file = Path(self.export_dir) / "file"
        blocking_file.write_text("not a directory")
        response = self.client.post(
            f"{self.ENDPOINT}test/",
            {
                "kind": "local",
                "config": {"path": str(blocking_file / "sub")},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDocumentExportsAPI(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)
        self.target = ExportTarget.objects.create(
            name="Local target",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": tempfile.mkdtemp()},
        )
        self.doc = Document.objects.create(
            title="Invoice",
            mime_type="application/pdf",
            checksum="abc123",
            filename="invoice.pdf",
        )

    def test_list_export_records(self) -> None:
        ExportRecord.objects.create(
            target=self.target,
            document=self.doc,
            document_pk=self.doc.pk,
            status=ExportRecord.Status.COMPLETE,
            object_key="0000001_invoice.pdf",
        )
        response = self.client.get(f"/api/documents/{self.doc.pk}/exports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["target_name"], "Local target")
        self.assertEqual(response.data[0]["object_key"], "0000001_invoice.pdf")

    @mock.patch("documents.views.export_document.apply_async")
    def test_export_now(self, mock_apply) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/documents/{self.doc.pk}/exports/",
                {"target": self.target.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record = ExportRecord.objects.get()
        self.assertEqual(record.status, ExportRecord.Status.PENDING)
        self.assertIsNone(record.action)
        mock_apply.assert_called_once_with(kwargs={"record_id": record.pk})

    @mock.patch("documents.views.export_document.apply_async")
    def test_export_now_disabled_target(self, mock_apply) -> None:
        self.target.enabled = False
        self.target.save()
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/",
            {"target": self.target.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_apply.assert_not_called()

    def test_export_now_requires_target(self) -> None:
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_requires_view_exportrecord(self) -> None:
        """
        GIVEN:
            - A user who may view the document but not export records
        WHEN:
            - The document's export history is requested
        THEN:
            - Access is refused, matching what the UI shows that user
        """
        user = User.objects.create_user(username="viewer")
        user.user_permissions.add(
            *Permission.objects.filter(codename="view_document"),
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/documents/{self.doc.pk}/exports/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _failed_record(self) -> ExportRecord:
        return ExportRecord.objects.create(
            target=self.target,
            document=self.doc,
            document_pk=self.doc.pk,
            status=ExportRecord.Status.FAILED,
            last_error={"error": "Access denied", "attempt": 4},
            finished_at=timezone.now(),
        )

    @mock.patch("documents.views.export_document.apply_async")
    def test_retry_failed_export(self, mock_apply) -> None:
        """
        GIVEN:
            - A failed export record (e.g. stale target credentials, now fixed)
        WHEN:
            - Its retry endpoint is called
        THEN:
            - The record returns to pending, its error is cleared and the
              delivery task is queued again for the same record
        """
        record = self._failed_record()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/documents/{self.doc.pk}/exports/{record.pk}/retry/",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.PENDING)
        self.assertIsNone(record.last_error)
        self.assertIsNone(record.finished_at)
        mock_apply.assert_called_once_with(kwargs={"record_id": record.pk})

    @mock.patch("documents.views.export_document.apply_async")
    def test_retry_requires_failed_status(self, mock_apply) -> None:
        record = ExportRecord.objects.create(
            target=self.target,
            document=self.doc,
            document_pk=self.doc.pk,
            status=ExportRecord.Status.COMPLETE,
            object_key="0000001_invoice.pdf",
        )
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/{record.pk}/retry/",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_apply.assert_not_called()

    @mock.patch("documents.views.export_document.apply_async")
    def test_retry_disabled_target(self, mock_apply) -> None:
        record = self._failed_record()
        self.target.enabled = False
        self.target.save()
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/{record.pk}/retry/",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_apply.assert_not_called()

    @mock.patch("documents.views.export_document.apply_async")
    def test_retry_record_of_other_document_is_404(self, mock_apply) -> None:
        record = self._failed_record()
        other = Document.objects.create(
            title="Other",
            mime_type="application/pdf",
            checksum="def456",
            filename="other.pdf",
        )
        response = self.client.post(
            f"/api/documents/{other.pk}/exports/{record.pk}/retry/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_apply.assert_not_called()

    @mock.patch("documents.views.export_document.apply_async")
    def test_retry_requires_add_exportrecord(self, mock_apply) -> None:
        record = self._failed_record()
        user = User.objects.create_user(username="viewer2")
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_document", "view_exportrecord"],
            ),
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/{record.pk}/retry/",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_apply.assert_not_called()

    @mock.patch("documents.views.export_document.apply_async")
    def test_export_now_requires_add_exportrecord(self, mock_apply) -> None:
        user = User.objects.create_user(username="viewer")
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_document", "view_exportrecord"],
            ),
        )
        self.client.force_authenticate(user=user)
        self.assertEqual(
            self.client.get(f"/api/documents/{self.doc.pk}/exports/").status_code,
            status.HTTP_200_OK,
        )
        response = self.client.post(
            f"/api/documents/{self.doc.pk}/exports/",
            {"target": self.target.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_apply.assert_not_called()


class TestExportTaskFailure(DirectoriesMixin, TestCase):
    def test_exhausted_retries_mark_record_failed(self) -> None:
        from documents.workflows.exports import export_document

        target = ExportTarget.objects.create(
            name="Broken",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": "/nonexistent"},
        )
        doc = Document.objects.create(
            title="Invoice",
            mime_type="application/pdf",
            checksum="abc123",
            filename="invoice.pdf",
        )
        record = ExportRecord.objects.create(
            target=target,
            document=doc,
            document_pk=doc.pk,
        )

        with (
            mock.patch(
                "documents.export.delivery.deliver_export_record",
                side_effect=ExportSinkError("boom"),
            ),
            mock.patch.object(export_document, "retry", side_effect=Exception),
            mock.patch.object(
                export_document,
                "max_retries",
                0,
            ),
        ):
            with self.assertRaises(ExportSinkError):
                export_document.apply(kwargs={"record_id": record.pk}).get()

        record.refresh_from_db()
        self.assertEqual(record.status, ExportRecord.Status.FAILED)
        self.assertEqual(record.last_error["error"], "boom")
        self.assertIsNotNone(record.finished_at)


class TestExportTaskTracking(DirectoriesMixin, TestCase):
    """
    The export task is a tracked task: publishing it creates a PaperlessTask,
    so failed exports show up in the tasks view instead of only in system
    status.
    """

    def setUp(self) -> None:
        super().setUp()
        self.target = ExportTarget.objects.create(
            name="Local target",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": tempfile.mkdtemp()},
        )
        self.doc = Document.objects.create(
            title="Invoice",
            mime_type="application/pdf",
            checksum="abc123",
            filename="invoice.pdf",
        )
        self.record = ExportRecord.objects.create(
            target=self.target,
            document=self.doc,
            document_pk=self.doc.pk,
        )

    def _publish(self, task_id: str = "export-task-1") -> None:
        from documents.signals.handlers import before_task_publish_handler

        before_task_publish_handler(
            headers={
                "task": "documents.workflows.exports.export_document",
                "id": task_id,
            },
            body=((), {"record_id": self.record.pk}, {}),
        )

    def test_publish_creates_tracked_task(self) -> None:
        self._publish()
        task = PaperlessTask.objects.get()
        self.assertEqual(task.task_type, PaperlessTask.TaskType.EXPORT_DOCUMENT)
        self.assertEqual(task.status, PaperlessTask.Status.PENDING)
        self.assertEqual(task.input_data["record_id"], self.record.pk)
        self.assertEqual(task.input_data["document_id"], self.doc.pk)
        self.assertEqual(task.input_data["target"], "Local target")
        self.assertEqual(task.related_document_ids, [self.doc.pk])

    def test_retry_republish_does_not_duplicate_task(self) -> None:
        """
        Celery retries republish the message under the same task id; the
        record from the first publish must stand instead of raising on the
        unique constraint.
        """
        self._publish()
        self._publish()
        self.assertEqual(PaperlessTask.objects.count(), 1)


class TestExportAdmin(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_login(self.user)
        self.target = ExportTarget.objects.create(
            name="NAS",
            kind=ExportTarget.Kind.LOCAL,
            config={"path": tempfile.mkdtemp()},
            secret_key="topsecret",
        )
        self.record = ExportRecord.objects.create(
            target=self.target,
            document_pk=1,
            status=ExportRecord.Status.COMPLETE,
            object_key="0000001_invoice.pdf",
        )

    def test_target_pages_render_without_exposing_secrets(self) -> None:
        """
        GIVEN:
            - An export target with a stored secret
        WHEN:
            - Its admin pages are opened
        THEN:
            - They render, and the secret is not written into the form
        """
        response = self.client.get("/admin/documents/exporttarget/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/admin/documents/exporttarget/{self.target.pk}/change/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, "topsecret")
        self.assertContains(response, "secret key")

    def test_record_pages_render(self) -> None:
        response = self.client.get("/admin/documents/exportrecord/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/admin/documents/exportrecord/{self.record.pk}/change/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "0000001_invoice.pdf")

    def test_records_cannot_be_created_by_hand(self) -> None:
        # Records are audit evidence written by the delivery task
        response = self.client.get("/admin/documents/exportrecord/add/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
