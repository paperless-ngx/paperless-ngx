from __future__ import annotations

import zipfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from rest_framework import status
from rest_framework.test import APITestCase

from documents.filters import ShareLinkBundleFilterSet
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.serialisers import ShareLinkBundleSerializer
from documents.tasks import build_share_link_bundle
from documents.tasks import cleanup_expired_share_link_bundles
from documents.tests.factories import DocumentFactory
from documents.tests.utils import DirectoriesMixin


class ShareLinkBundleAPITests(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/share_link_bundles/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="bundle_admin")
        self.client.force_authenticate(self.user)
        self.document = DocumentFactory.create()

    @mock.patch("documents.views.build_share_link_bundle.delay")
    def test_create_bundle_triggers_build_job(self, delay_mock) -> None:
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

    def test_create_bundle_rejects_missing_documents(self) -> None:
        payload = {
            "document_ids": [9999],
            "file_version": ShareLink.FileVersion.ARCHIVE,
            "expiration_days": 7,
        }

        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_ids", response.data)

    @mock.patch("documents.views.has_perms_owner_aware", return_value=False)
    def test_create_bundle_rejects_insufficient_permissions(self, perms_mock) -> None:
        payload = {
            "document_ids": [self.document.pk],
            "file_version": ShareLink.FileVersion.ARCHIVE,
            "expiration_days": 7,
        }

        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_ids", response.data)
        perms_mock.assert_called()

    @mock.patch("documents.views.build_share_link_bundle.delay")
    def test_rebuild_bundle_resets_state(self, delay_mock) -> None:
        bundle = ShareLinkBundle.objects.create(
            slug="rebuild-slug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.FAILED,
        )
        bundle.documents.set([self.document])
        bundle.last_error = {"message": "Something went wrong"}
        bundle.size_bytes = 100
        bundle.file_path = "path/to/file.zip"
        bundle.save()

        response = self.client.post(f"{self.ENDPOINT}{bundle.pk}/rebuild/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bundle.refresh_from_db()
        self.assertEqual(bundle.status, ShareLinkBundle.Status.PENDING)
        self.assertIsNone(bundle.last_error)
        self.assertIsNone(bundle.size_bytes)
        self.assertEqual(bundle.file_path, "")
        delay_mock.assert_called_once_with(bundle.pk)

    def test_rebuild_bundle_rejects_processing_status(self) -> None:
        bundle = ShareLinkBundle.objects.create(
            slug="processing-slug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.PROCESSING,
        )
        bundle.documents.set([self.document])

        response = self.client.post(f"{self.ENDPOINT}{bundle.pk}/rebuild/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_create_bundle_rejects_duplicate_documents(self) -> None:
        payload = {
            "document_ids": [self.document.pk, self.document.pk],
            "file_version": ShareLink.FileVersion.ARCHIVE,
            "expiration_days": 7,
        }

        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_ids", response.data)

    def test_download_ready_bundle_streams_file(self) -> None:
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

    def test_download_pending_bundle_returns_202(self) -> None:
        bundle = ShareLinkBundle.objects.create(
            slug="pendingslug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.PENDING,
        )
        bundle.documents.set([self.document])

        self.client.logout()
        response = self.client.get(f"/share/{bundle.slug}/")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_download_failed_bundle_returns_503(self) -> None:
        bundle = ShareLinkBundle.objects.create(
            slug="failedslug",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.FAILED,
        )
        bundle.documents.set([self.document])

        self.client.logout()
        response = self.client.get(f"/share/{bundle.slug}/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_expired_share_link_redirects(self) -> None:
        share_link = ShareLink.objects.create(
            slug="expiredlink",
            document=self.document,
            file_version=ShareLink.FileVersion.ORIGINAL,
            expiration=timezone.now() - timedelta(hours=1),
        )

        self.client.logout()
        response = self.client.get(f"/share/{share_link.slug}/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("sharelink_expired=1", response["Location"])

    def test_unknown_share_link_redirects(self) -> None:
        self.client.logout()
        response = self.client.get("/share/unknownsharelink/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("sharelink_notfound=1", response["Location"])


class ShareLinkBundleTaskTests(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.document = DocumentFactory.create()

    def test_cleanup_expired_share_link_bundles(self) -> None:
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

    def test_cleanup_expired_share_link_bundles_logs_on_failure(self) -> None:
        expired_bundle = ShareLinkBundle.objects.create(
            slug="expired-bundle",
            file_version=ShareLink.FileVersion.ARCHIVE,
            status=ShareLinkBundle.Status.READY,
            expiration=timezone.now() - timedelta(days=1),
        )
        expired_bundle.documents.set([self.document])

        with mock.patch.object(
            ShareLinkBundle,
            "delete",
            side_effect=RuntimeError("fail"),
        ):
            with self.assertLogs("paperless.tasks", level="WARNING") as logs:
                cleanup_expired_share_link_bundles()

        self.assertTrue(
            any(
                "Failed to delete expired share link bundle" in msg
                for msg in logs.output
            ),
        )


class ShareLinkBundleBuildTaskTests(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.document = DocumentFactory.create(
            mime_type="application/pdf",
            checksum="123",
        )
        self.document.archive_checksum = ""
        self.document.save()
        self.addCleanup(
            setattr,
            settings,
            "SHARE_LINK_BUNDLE_DIR",
            settings.SHARE_LINK_BUNDLE_DIR,
        )
        settings.SHARE_LINK_BUNDLE_DIR = (
            Path(settings.MEDIA_ROOT) / "documents" / "share_link_bundles"
        )

    def _write_document_file(self, *, archive: bool, content: bytes) -> Path:
        if archive:
            self.document.archive_filename = f"{self.document.pk:07}.pdf"
            self.document.save()
            path = self.document.archive_path
        else:
            path = self.document.source_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_build_share_link_bundle_creates_zip_and_sets_metadata(self) -> None:
        self._write_document_file(archive=False, content=b"source")
        archive_path = self._write_document_file(archive=True, content=b"archive")
        bundle = ShareLinkBundle.objects.create(
            slug="build-archive",
            file_version=ShareLink.FileVersion.ARCHIVE,
        )
        bundle.documents.set([self.document])

        build_share_link_bundle(bundle.pk)

        bundle.refresh_from_db()
        self.assertEqual(bundle.status, ShareLinkBundle.Status.READY)
        self.assertIsNone(bundle.last_error)
        self.assertIsNotNone(bundle.built_at)
        self.assertGreater(bundle.size_bytes or 0, 0)
        final_path = bundle.absolute_file_path
        self.assertIsNotNone(final_path)
        self.assertTrue(final_path.exists())
        with zipfile.ZipFile(final_path) as zipf:
            names = zipf.namelist()
            self.assertEqual(len(names), 1)
            self.assertEqual(zipf.read(names[0]), archive_path.read_bytes())

    def test_build_share_link_bundle_overwrites_existing_file(self) -> None:
        self._write_document_file(archive=False, content=b"source")
        bundle = ShareLinkBundle.objects.create(
            slug="overwrite",
            file_version=ShareLink.FileVersion.ORIGINAL,
        )
        bundle.documents.set([self.document])

        existing = settings.SHARE_LINK_BUNDLE_DIR / "overwrite.zip"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"old")

        build_share_link_bundle(bundle.pk)

        bundle.refresh_from_db()
        final_path = bundle.absolute_file_path
        self.assertIsNotNone(final_path)
        self.assertTrue(final_path.exists())
        self.assertNotEqual(final_path.read_bytes(), b"old")

    def test_build_share_link_bundle_failure_marks_failed(self) -> None:
        self._write_document_file(archive=False, content=b"source")
        bundle = ShareLinkBundle.objects.create(
            slug="fail-bundle",
            file_version=ShareLink.FileVersion.ORIGINAL,
        )
        bundle.documents.set([self.document])

        with (
            mock.patch(
                "documents.tasks.OriginalsOnlyStrategy.add_document",
                side_effect=RuntimeError("zip failure"),
            ),
            mock.patch("pathlib.Path.unlink") as unlink_mock,
        ):
            unlink_mock.side_effect = [OSError("unlink"), OSError("unlink-finally")] + [
                None,
            ] * 5
            with self.assertRaises(RuntimeError):
                build_share_link_bundle(bundle.pk)

        bundle.refresh_from_db()
        self.assertEqual(bundle.status, ShareLinkBundle.Status.FAILED)
        self.assertIsInstance(bundle.last_error, dict)
        self.assertEqual(bundle.last_error.get("message"), "zip failure")
        self.assertEqual(bundle.last_error.get("exception_type"), "RuntimeError")
        scratch_zips = list(Path(settings.SCRATCH_DIR).glob("*.zip"))
        self.assertTrue(scratch_zips)
        for path in scratch_zips:
            path.unlink(missing_ok=True)

    def test_build_share_link_bundle_missing_bundle_noop(self) -> None:
        # Should not raise when bundle does not exist
        build_share_link_bundle(99999)


class ShareLinkBundleFilterSetTests(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.document = DocumentFactory.create()
        self.document.checksum = "doc1checksum"
        self.document.save()
        self.other_document = DocumentFactory.create()
        self.other_document.checksum = "doc2checksum"
        self.other_document.save()
        self.bundle_one = ShareLinkBundle.objects.create(
            slug="bundle-one",
            file_version=ShareLink.FileVersion.ORIGINAL,
        )
        self.bundle_one.documents.set([self.document])
        self.bundle_two = ShareLinkBundle.objects.create(
            slug="bundle-two",
            file_version=ShareLink.FileVersion.ORIGINAL,
        )
        self.bundle_two.documents.set([self.other_document])

    def test_filter_documents_returns_all_for_empty_value(self) -> None:
        filterset = ShareLinkBundleFilterSet(
            data={"documents": ""},
            queryset=ShareLinkBundle.objects.all(),
        )

        self.assertCountEqual(filterset.qs, [self.bundle_one, self.bundle_two])

    def test_filter_documents_handles_invalid_input(self) -> None:
        filterset = ShareLinkBundleFilterSet(
            data={"documents": "invalid"},
            queryset=ShareLinkBundle.objects.all(),
        )

        self.assertFalse(filterset.qs.exists())

    def test_filter_documents_filters_by_multiple_ids(self) -> None:
        filterset = ShareLinkBundleFilterSet(
            data={"documents": f"{self.document.pk},{self.other_document.pk}"},
            queryset=ShareLinkBundle.objects.all(),
        )

        self.assertCountEqual(filterset.qs, [self.bundle_one, self.bundle_two])

    def test_filter_documents_returns_queryset_for_empty_ids(self) -> None:
        filterset = ShareLinkBundleFilterSet(
            data={"documents": ","},
            queryset=ShareLinkBundle.objects.all(),
        )

        self.assertCountEqual(filterset.qs, [self.bundle_one, self.bundle_two])


class ShareLinkBundleModelTests(DirectoriesMixin, APITestCase):
    def test_absolute_file_path_handles_relative_and_absolute(self) -> None:
        relative_path = Path("relative.zip")
        bundle = ShareLinkBundle.objects.create(
            slug="relative-bundle",
            file_version=ShareLink.FileVersion.ORIGINAL,
            file_path=str(relative_path),
        )

        self.assertEqual(
            bundle.absolute_file_path,
            (settings.SHARE_LINK_BUNDLE_DIR / relative_path).resolve(),
        )

        absolute_path = Path(self.dirs.media_dir) / "absolute.zip"
        bundle.file_path = str(absolute_path)

        self.assertEqual(bundle.absolute_file_path.resolve(), absolute_path.resolve())

    def test_str_returns_translated_slug(self) -> None:
        bundle = ShareLinkBundle.objects.create(
            slug="string-slug",
            file_version=ShareLink.FileVersion.ORIGINAL,
        )

        self.assertIn("string-slug", str(bundle))

    def test_remove_file_deletes_existing_file(self) -> None:
        bundle_path = settings.SHARE_LINK_BUNDLE_DIR / "remove.zip"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_bytes(b"remove-me")
        bundle = ShareLinkBundle.objects.create(
            slug="remove-bundle",
            file_version=ShareLink.FileVersion.ORIGINAL,
            file_path=str(bundle_path.relative_to(settings.SHARE_LINK_BUNDLE_DIR)),
        )

        bundle.remove_file()

        self.assertFalse(bundle_path.exists())

    def test_remove_file_handles_oserror(self) -> None:
        bundle_path = settings.SHARE_LINK_BUNDLE_DIR / "remove-error.zip"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_bytes(b"remove-me")
        bundle = ShareLinkBundle.objects.create(
            slug="remove-error",
            file_version=ShareLink.FileVersion.ORIGINAL,
            file_path=str(bundle_path.relative_to(settings.SHARE_LINK_BUNDLE_DIR)),
        )

        with mock.patch("pathlib.Path.unlink", side_effect=OSError("fail")):
            bundle.remove_file()

        self.assertTrue(bundle_path.exists())

    def test_delete_calls_remove_file(self) -> None:
        bundle_path = settings.SHARE_LINK_BUNDLE_DIR / "delete.zip"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_bytes(b"remove-me")
        bundle = ShareLinkBundle.objects.create(
            slug="delete-bundle",
            file_version=ShareLink.FileVersion.ORIGINAL,
            file_path=str(bundle_path.relative_to(settings.SHARE_LINK_BUNDLE_DIR)),
        )

        bundle.delete()
        self.assertFalse(bundle_path.exists())


class ShareLinkBundleSerializerTests(DirectoriesMixin, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.document = DocumentFactory.create()

    def test_validate_document_ids_rejects_duplicates(self) -> None:
        serializer = ShareLinkBundleSerializer(
            data={
                "document_ids": [self.document.pk, self.document.pk],
                "file_version": ShareLink.FileVersion.ORIGINAL,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("document_ids", serializer.errors)

    def test_create_assigns_documents_and_expiration(self) -> None:
        serializer = ShareLinkBundleSerializer(
            data={
                "document_ids": [self.document.pk],
                "file_version": ShareLink.FileVersion.ORIGINAL,
                "expiration_days": 3,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        bundle = serializer.save()

        self.assertEqual(list(bundle.documents.all()), [self.document])
        expected_expiration = timezone.now() + timedelta(days=3)
        self.assertAlmostEqual(
            bundle.expiration,
            expected_expiration,
            delta=timedelta(seconds=10),
        )

    def test_create_raises_when_missing_documents(self) -> None:
        serializer = ShareLinkBundleSerializer(
            data={
                "document_ids": [self.document.pk, 9999],
                "file_version": ShareLink.FileVersion.ORIGINAL,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(serializers.ValidationError):
            serializer.save(documents=[self.document])
