from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from documents.conditionals import metadata_etag
from documents.conditionals import preview_etag
from documents.conditionals import thumbnail_last_modified
from documents.models import Document
from documents.tests.utils import DirectoriesMixin
from documents.versioning import resolve_effective_document_by_pk


class TestConditionals(DirectoriesMixin, TestCase):
    def test_metadata_etag_uses_latest_version_for_root_request(self) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root-checksum",
            archive_checksum="root-archive",
            mime_type="application/pdf",
        )
        latest = Document.objects.create(
            title="v1",
            checksum="version-checksum",
            archive_checksum="version-archive",
            mime_type="application/pdf",
            root_document=root,
        )
        request = SimpleNamespace(query_params={})

        self.assertEqual(metadata_etag(request, root.id), latest.checksum)
        self.assertEqual(preview_etag(request, root.id), latest.archive_checksum)

    def test_resolve_effective_doc_returns_none_for_invalid_or_unrelated_version(
        self,
    ) -> None:
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

        invalid_request = SimpleNamespace(query_params={"version": "not-a-number"})
        unrelated_request = SimpleNamespace(
            query_params={"version": str(other_version.id)},
        )

        self.assertIsNone(
            resolve_effective_document_by_pk(root.id, invalid_request).document,
        )
        self.assertIsNone(
            resolve_effective_document_by_pk(root.id, unrelated_request).document,
        )

    def test_thumbnail_last_modified_uses_effective_document_for_cache_key(
        self,
    ) -> None:
        root = Document.objects.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
        )
        latest = Document.objects.create(
            title="v2",
            checksum="v2",
            mime_type="application/pdf",
            root_document=root,
        )
        latest.thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        latest.thumbnail_path.write_bytes(b"thumb")

        request = SimpleNamespace(query_params={})
        with mock.patch(
            "documents.conditionals.get_thumbnail_modified_key",
            return_value="thumb-modified-key",
        ) as get_thumb_key:
            result = thumbnail_last_modified(request, root.id)

        self.assertIsNotNone(result)
        get_thumb_key.assert_called_once_with(latest.id)
