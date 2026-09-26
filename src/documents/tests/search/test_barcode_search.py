"""Stored barcode contents in the search index.

Barcodes are a JSON field like notes and custom fields: barcodes: resolves to
barcodes.value:, and a plain query without the prefix does not look at them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import DocumentBarcode
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestBarcodeSearch:
    @pytest.fixture
    def with_barcodes(self, backend: TantivyBackend) -> Document:
        document = DocumentFactory(title="Letter", content="x")
        DocumentBarcode.objects.create(
            document=document,
            page=1,
            value="WIFI:T:WPA;S:Guest-WLAN;P:crocodile123;;",
            format="QR Code",
        )
        DocumentBarcode.objects.create(
            document=document,
            page=2,
            value="DE89370400440532013000",
            format="Code 128",
        )
        backend.add_or_update(document)
        return document

    def test_bare_barcodes_prefix_searches_values(
        self,
        with_barcodes: Document,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with stored barcodes, and a decoy document whose
              content (not a barcode) contains the same word
        WHEN:
            - A bare "barcodes:" prefix query is run
        THEN:
            - Only the document whose barcode matches is returned, also for a
              part of a barcode between separators
        """
        index_document(title="Decoy", content="crocodile123 in the text")

        assert matched_ids("barcodes:crocodile123") == {with_barcodes.pk}
        assert matched_ids("barcodes.value:DE89370400440532013000") == {
            with_barcodes.pk,
        }

    def test_barcodes_format_subpath(
        self,
        with_barcodes: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with a QR code and a Code 128 barcode
        WHEN:
            - The format subpath is queried
        THEN:
            - The document is found by its barcode formats
        """
        assert matched_ids('barcodes.format:"qr code"') == {with_barcodes.pk}
        assert matched_ids("barcodes.format:aztec") == set()

    def test_plain_query_ignores_barcodes(
        self,
        with_barcodes: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with a barcode value not found in its text
        WHEN:
            - The value is searched without a field prefix
        THEN:
            - Nothing is found, as with notes and custom fields
        """
        assert matched_ids("crocodile123") == set()
