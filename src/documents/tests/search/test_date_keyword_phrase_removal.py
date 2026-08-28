"""Pins the correctness gained by deleting the pre-parse
_quote_date_keyword_phrases rewrite.

That rewrite matched date-keyword phrases (e.g. "previous month" after a
date field) anywhere in the raw query string, including inside an
unrelated quoted string, and inserted quotes mid-phrase there too. Its
own docstring gave ``title:"see added:previous month notes"`` as the
example of what it corrupted. whoosh-compat's grammar accepts the same
phrase vocabulary unquoted natively (see TestUnquotedDateKeywordPhrases
in test_acceptance.py), so the rewrite was redundant everywhere it was
safe and actively wrong everywhere it was not. This is the one case that
tells the two apart: a literal title phrase that happens to contain
"added:previous month" as running text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Document

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


class TestQuotedStringContainingDateKeywordText:
    """A quoted title phrase containing the literal text
    "added:previous month" as running words must match on that literal
    text alone, never spill into an unfielded search for "previous" and
    "month" across the default search fields the way the deleted rewrite
    would have decomposed it into."""

    def test_matches_only_the_literal_phrase(
        self,
        backend: TantivyBackend,
    ) -> None:
        literal = _index(
            backend,
            title="see added:previous month notes",
            content="quarterly filing",
            checksum="dkp-literal",
            archive_serial_number=920,
        )
        # Under the deleted rewrite, this decoy would incorrectly match:
        # its title contains the "see added:" and " notes" fragments the
        # corrupted parse required as title phrases, and its content
        # supplies "previous" and "month" as the decomposed word-match
        # clauses the rewrite turned the middle of the phrase into.
        decoy = _index(
            backend,
            title="see added: quarterly report notes",
            content="we reviewed the previous statement about month end",
            checksum="dkp-decoy",
            archive_serial_number=921,
        )
        query = 'title:"see added:previous month notes"'
        assert _matched_ids(backend, query) == {literal.pk}
        assert decoy.pk not in _matched_ids(backend, query)
