import unicodedata

import pytest

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.matching import consumable_document_matches_workflow
from documents.matching import existing_document_matches_workflow
from documents.models import Document
from documents.models import Workflow
from documents.models import WorkflowTrigger


@pytest.mark.django_db
class TestMatchingNfcNormalization:
    def test_consumable_document_filename_nfd_matches_nfc_pattern(
        self,
        tmp_path,
    ) -> None:
        """
        GIVEN:
            - A file on disk whose name is NFD-normalized
            - A workflow trigger filename filter typed as NFC
        WHEN:
            - The consumable document is checked against the trigger
        THEN:
            - It matches, because both sides are normalized before comparing
        """
        nfd_name = unicodedata.normalize("NFD", "Gehaltserhöhung.pdf")
        nfc_pattern = unicodedata.normalize("NFC", "*Gehaltserhöhung*")
        assert nfd_name != unicodedata.normalize("NFC", nfd_name)

        file_path = tmp_path / nfd_name
        file_path.write_bytes(b"%PDF-1.4 test")

        document = ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=file_path,
        )
        trigger = WorkflowTrigger(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            filter_filename=nfc_pattern,
            sources=[],
        )

        matched, reason = consumable_document_matches_workflow(document, trigger)

        assert matched, reason

    def test_existing_document_filename_nfd_matches_nfc_pattern(self) -> None:
        """
        GIVEN:
            - A Document whose original_filename is NFD-normalized (e.g. from
              before normalization was applied at consumption time)
            - A workflow trigger filename filter typed as NFC
        WHEN:
            - The document is checked against the trigger
        THEN:
            - It matches, because both sides are normalized before comparing
        """
        nfd_name = unicodedata.normalize("NFD", "Gehaltserhöhung.pdf")
        nfc_pattern = unicodedata.normalize("NFC", "*Gehaltserhöhung*")

        document = Document.objects.create(
            title="Test",
            content="content",
            checksum="checksum",
            mime_type="application/pdf",
            original_filename=nfd_name,
        )
        workflow = Workflow.objects.create(name="Test workflow", order=0)
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_filename=nfc_pattern,
        )
        workflow.triggers.add(trigger)

        matched, reason = existing_document_matches_workflow(document, trigger)

        assert matched, reason
