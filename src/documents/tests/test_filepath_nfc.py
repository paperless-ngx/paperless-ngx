"""
Tests for NFC Unicode normalization in generate_filename / FilePathTemplate.render().

NFC `ü` (UTF-8: c3 bc) and NFD `ü` (UTF-8: 75 cc 88) are visually identical but
produce different byte sequences.  On Linux (ext4, ZFS) these are distinct filenames.
All paths produced by the templating system must be NFC-normalized.
"""

import unicodedata

import pytest

from documents.file_handling import generate_filename
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import StoragePathFactory


@pytest.mark.django_db
class TestGenerateFilenameNFCNormalization:
    @pytest.mark.parametrize(
        "raw,display",
        [
            (unicodedata.normalize("NFD", "Gemüse"), "Gemüse"),
            (unicodedata.normalize("NFD", "Café"), "Café"),
            (unicodedata.normalize("NFD", "naïve"), "naïve"),
        ],
    )
    def test_nfd_title_normalized_to_nfc(self, settings, raw, display):
        """NFD title must produce NFC path bytes."""
        settings.FILENAME_FORMAT = "{{ title }}"
        nfc = unicodedata.normalize("NFC", display)
        assert raw != nfc  # confirm byte-level difference

        doc = DocumentFactory(title=raw, mime_type="application/pdf")
        result = generate_filename(doc)

        assert str(result) == f"{nfc}.pdf"
        assert str(result).encode() == f"{nfc}.pdf".encode()

    def test_nfd_correspondent_normalized_to_nfc(self, settings):
        """NFD correspondent name must produce NFC path component."""
        settings.FILENAME_FORMAT = "{{ correspondent }}/{{ title }}"
        nfd = unicodedata.normalize("NFD", "Müller")
        nfc = unicodedata.normalize("NFC", "Müller")

        correspondent = CorrespondentFactory(name=nfd)
        doc = DocumentFactory(
            title="invoice",
            correspondent=correspondent,
            mime_type="application/pdf",
        )
        result = generate_filename(doc)

        assert str(result) == f"{nfc}/invoice.pdf"
        assert str(result).encode() == f"{nfc}/invoice.pdf".encode()

    def test_nfd_storage_path_normalized_to_nfc(self, settings):
        """NFD literal in StoragePath.path template must produce NFC path bytes."""
        settings.FILENAME_FORMAT = None
        nfd = unicodedata.normalize("NFD", "Büro")
        nfc = unicodedata.normalize("NFC", "Büro")

        # StoragePath.path is used directly as the format/template string.
        # Literal NFD characters in the template must survive rendering as NFC.
        sp = StoragePathFactory(path=f"{nfd}/{{{{ title }}}}")
        doc = DocumentFactory(title="doc", storage_path=sp, mime_type="application/pdf")
        result = generate_filename(doc)

        assert str(result).encode() == f"{nfc}/doc.pdf".encode()

    def test_nfd_raw_document_title_normalized_to_nfc(self, settings):
        """NFD title accessed via document.title (unsanitized context) must also be NFC."""
        settings.FILENAME_FORMAT = "{{ document.title }}"
        nfd = unicodedata.normalize("NFD", "Café")
        nfc = unicodedata.normalize("NFC", "Café")

        doc = DocumentFactory(title=nfd, mime_type="application/pdf")
        result = generate_filename(doc)

        assert str(result) == f"{nfc}.pdf"
        assert str(result).encode() == f"{nfc}.pdf".encode()
