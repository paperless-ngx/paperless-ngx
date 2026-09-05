from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from unittest import mock

from auditlog.models import LogEntry  # type: ignore[import-untyped]
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase as DjangoTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.filters import EffectiveContentFilter
from documents.filters import TitleContentFilter
from documents.models import Document
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import read_streaming_response
from documents.versioning import annotate_effective_content
from documents.views import DocumentSelectionMixin

if TYPE_CHECKING:
    from pathlib import Path


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

    def _write_file(self, path: Path, content: bytes = b"data") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _create_pdf(
        self,
        *,
        title: str,
        checksum: str,
        root_document: Document | None = None,
    ) -> Document:
        doc = Document.objects.create(
            title=title,
            checksum=checksum,
            mime_type="application/pdf",
            root_document=root_document,
        )
        self._write_file(doc.source_path, b"pdf")
        self._write_file(doc.thumbnail_path, b"thumb")
        return doc

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

    def test_root_endpoint_returns_404_for_missing_document(self) -> None:
        resp = self.client.get("/api/documents/9999/root/")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_root_endpoint_returns_403_when_user_lacks_permission(self) -> None:
        owner = User.objects.create_user(username="owner")
        viewer = User.objects.create_user(username="viewer")
        viewer.user_permissions.add(
            Permission.objects.get(codename="view_document"),
        )
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            owner=owner,
        )
        self.client.force_authenticate(user=viewer)

        resp = self.client.get(f"/api/documents/{root.id}/root/")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_version_disallows_deleting_root(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )

        with mock.patch("documents.search.get_backend"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{root.id}/")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Document.objects.filter(id=root.id).exists())

    def test_delete_version_deletes_version_and_returns_current_version(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        v1 = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="v1-content",
        )
        v2 = Document.objects.create(
            title="v2",
            checksum="v2",
            mime_type="application/pdf",
            root_document=root,
            content="v2-content",
        )
        original_modified = timezone.now() - datetime.timedelta(days=1)
        Document.objects.filter(pk=root.pk).update(modified=original_modified)

        with mock.patch("documents.search.get_backend"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{v2.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=v2.id).exists())
        self.assertEqual(resp.data["current_version_id"], v1.id)
        root.refresh_from_db()
        self.assertEqual(root.content, "root-content")
        self.assertGreater(root.modified, original_modified)

        with mock.patch("documents.search.get_backend"):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{v1.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=v1.id).exists())
        self.assertEqual(resp.data["current_version_id"], root.id)
        root.refresh_from_db()
        self.assertEqual(root.content, "root-content")

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

        with mock.patch("documents.search.get_backend"):
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

        with mock.patch("documents.search.get_backend"):
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

        with mock.patch("documents.search.get_backend"):
            resp = self.client.delete(
                f"/api/documents/{version.id}/versions/{version.id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=version.id).exists())
        self.assertEqual(resp.data["current_version_id"], root.id)

    def test_delete_version_returns_404_when_root_missing(self) -> None:
        resp = self.client.delete("/api/documents/9999/versions/123/")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_version_reindexes_root_document(self) -> None:
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

        with mock.patch("documents.search.get_backend") as mock_get_backend:
            mock_backend = mock.MagicMock()
            mock_get_backend.return_value = mock_backend
            resp = self.client.delete(
                f"/api/documents/{root.id}/versions/{version.id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_backend.remove.assert_called_once_with(version.pk)
        mock_backend.add_or_update.assert_called_once()
        self.assertEqual(mock_backend.add_or_update.call_args[0][0].id, root.id)

    def test_delete_version_returns_403_without_permission(self) -> None:
        owner = User.objects.create_user(username="owner")
        other = User.objects.create_user(username="other")
        other.user_permissions.add(
            Permission.objects.get(codename="delete_document"),
        )
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            owner=owner,
        )
        version = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.delete(
            f"/api/documents/{root.id}/versions/{version.id}/",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_version_returns_404_when_version_missing(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )

        resp = self.client.delete(f"/api/documents/{root.id}/versions/9999/")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_version_label_updates_and_trims(self) -> None:
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
            version_label="old",
        )
        original_modified = timezone.now() - datetime.timedelta(days=1)
        Document.objects.filter(pk=root.pk).update(modified=original_modified)

        resp = self.client.patch(
            f"/api/documents/{root.id}/versions/{version.id}/",
            {"version_label": "  Label 1  "},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        version.refresh_from_db()
        self.assertEqual(version.version_label, "Label 1")
        self.assertEqual(resp.data["version_label"], "Label 1")
        self.assertEqual(resp.data["id"], version.id)
        self.assertFalse(resp.data["is_root"])
        root.refresh_from_db()
        self.assertGreater(root.modified, original_modified)

    def test_update_version_label_clears_on_blank(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            version_label="Root Label",
        )

        resp = self.client.patch(
            f"/api/documents/{root.id}/versions/{root.id}/",
            {"version_label": "   "},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        root.refresh_from_db()
        self.assertIsNone(root.version_label)
        self.assertIsNone(resp.data["version_label"])
        self.assertTrue(resp.data["is_root"])

    def test_update_version_label_returns_403_without_permission(self) -> None:
        owner = User.objects.create_user(username="owner")
        other = User.objects.create_user(username="other")
        other.user_permissions.add(
            Permission.objects.get(codename="change_document"),
        )
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            owner=owner,
        )
        version = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.patch(
            f"/api/documents/{root.id}/versions/{version.id}/",
            {"version_label": "Blocked"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_version_label_returns_404_for_unrelated_version(self) -> None:
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

        resp = self.client.patch(
            f"/api/documents/{root.id}/versions/{other_version.id}/",
            {"version_label": "Nope"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_version_param_errors(self) -> None:
        root = self._create_pdf(title="root", checksum="root")

        resp = self.client.get(
            f"/api/documents/{root.id}/download/?version=not-a-number",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = self.client.get(f"/api/documents/{root.id}/download/?version=9999")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        other_root = self._create_pdf(title="other", checksum="other")
        other_version = self._create_pdf(
            title="other-v1",
            checksum="other-v1",
            root_document=other_root,
        )
        resp = self.client.get(
            f"/api/documents/{root.id}/download/?version={other_version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_preview_thumb_with_version_param(self) -> None:
        root = self._create_pdf(title="root", checksum="root")
        version = self._create_pdf(
            title="v1",
            checksum="v1",
            root_document=root,
        )
        self._write_file(version.source_path, b"version")
        self._write_file(version.thumbnail_path, b"thumb")

        resp = self.client.get(
            f"/api/documents/{root.id}/download/?version={version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(read_streaming_response(resp), b"version")

        resp = self.client.get(
            f"/api/documents/{root.id}/preview/?version={version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(read_streaming_response(resp), b"version")

        resp = self.client.get(
            f"/api/documents/{root.id}/thumb/?version={version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(read_streaming_response(resp), b"thumb")

    def test_thumb_etag_changes_when_latest_version_is_deleted(self) -> None:
        root = self._create_pdf(title="root", checksum="root")
        v1 = self._create_pdf(
            title="v1",
            checksum="v1",
            root_document=root,
        )
        v2 = self._create_pdf(
            title="v2",
            checksum="v2",
            root_document=root,
        )
        self._write_file(v1.thumbnail_path, b"thumb-v1")
        self._write_file(v2.thumbnail_path, b"thumb-v2")

        resp = self.client.get(f"/api/documents/{root.id}/thumb/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(read_streaming_response(resp), b"thumb-v2")
        self.assertEqual(resp.headers["ETag"], '"v2"')

        with mock.patch("documents.search.get_backend"):
            delete_resp = self.client.delete(
                f"/api/documents/{root.id}/versions/{v2.id}/",
            )
        self.assertEqual(delete_resp.status_code, status.HTTP_200_OK)

        resp = self.client.get(
            f"/api/documents/{root.id}/thumb/",
            HTTP_IF_NONE_MATCH='"v2"',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.headers["ETag"], '"v1"')
        self.assertEqual(read_streaming_response(resp), b"thumb-v1")

    def test_metadata_version_param_uses_version(self) -> None:
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

        with mock.patch("documents.views.DocumentViewSet.get_metadata") as metadata:
            metadata.return_value = []
            resp = self.client.get(
                f"/api/documents/{root.id}/metadata/?version={version.id}",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(metadata.called)

    def test_metadata_version_param_errors(self) -> None:
        root = self._create_pdf(title="root", checksum="root")

        resp = self.client.get(
            f"/api/documents/{root.id}/metadata/?version=not-a-number",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = self.client.get(f"/api/documents/{root.id}/metadata/?version=9999")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        other_root = self._create_pdf(title="other", checksum="other")
        other_version = self._create_pdf(
            title="other-v1",
            checksum="other-v1",
            root_document=other_root,
        )
        resp = self.client.get(
            f"/api/documents/{root.id}/metadata/?version={other_version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_metadata_returns_403_when_user_lacks_permission(self) -> None:
        owner = User.objects.create_user(username="owner")
        other = User.objects.create_user(username="other")
        other.user_permissions.add(
            Permission.objects.get(codename="view_document"),
        )
        doc = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            owner=owner,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.get(f"/api/documents/{doc.id}/metadata/")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

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
            consume_mock.apply_async.return_value = async_task
            resp = self.client.post(
                f"/api/documents/{root.id}/update_version/",
                {"document": upload, "version_label": "  New Version  "},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, "task-123")
        consume_mock.apply_async.assert_called_once()
        task_kwargs = consume_mock.apply_async.call_args.kwargs["kwargs"]
        input_doc, overrides = task_kwargs["input_doc"], task_kwargs["overrides"]
        self.assertEqual(input_doc.root_document_id, root.id)
        self.assertEqual(input_doc.source, DocumentSource.ApiUpload)
        self.assertEqual(overrides.version_label, "New Version")
        self.assertEqual(overrides.actor_id, self.user.id)

    def test_update_version_with_version_pk_normalizes_to_root(self) -> None:
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
        upload = self._make_pdf_upload()

        async_task = mock.Mock()
        async_task.id = "task-123"

        with mock.patch("documents.views.consume_file") as consume_mock:
            consume_mock.apply_async.return_value = async_task
            resp = self.client.post(
                f"/api/documents/{version.id}/update_version/",
                {"document": upload, "version_label": "  New Version  "},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, "task-123")
        consume_mock.apply_async.assert_called_once()
        task_kwargs = consume_mock.apply_async.call_args.kwargs["kwargs"]
        input_doc, overrides = task_kwargs["input_doc"], task_kwargs["overrides"]
        self.assertEqual(input_doc.root_document_id, root.id)
        self.assertEqual(overrides.version_label, "New Version")
        self.assertEqual(overrides.actor_id, self.user.id)

    def test_update_version_returns_500_on_consume_failure(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        upload = self._make_pdf_upload()

        with mock.patch("documents.views.consume_file") as consume_mock:
            consume_mock.apply_async.side_effect = Exception("boom")
            resp = self.client.post(
                f"/api/documents/{root.id}/update_version/",
                {"document": upload},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    def test_update_version_requires_global_change_permission(self) -> None:
        user = User.objects.create_user(username="add-only")
        user.user_permissions.add(Permission.objects.get(codename="add_document"))
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        self.client.force_authenticate(user=user)

        with mock.patch("documents.views.consume_file") as consume_mock:
            resp = self.client.post(
                f"/api/documents/{root.id}/update_version/",
                {"document": self._make_pdf_upload()},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        consume_mock.apply_async.assert_not_called()

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

    def test_patch_content_updates_latest_version_content(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        v1 = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="v1-content",
        )
        v2 = Document.objects.create(
            title="v2",
            checksum="v2",
            mime_type="application/pdf",
            root_document=root,
            content="v2-content",
        )

        resp = self.client.patch(
            f"/api/documents/{root.id}/",
            {"content": "edited-content"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "edited-content")
        root.refresh_from_db()
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v2.content, "edited-content")
        self.assertEqual(root.content, "root-content")
        self.assertEqual(v1.content, "v1-content")

    def test_patch_content_updates_selected_version_content(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        v1 = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="v1-content",
        )
        v2 = Document.objects.create(
            title="v2",
            checksum="v2",
            mime_type="application/pdf",
            root_document=root,
            content="v2-content",
        )

        resp = self.client.patch(
            f"/api/documents/{root.id}/?version={v1.id}",
            {"content": "edited-v1"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "edited-v1")
        root.refresh_from_db()
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v1.content, "edited-v1")
        self.assertEqual(v2.content, "v2-content")
        self.assertEqual(root.content, "root-content")

    def test_retrieve_returns_latest_version_content(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="v1-content",
        )

        resp = self.client.get(f"/api/documents/{root.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "v1-content")

    def test_retrieve_with_version_param_returns_selected_version_content(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        v1 = Document.objects.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="v1-content",
        )

        resp = self.client.get(f"/api/documents/{root.id}/?version={v1.id}")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "v1-content")

    def _make_root_with_out_of_order_versions(self) -> tuple[Document, ...]:
        """
        A root whose newest version has a *lower* id than an older one, which is
        what merging an existing document in as a version produces.
        """
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root-content",
        )
        newest = Document.objects.create(
            title="newest",
            checksum="newest",
            mime_type="application/pdf",
            content="newest-content",
        )
        older = Document.objects.create(
            title="older",
            checksum="older",
            mime_type="application/pdf",
            root_document=root,
            version_index=1,
            content="older-content",
        )
        # Assigned last, so `newest` has the lower id despite being the later version
        newest.root_document = root
        newest.version_index = 2
        newest.save()
        return root, newest, older

    def test_retrieve_uses_version_index_not_id_for_latest(self) -> None:
        root, _, _ = self._make_root_with_out_of_order_versions()

        resp = self.client.get(f"/api/documents/{root.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "newest-content")

    def test_list_uses_version_index_not_id_for_latest(self) -> None:
        self._make_root_with_out_of_order_versions()

        resp = self.client.get("/api/documents/?fields=id,content")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [doc["content"] for doc in resp.data["results"]],
            ["newest-content"],
        )

    def test_versions_are_listed_newest_first_with_root_last(self) -> None:
        root, newest, older = self._make_root_with_out_of_order_versions()

        resp = self.client.get(f"/api/documents/{root.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(version["id"], version["is_root"]) for version in resp.data["versions"]],
            [(newest.id, False), (older.id, False), (root.id, True)],
        )


class TestVersionAwareFilters(DjangoTestCase):
    """
    The filters annotate effective_content themselves rather than relying on
    the caller's queryset carrying it, so they stay version-aware on a plain
    Document queryset (e.g. the bulk-edit "select all matching" path).
    """

    def setUp(self) -> None:
        super().setUp()
        self.root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="superseded-content",
        )
        Document.objects.create(
            title="version",
            checksum="version",
            mime_type="application/pdf",
            root_document=self.root,
            version_index=1,
            content="latest-content",
        )
        self.unversioned = Document.objects.create(
            title="unversioned",
            checksum="unversioned",
            mime_type="application/pdf",
            content="latest-content",
        )

    def test_title_content_filter_matches_latest_version_content(self) -> None:
        result = TitleContentFilter().filter(
            Document.objects.filter(root_document__isnull=True),
            " latest ",
        )

        self.assertCountEqual(
            [doc.id for doc in result],
            [self.root.id, self.unversioned.id],
        )

    def test_effective_content_filter_matches_latest_version_content(self) -> None:
        result = EffectiveContentFilter(lookup_expr="icontains").filter(
            Document.objects.filter(root_document__isnull=True),
            " latest ",
        )

        self.assertCountEqual(
            [doc.id for doc in result],
            [self.root.id, self.unversioned.id],
        )

    def test_effective_content_filter_ignores_superseded_content(self) -> None:
        result = EffectiveContentFilter(lookup_expr="icontains").filter(
            Document.objects.filter(root_document__isnull=True),
            "superseded",
        )

        self.assertEqual(list(result), [])

    def test_filters_reuse_an_existing_annotation(self) -> None:
        """
        Annotating twice under the same alias is an error, so an already
        annotated queryset (the search path) has to be left alone.
        """
        annotated = annotate_effective_content(
            Document.objects.filter(root_document__isnull=True),
        )
        self.assertIs(annotate_effective_content(annotated), annotated)

        result = EffectiveContentFilter(lookup_expr="icontains").filter(
            annotated,
            "latest",
        )

        self.assertCountEqual(
            [doc.id for doc in result],
            [self.root.id, self.unversioned.id],
        )

    def test_bulk_selection_does_not_match_superseded_content(self) -> None:
        """
        Bulk edit's "select all matching" builds its own queryset, so before
        the filters annotated for themselves it matched the root document's
        superseded content -- selecting documents the list view, filtered by
        the same term, does not show.
        """
        user = User.objects.create_superuser(username="bulk_selection")

        selected = DocumentSelectionMixin()._resolve_document_ids(
            user=user,
            validated_data={
                "all": True,
                "filters": {"content__icontains": "superseded"},
            },
        )

        self.assertEqual(selected, [])

    def test_effective_content_filter_returns_input_for_empty_values(self) -> None:
        queryset = mock.Mock()

        result = EffectiveContentFilter(lookup_expr="icontains").filter(queryset, "   ")

        self.assertIs(result, queryset)
        queryset.filter.assert_not_called()


class TestBulkSelectionExcludesVersions(DjangoTestCase):
    def test_select_all_matching_does_not_select_version_documents(self) -> None:
        """
        "Select all matching" reconstructs the document list, which never
        contains version documents as rows of their own.
        """
        user = User.objects.create_superuser(username="bulk_versions")
        root = Document.objects.create(
            title="shared-title root",
            checksum="bulk-root",
            mime_type="application/pdf",
            content="root",
        )
        Document.objects.create(
            title="shared-title version",
            checksum="bulk-version",
            mime_type="application/pdf",
            root_document=root,
            version_index=1,
            content="version",
        )

        selected = DocumentSelectionMixin()._resolve_document_ids(
            user=user,
            validated_data={
                "all": True,
                "filters": {"title__icontains": "shared-title"},
            },
        )

        self.assertEqual(selected, [root.id])
