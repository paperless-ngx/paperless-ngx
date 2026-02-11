from __future__ import annotations

from unittest import mock

from auditlog.models import LogEntry  # type: ignore[import-untyped]
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.models import Document
from documents.tests.utils import DirectoriesMixin


class TestDocumentVersioningApi(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def _make_pdf_upload(self, name: str = "version.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )

    def test_root_endpoint_returns_root_for_version_and_root(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        version = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )

        resp_root = self.client.get(f"/api/documents/{root.id}/root/")
        self.assertEqual(resp_root.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_root.data["root_id"], root.id)

        resp_version = self.client.get(f"/api/documents/{version.id}/root/")
        self.assertEqual(resp_version.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_version.data["root_id"], root.id)

    def test_delete_version_disallows_deleting_root(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{root.id}/")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Document.objects.filter(id=root.id).exists())

    def test_delete_version_deletes_version_and_returns_current_version(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        v1 = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )
        v2 = Document.objects.create(
            title="v2",
            checksum="v2",
            mime_type="application/pdf",
            root_document=root,
        )

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{v2.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=v2.id).exists())
        self.assertEqual(resp.data["current_version_id"], v1.id)

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{v1.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=v1.id).exists())
        self.assertEqual(resp.data["current_version_id"], root.id)

    def test_delete_version_writes_audit_log_entry(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        version = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )
        version_id = version.id

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(
                f"/api/documents/{root.id}/versions/{version_id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Audit log entry is created against the root document.
        entry = (
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(Document),
                object_id=root.id,
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIsNotNone(entry.actor)
        assert entry.actor is not None
        self.assertEqual(entry.actor.id, self.user.id)
        self.assertEqual(entry.action, LogEntry.Action.UPDATE)
        self.assertEqual(
            entry.changes,
            {"Version Deleted": ["None", version_id]},
        )
        additional_data = entry.additional_data or {}
        self.assertEqual(additional_data.get("version_id"), version_id)

    def test_delete_version_returns_404_when_version_not_related(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        other_root = Document.objects.create(
            title="other",
            checksum="other",
            mime_type="application/pdf",
        )
        other_version = Document.objects.create(
            title="other-v1",
            checksum="other-v1",
            mime_type="application/pdf",
            root_document=other_root,
        )

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(
                f"/api/documents/{root.id}/versions/{other_version.id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_version_accepts_version_id_as_root_parameter(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        version = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )

        with mock.patch("documents.index.remove_document_from_index"):
            resp = self.client.delete(
                f"/api/documents/{version.id}/versions/{version.id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=version.id).exists())
        self.assertEqual(resp.data["current_version_id"], root.id)

    def test_update_version_enqueues_consume_with_overrides(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        upload = self._make_pdf_upload()

        async_task = mock.Mock()
        async_task.id = "task-123"

        with mock.patch("documents.views.consume_file") as consume_mock:
            consume_mock.delay.return_value = async_task
            resp = self.client.post(
                f"/api/documents/{root.id}/update_version/",
                {"document": upload, "version_label": "  New Version  "},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, "task-123")
        consume_mock.delay.assert_called_once()
        input_doc, overrides = consume_mock.delay.call_args[0]
        self.assertEqual(input_doc.root_document_id, root.id)
        self.assertEqual(input_doc.source, DocumentSource.ApiUpload)
        self.assertEqual(overrides.version_label, "New Version")
        self.assertEqual(overrides.actor_id, self.user.id)

    def test_update_version_returns_403_without_permission(self) -> None:
        owner = User.objects.create_user(username="owner")
        other = User.objects.create_user(username="other")
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            owner=owner,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.post(
            f"/api/documents/{root.id}/update_version/",
            {"document": self._make_pdf_upload()},
            format="multipart",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_version_returns_404_for_missing_document(self) -> None:
        resp = self.client.post(
            "/api/documents/9999/update_version/",
            {"document": self._make_pdf_upload()},
            format="multipart",
        )

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_version_requires_document(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )

        resp = self.client.post(
            f"/api/documents/{root.id}/update_version/",
            {"version_label": "label"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
