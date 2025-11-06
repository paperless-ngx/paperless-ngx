from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.tasks import cleanup_expired_share_link_bundles
from documents.tests.factories import DocumentFactory
from documents.tests.utils import DirectoriesMixin


class ShareLinkBundleAPITests(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/share_link_bundles/"

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username="bundle_admin")
        self.client.force_authenticate(self.user)
        self.document = DocumentFactory.create()

    @mock.patch("documents.views.build_share_link_bundle.delay")
    def test_create_bundle_triggers_build_job(self, delay_mock):
        payload = {
            "document_ids": [self.document.pk],
            "file_version": ShareLink.FileVersion.ARCHIVE,
            "expiration_days": 7,
        }

        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bundle = ShareLinkBundle.objects.get(pk=response.data["id"])
        self.assertEqual(bundle.documents.count(), 1)
        self.assertEqual(bundle.status, ShareLinkBundle.Status.PENDING)
        delay_mock.assert_called_once_with(bundle.pk)

    def test_create_bundle_rejects_missing_documents(self):
        payload = {
            "document_ids": [9999],
            "file_version": ShareLink.FileVersion.ARCHIVE,
            "expiration_days": 7,
        }

        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_ids", response.data)

    @mock.patch("documents.views.build_share_link_bundle.delay")
    def test_rebuild_bundle_resets_state(self, delay_mock):
        bundle = ShareLinkBundle.objects.create(
            slug="rebuild-slug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.FAILED,
        )
        bundle.documents.set([self.document])
        bundle.last_error = "Something went wrong"
        bundle.size_bytes = 100
        bundle.file_path = "path/to/file.zip"
        bundle.save()

        response = self.client.post(f"{self.ENDPOINT}{bundle.pk}/rebuild/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bundle.refresh_from_db()
        self.assertEqual(bundle.status, ShareLinkBundle.Status.PENDING)
        self.assertEqual(bundle.last_error, "")
        self.assertIsNone(bundle.size_bytes)
        self.assertEqual(bundle.file_path, "")
        delay_mock.assert_called_once_with(bundle.pk)

    def test_rebuild_bundle_rejects_processing_status(self):
        bundle = ShareLinkBundle.objects.create(
            slug="processing-slug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.PROCESSING,
        )
        bundle.documents.set([self.document])

        response = self.client.post(f"{self.ENDPOINT}{bundle.pk}/rebuild/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_download_ready_bundle_streams_file(self):
        bundle_file = Path(self.dirs.media_dir) / "bundles" / "ready.zip"
        bundle_file.parent.mkdir(parents=True, exist_ok=True)
        bundle_file.write_bytes(b"binary-zip-content")

        bundle = ShareLinkBundle.objects.create(
            slug="readyslug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.READY,
            file_path=str(bundle_file),
        )
        bundle.documents.set([self.document])

        self.client.logout()
        response = self.client.get(f"/share/{bundle.slug}/")
        content = b"".join(response.streaming_content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertEqual(content, b"binary-zip-content")
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_download_pending_bundle_returns_202(self):
        bundle = ShareLinkBundle.objects.create(
            slug="pendingslug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.PENDING,
        )
        bundle.documents.set([self.document])

        self.client.logout()
        response = self.client.get(f"/share/{bundle.slug}/")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    @mock.patch("documents.views.build_share_link_bundle.delay")
    def test_download_missing_file_triggers_rebuild(self, delay_mock):
        bundle = ShareLinkBundle.objects.create(
            slug="missingfileslug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.READY,
            file_path=str(Path(self.dirs.media_dir) / "does-not-exist.zip"),
        )
        bundle.documents.set([self.document])

        self.client.logout()
        response = self.client.get(f"/share/{bundle.slug}/")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        bundle.refresh_from_db()
        self.assertEqual(bundle.status, ShareLinkBundle.Status.PENDING)
        delay_mock.assert_called_once_with(bundle.pk)


class ShareLinkBundleTaskTests(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.document = DocumentFactory.create()

    def test_cleanup_expired_share_link_bundles(self):
        expired_path = Path(self.dirs.media_dir) / "expired.zip"
        expired_path.parent.mkdir(parents=True, exist_ok=True)
        expired_path.write_bytes(b"expired")

        active_path = Path(self.dirs.media_dir) / "active.zip"
        active_path.write_bytes(b"active")

        expired_bundle = ShareLinkBundle.objects.create(
            slug="expired-bundle",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.READY,
            expiration=timezone.now() - timedelta(days=1),
            file_path=str(expired_path),
        )
        expired_bundle.documents.set([self.document])

        active_bundle = ShareLinkBundle.objects.create(
            slug="active-bundle",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.READY,
            expiration=timezone.now() + timedelta(days=1),
            file_path=str(active_path),
        )
        active_bundle.documents.set([self.document])

        cleanup_expired_share_link_bundles()

        self.assertFalse(ShareLinkBundle.objects.filter(pk=expired_bundle.pk).exists())
        self.assertTrue(ShareLinkBundle.objects.filter(pk=active_bundle.pk).exists())
        self.assertFalse(expired_path.exists())
        self.assertTrue(active_path.exists())
