import unicodedata
from typing import TYPE_CHECKING
from unittest import mock

import celery.result
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from documents.models import Document

if TYPE_CHECKING:
    from documents.data_models import ConsumableDocument


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
class TestUpdateVersionNFCNormalization:
    def test_nfd_filename_normalized_to_nfc(
        self,
        admin_client,
        consume_file_mock: mock.MagicMock,
        directories,
    ):
        """Uploaded new-version file with NFD filename must have its temp name stored as NFC."""
        document = Document.objects.create(
            title="Test",
            content="content",
            checksum="checksum",
            mime_type="application/pdf",
        )

        nfd = unicodedata.normalize("NFD", "Rechnung März.pdf")
        nfc = unicodedata.normalize("NFC", "Rechnung März.pdf")

        assert nfd != nfc

        uploaded = SimpleUploadedFile(
            nfd,
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        response = admin_client.post(
            f"/api/documents/{document.pk}/update_version/",
            {"document": uploaded},
        )

        assert response.status_code == 200

        task_kwargs = consume_file_mock.call_args.kwargs["kwargs"]
        input_doc: ConsumableDocument = task_kwargs["input_doc"]

        assert input_doc.original_file.name == nfc, (
            f"Expected NFC filename {nfc!r}, got {input_doc.original_file.name!r}"
        )
        assert unicodedata.is_normalized("NFC", input_doc.original_file.name)
