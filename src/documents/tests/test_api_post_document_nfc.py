import unicodedata
from typing import TYPE_CHECKING
from unittest import mock

import celery.result
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

if TYPE_CHECKING:
    from documents.data_models import ConsumableDocument
    from documents.data_models import DocumentMetadataOverrides


@pytest.fixture()
def consume_file_mock():
    with mock.patch("documents.tasks.consume_file.apply_async") as m:
        m.return_value = celery.result.AsyncResult(id="test-task-id")
        yield m


@pytest.fixture()
def directories(tmp_path, settings, _media_settings):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    settings.SCRATCH_DIR = scratch
    return scratch


@pytest.mark.django_db
class TestPostDocumentNFCNormalization:
    def test_nfd_filename_normalized_to_nfc(
        self,
        admin_client,
        consume_file_mock: mock.MagicMock,
        directories,
    ):
        """Uploaded file with NFD filename must have its name stored as NFC."""
        nfd = unicodedata.normalize("NFD", "Rechnung März.pdf")
        nfc = unicodedata.normalize("NFC", "Rechnung März.pdf")

        # Verify our test strings actually differ at the byte level
        assert nfd != nfc

        uploaded = SimpleUploadedFile(
            nfd,
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        response = admin_client.post(
            "/api/documents/post_document/",
            {"document": uploaded},
        )

        assert response.status_code == 200

        task_kwargs = consume_file_mock.call_args.kwargs["kwargs"]
        input_doc: ConsumableDocument = task_kwargs["input_doc"]
        overrides: DocumentMetadataOverrides = task_kwargs["overrides"]

        # The temp file on disk must have an NFC name
        assert input_doc.original_file.name == nfc, (
            f"Expected NFC filename {nfc!r}, got {input_doc.original_file.name!r}"
        )
        # The override filename stored for later use must also be NFC
        assert overrides.filename == nfc, (
            f"Expected NFC override filename {nfc!r}, got {overrides.filename!r}"
        )
        assert unicodedata.is_normalized("NFC", overrides.filename)

    def test_already_nfc_filename_unchanged(
        self,
        admin_client,
        consume_file_mock: mock.MagicMock,
        directories,
    ):
        """Uploaded file with already-NFC filename must pass through unchanged."""
        nfc = unicodedata.normalize("NFC", "Invoice_2024.pdf")

        uploaded = SimpleUploadedFile(
            nfc,
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        response = admin_client.post(
            "/api/documents/post_document/",
            {"document": uploaded},
        )

        assert response.status_code == 200

        task_kwargs = consume_file_mock.call_args.kwargs["kwargs"]
        overrides: DocumentMetadataOverrides = task_kwargs["overrides"]

        assert overrides.filename == nfc
        assert unicodedata.is_normalized("NFC", overrides.filename)
