"""
Tests for NFC Unicode normalization in generate_filename / FilePathTemplate.render().

NFC `ü` (UTF-8: c3 bc) and NFD `ü` (UTF-8: 75 cc 88) are visually identical but
produce different byte sequences.  On Linux (ext4, ZFS) these are distinct filenames.
All paths produced by the templating system must be NFC-normalized.
"""

import unicodedata

import pytest

from documents.file_handling import generate_filename
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import StoragePathFactory
from documents.tests.factories import TagFactory


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


@pytest.mark.django_db
class TestContextBuilderNFCNormalization:
    """
    Defense-in-depth: context builder functions must NFC-normalize string inputs
    before passing them to sanitize_filename().  Task 1 already normalizes the
    final rendered path via clean_filepath(), so these tests may already pass;
    they exist as regression guards for the context-builder layer.
    """

    def test_nfd_tag_name_normalized_in_tag_list(self, settings):
        """NFD tag name must appear as NFC bytes in the {{ tag_list }} shorthand."""
        settings.FILENAME_FORMAT = "{{ tag_list }}/{{ title }}"
        nfd = unicodedata.normalize("NFD", "Büro")
        nfc = unicodedata.normalize("NFC", "Büro")
        assert nfd != nfc  # confirm they differ at byte level

        tag = TagFactory(name=nfd)
        doc = DocumentFactory(title="doc", mime_type="application/pdf")
        doc.tags.set([tag])

        result = generate_filename(doc)

        assert str(result).encode() == f"{nfc}/doc.pdf".encode()

    def test_nfd_original_name_normalized_to_nfc(self, settings):
        settings.FILENAME_FORMAT = "{{ original_name }}"
        nfd = unicodedata.normalize("NFD", "Rechnung März")
        nfc = unicodedata.normalize("NFC", "Rechnung März")

        doc = DocumentFactory(
            original_filename=f"{nfd}.pdf",
            mime_type="application/pdf",
        )
        result = generate_filename(doc)

        assert str(result).encode() == f"{nfc}.pdf".encode()

    def test_nfd_custom_field_string_value_normalized(self, settings):
        """NFD value in a STRING-type custom field must appear as NFC in the context."""
        settings.FILENAME_FORMAT = (
            "{{ custom_fields['Location']['value'] }}/{{ title }}"
        )
        nfd_value = unicodedata.normalize("NFD", "Düsseldorf")
        nfc_value = unicodedata.normalize("NFC", "Düsseldorf")
        assert nfd_value != nfc_value

        doc = DocumentFactory(title="report", mime_type="application/pdf")
        cf = CustomField.objects.create(
            name="Location",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=cf,
            value_text=nfd_value,
        )

        result = generate_filename(doc)

        assert str(result).encode() == f"{nfc_value}/report.pdf".encode()

    def test_nfd_custom_field_name_normalized_as_key(self, settings):
        """NFD characters in a custom field name must appear as NFC in the context dict key."""
        nfd_name = unicodedata.normalize("NFD", "Größe")
        nfc_name = unicodedata.normalize("NFC", "Größe")
        assert nfd_name != nfc_name

        settings.FILENAME_FORMAT = f"{{% if custom_fields['{nfc_name}'] %}}{{{{ custom_fields['{nfc_name}']['value'] }}}}/{{{{ title }}}}{{% else %}}{{{{ title }}}}{{% endif %}}"

        doc = DocumentFactory(title="letter", mime_type="application/pdf")
        cf = CustomField.objects.create(
            name=nfd_name,
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=cf,
            value_text="Berlin",
        )

        result = generate_filename(doc)

        # If field name key is NFC-normalized, the template condition succeeds
        # and result is "Berlin/letter.pdf"; otherwise it falls back to "letter.pdf"
        assert str(result) == "Berlin/letter.pdf"

    def test_nfd_tag_name_list_normalized_to_nfc(self, settings):
        """NFD tag names in tag_name_list must appear as NFC bytes when iterated."""
        settings.FILENAME_FORMAT = (
            "{% for t in tag_name_list %}{{ t }}{% endfor %}/{{ title }}"
        )
        nfd = unicodedata.normalize("NFD", "Büro")
        nfc = unicodedata.normalize("NFC", "Büro")
        assert nfd != nfc  # confirm byte-level difference

        doc = DocumentFactory(title="doc", mime_type="application/pdf")
        doc.tags.add(TagFactory(name=nfd))
        result = generate_filename(doc)

        assert str(result).encode() == f"{nfc}/doc.pdf".encode()
