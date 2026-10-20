"""What survives ADVANCED_FUZZY_SEARCH_THRESHOLD.

The rest of the fuzzy tests run at threshold 0.0 so they see matching
behavior rather than the filter. These run at 0.5, the value the docs
recommend, because the filter has properties of its own that nothing else
covers: a near-miss must not be cut according to how well the query's
correctly spelled words matched, and an exact match must outrank one that
is only partly exact.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import SettingsWrapper

    from documents.models import Document
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

# Long enough that BM25 scores it well below a short document holding the
# same word, which is what makes the spread these tests are about.
_PADDING = "lorem ipsum dolor sit amet " * 40


@pytest.fixture(autouse=True)
def _threshold(settings: SettingsWrapper) -> None:
    settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.5


class TestNearMissesAreNotCutByTheSpread:
    def test_two_equal_near_misses_both_survive(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two documents that both contain a rare correctly spelled
              word and both near-match a misspelled one. One has the rare
              word in its title, the other buried in a long body, so BM25
              scores them very differently
        WHEN:
            - Both words are searched at threshold 0.5
        THEN:
            - Both survive. Neither is a better answer than the other:
              they differ only in where the correctly spelled word sits.
              If the widened tree were scored normally, the fuzzy side
              would inherit the BM25 spread of the correct word and the
              weaker document would be cut
        """
        titled = index_document(
            title="Zarquon",
            content=f"invoices {_PADDING}",
        )
        buried = index_document(
            title="Nothing",
            content=f"{_PADDING} zarquon invoicing",
        )

        assert matched_ids("zarquon invoce") == {titled.pk, buried.pk}

    def test_near_misses_still_rank_among_themselves(
        self,
        backend: TantivyBackend,
        index_document: Callable[..., Document],
    ) -> None:
        """
        GIVEN:
            - A document near-matching the query in several fields and one
              near-matching it in a single field
        WHEN:
            - The misspelled word is searched
        THEN:
            - Both survive, and the multi-field one ranks first. Flat
              scoring alone would tie every near-miss and lose relevance
              ordering entirely, which is what the tiebreak clause exists
              to prevent
        """
        strong = index_document(
            title="Invoices",
            content="invoices for invoicing",
        )
        weak = index_document(title="Nothing", content="invoices")

        hits = backend.search_ids("invoce", user=None)

        assert set(hits) == {strong.pk, weak.pk}
        assert hits[0] == strong.pk


class TestExactOutranksNearMiss:
    def test_a_fully_exact_document_outranks_a_partly_exact_one(
        self,
        backend: TantivyBackend,
        index_document: Callable[..., Document],
    ) -> None:
        """
        GIVEN:
            - A document matching both query words exactly but buried in a
              long body, and one matching the first word exactly several
              times while only near-matching the second
        WHEN:
            - Both words are searched, spelled correctly
        THEN:
            - The fully exact document ranks first. docs/configuration.md
              promises fuzzy results rank below exact matches, and the
              widened tree alone would break it: a partly exact document
              collects real BM25 for what it did match plus a constant for
              what it only near-matched

        Only the ordering is asserted, not that the partly exact document
        survives the threshold. Spec 4.2a accepts that a large enough BM25
        spread still cuts a near-miss, so whether it survives depends on
        the corpus and is not a property to pin.
        """
        index_document(
            title="Invoice Invoice Invoice",
            content="reportage weekly",
        )
        fully = index_document(
            title="Nothing",
            content=f"{_PADDING} invoice report",
        )

        hits = backend.search_ids("invoice report", user=None)

        assert hits[0] == fully.pk
