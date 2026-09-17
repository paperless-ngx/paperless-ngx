"""The words a leaf contributes to its fuzzy alternative.

Each leaf is widened in the tree now, so nothing is re-parsed as a string
and a boolean keyword can no longer be read as grammar. What still has to
hold is that a word is stemmed exactly once (analysis is not idempotent)
and that hyphenated, dotted and quoted terms keep contributing their
words.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document

pytestmark = [
    pytest.mark.search,
    pytest.mark.django_db,
    pytest.mark.usefixtures("fuzzy_enabled"),
]


class TestFuzzyClauseWords:
    def test_a_stemmed_word_is_not_stemmed_a_second_time(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Documents whose content contains "universities", a
              one-transposition typo of it ("universties"), and two
              unrelated words that share its stem prefix ("univalent",
              "unicycle")
        WHEN:
            - Searching for "universities" with the fuzzy blend enabled
        THEN:
            - Only the correctly-spelled document and its typo match; the
              clause does not widen far enough to reach the unrelated
              words. 'universities' stems to 'univers'; feeding that back
              to tantivy would stem it again to 'univ', whose fuzzy prefix
              reaches unrelated words - the clause must stay wide enough
              for a typo and no wider
        """
        wanted = index_document(
            title="A",
            content="universities of europe",
        )
        typo = index_document(
            title="B",
            content="universties of europe",
        )
        index_document(
            title="C",
            content="univalent chemical bonds",
        )
        index_document(
            title="D",
            content="unicycle repair manual",
        )

        assert matched_ids("universities") == {wanted.pk, typo.pk}

    def test_a_hyphenated_term_still_reaches_the_clause(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document whose content contains a near-miss of "COVID-19"
              ("covidx")
        WHEN:
            - Searching for "COVID-19" with the fuzzy blend enabled
        THEN:
            - The document matches; 'COVID-19' is one raw token, so unless
              it is split into words, it carries characters the re-parse
              would read as grammar, is dropped, and the whole query loses
              its fuzzy clause
        """
        misspelled = index_document(
            title="A",
            content="covidx testing results",
        )

        assert matched_ids("COVID-19") == {misspelled.pk}

    def test_a_phrase_still_reaches_the_clause(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document whose content near-misses a quoted phrase
        WHEN:
            - Searching for the quoted phrase '"tax reports"' with the
              fuzzy blend enabled
        THEN:
            - The document matches; a phrase is one raw token carrying a
              space, and is the whole query's only free text here, so it
              must still reach the clause
        """
        near_miss = index_document(
            title="A",
            content="taxation reportage weekly",
        )

        assert matched_ids('"tax reports"') == {near_miss.pk}


class TestBooleanKeywordsInRawText:
    """Tantivy's boolean keywords used to reach its parser with their case
    intact, through the word string the old clause was re-parsed from, so a
    quoted phrase could smuggle grammar in. Leaves are built as AST nodes
    now, which closes that off structurally; these pin it shut."""

    @pytest.fixture
    def corpus(self, index_document: Callable[..., Document]) -> dict[str, int]:
        both = index_document(
            title="A",
            content="taxation reportage weekly",
        )
        tax_only = index_document(
            title="B",
            content="taxation only here",
        )
        report_only = index_document(
            title="C",
            content="reportage only here",
        )
        return {
            "both": both.pk,
            "tax_only": tax_only.pk,
            "report_only": report_only.pk,
        }

    @pytest.mark.parametrize(
        ("keyword_spelling", "ordinary_spelling"),
        [
            pytest.param('"tax AND reports"', '"tax and reports"', id="and"),
            pytest.param('"tax OR reports"', '"tax or reports"', id="or"),
            pytest.param('"tax NOT reports"', '"tax not reports"', id="not"),
            pytest.param('"tax IN reports"', '"tax in reports"', id="in"),
        ],
    )
    def test_a_keyword_inside_a_phrase_stays_an_ordinary_word(
        self,
        matched_ids: Callable[[str], set[int]],
        corpus: dict[str, int],
        keyword_spelling: str,
        ordinary_spelling: str,
    ) -> None:
        """
        GIVEN:
            - Three documents: one with both "taxation" and "reportage",
              one with only "taxation", one with only "reportage"
        WHEN:
            - A quoted phrase carries a tantivy boolean keyword as one of
              its words, spelled in upper case and in lower case
        THEN:
            - Both spellings match the same documents, so the keyword is
              an ordinary word of the phrase rather than grammar: AND does
              not make it a conjunction, NOT does not give it its own
              exclusion, IN does not fail the parse. Only the upper-case
              spelling was ever grammar
        """
        assert matched_ids(keyword_spelling) == matched_ids(ordinary_spelling)

    def test_a_phrase_needs_a_near_match_for_every_word(
        self,
        matched_ids: Callable[[str], set[int]],
        corpus: dict[str, int],
    ) -> None:
        """
        GIVEN:
            - Three documents: one with both "taxation" and "reportage",
              one with only "taxation", one with only "reportage"
        WHEN:
            - '"tax reports"' is searched, both words misspelled
        THEN:
            - Only the document near-matching both words comes back. A
              quoted phrase asks for more than the bare words, so its
              fuzzy side requires every one of them
        """
        assert matched_ids('"tax reports"') == {corpus["both"]}

    def test_a_trailing_keyword_is_just_a_word(
        self,
        matched_ids: Callable[[str], set[int]],
        corpus: dict[str, int],
    ) -> None:
        """
        GIVEN:
            - Three documents: one with both "taxation" and "reportage",
              one with only "taxation", one with only "reportage"
        WHEN:
            - '"tax AND"' is searched, a phrase that used to be a tantivy
              syntax error once the clause was re-parsed as a string
            - The same phrase is searched with the keyword in lower case
        THEN:
            - Both match the same documents, and neither raises. Nothing
              is re-parsed any more, so a trailing keyword cannot cost the
              query its fuzzy side
        """
        assert matched_ids('"tax AND"') == matched_ids('"tax and"')
