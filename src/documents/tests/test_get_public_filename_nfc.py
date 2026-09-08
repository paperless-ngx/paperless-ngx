import unicodedata
from datetime import date

import pytest

from documents.models import Correspondent
from documents.models import Document


@pytest.mark.django_db
class TestGetPublicFilenameNfc:
    def test_normalizes_nfd_title_to_nfc(self) -> None:
        nfd_title = unicodedata.normalize("NFD", "Gehaltserhöhung")
        assert not unicodedata.is_normalized("NFC", nfd_title)

        doc = Document(
            mime_type="application/pdf",
            title=nfd_title,
            created=date(2025, 10, 17),
        )

        result = doc.get_public_filename()

        assert unicodedata.is_normalized("NFC", result)
        assert (
            result
            == "2025-10-17 "
            + unicodedata.normalize(
                "NFC",
                nfd_title,
            )
            + ".pdf"
        )

    def test_normalizes_nfd_correspondent_name_to_nfc(self) -> None:
        nfd_name = unicodedata.normalize("NFD", "Müller GmbH")
        correspondent = Correspondent.objects.create(name=nfd_name)

        doc = Document.objects.create(
            mime_type="application/pdf",
            title="Rechnung",
            created=date(2025, 10, 17),
            correspondent=correspondent,
        )

        result = doc.get_public_filename()

        assert unicodedata.is_normalized("NFC", result)
