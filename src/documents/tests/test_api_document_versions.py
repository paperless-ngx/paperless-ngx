from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import TestCase
from unittest import mock

from auditlog.models import LogEntry  # type: ignore[import-untyped]
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from documents.data_models import DocumentSource
from documents.filters import EffectiveContentFilter
from documents.filters import TitleContentFilter
from documents.models import Document
from documents.tests.utils import DirectoriesMixin

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

        with mock.patch("documents.index.remove_document_from_index"):
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

        with (
            mock.patch("documents.index.remove_document_from_index"),
            mock.patch("documents.index.add_or_update_document"),
        ):
            resp = self.client.delete(f"/api/documents/{root.id}/versions/{v2.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Document.objects.filter(id=v2.id).exists())
        self.assertEqual(resp.data["current_version_id"], v1.id)
        root.refresh_from_db()
        self.assertEqual(root.content, "root-content")

        with (
            mock.patch("documents.index.remove_document_from_index"),
            mock.patch("documents.index.add_or_update_document"),
        ):
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

        with (
            mock.patch("documents.index.remove_document_from_index"),
            mock.patch("documents.index.add_or_update_document"),
        ):
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

        with (
            mock.patch("documents.index.remove_document_from_index"),
            mock.patch("documents.index.add_or_update_document"),
        ):
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

        with (
            mock.patch("documents.index.remove_document_from_index") as remove_index,
            mock.patch("documents.index.add_or_update_document") as add_or_update,
        ):
            resp = self.client.delete(
                f"/api/documents/{root.id}/versions/{version.id}/",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        remove_index.assert_called_once_with(version)
        add_or_update.assert_called_once()
        self.assertEqual(add_or_update.call_args[0][0].id, root.id)

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
        self.assertEqual(resp.content, b"version")

        resp = self.client.get(
            f"/api/documents/{root.id}/preview/?version={version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.content, b"version")

        resp = self.client.get(
            f"/api/documents/{root.id}/thumb/?version={version.id}",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.content, b"thumb")

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
            consume_mock.delay.return_value = async_task
            resp = self.client.post(
                f"/api/documents/{version.id}/update_version/",
                {"document": upload, "version_label": "  New Version  "},
                format="multipart",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, "task-123")
        consume_mock.delay.assert_called_once()
        input_doc, overrides = consume_mock.delay.call_args[0]
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
            consume_mock.delay.side_effect = Exception("boom")
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


class TestVersionAwareFilters(TestCase):
    def test_title_content_filter_falls_back_to_content(self) -> None:
        queryset = mock.Mock()
        fallback_queryset = mock.Mock()
        queryset.filter.side_effect = [FieldError("missing field"), fallback_queryset]

        result = TitleContentFilter().filter(queryset, " latest ")

        self.assertIs(result, fallback_queryset)
        self.assertEqual(queryset.filter.call_count, 2)

    def test_effective_content_filter_falls_back_to_content_lookup(self) -> None:
        queryset = mock.Mock()
        fallback_queryset = mock.Mock()
        queryset.filter.side_effect = [FieldError("missing field"), fallback_queryset]

        result = EffectiveContentFilter(lookup_expr="icontains").filter(
            queryset,
            " latest ",
        )

        self.assertIs(result, fallback_queryset)
        first_kwargs = queryset.filter.call_args_list[0].kwargs
        second_kwargs = queryset.filter.call_args_list[1].kwargs
        self.assertEqual(first_kwargs, {"effective_content__icontains": "latest"})
        self.assertEqual(second_kwargs, {"content__icontains": "latest"})

    def test_effective_content_filter_returns_input_for_empty_values(self) -> None:
        queryset = mock.Mock()

        result = EffectiveContentFilter(lookup_expr="icontains").filter(queryset, "   ")

        self.assertIs(result, queryset)
        queryset.filter.assert_not_called()
