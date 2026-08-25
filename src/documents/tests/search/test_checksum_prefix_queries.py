"""``checksum`` wildcard patterns stay literal end to end, once user queries
route through whoosh-compat.

The registry-level fact (the pattern normalizer folds a KEYWORD pattern
rather than stemming it) is pinned on its own in
``test_keyword_pattern_literal.py``. This proves it actually reaches a real
query: ``checksum:ceded*`` must match only the document whose checksum
starts with "ceded", not the one whose checksum stems to the same run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Document

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

CEDEF00D = "cedef00ddeadbeef0123456789abcdef01234567"
CEDEDEAD = "cededeadbeef567801234567" + "89abcdef01234567"


class TestChecksumPrefixQueries:
    @pytest.fixture
    def indexed(self, backend: TantivyBackend) -> None:
        for i, checksum in enumerate((CEDEF00D, CEDEDEAD)):
            doc = Document.objects.create(
                title=f"Checksum doc {i}",
                content="invoices for the quarter",
                checksum=checksum,
                archive_serial_number=940 + i,
            )
            backend.add_or_update(doc)

    def _ids(self, backend: TantivyBackend, query: str) -> set[int]:
        return set(backend.search_ids(query, user=None))

    def test_prefix_matches_only_the_document_that_starts_with_it(
        self,
        backend: TantivyBackend,
        indexed: None,
    ) -> None:
        matched = self._ids(backend, "checksum:ceded*")
        expected = Document.objects.get(checksum=CEDEDEAD).pk
        assert matched == {expected}

    def test_text_prefix_still_reaches_the_stemmed_index(
        self,
        backend: TantivyBackend,
        indexed: None,
    ) -> None:
        assert len(self._ids(backend, "invoice*")) == 2
