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

from documents.models import Document

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


@pytest.fixture(autouse=True)
def fuzzy_enabled(settings: SettingsWrapper) -> None:
    """Enable the fuzzy blend clause. The threshold doubles as a minimum
    score filter, so it is set to 0.0: every hit passes and the test sees
    the clause's matching behaviour, not the filter's."""
    settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.0


class TestFuzzyClauseWords:
    def test_a_stemmed_word_is_not_stemmed_a_second_time(
        self,
        backend: TantivyBackend,
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
        wanted = _index(
            backend,
            title="A",
            content="universities of europe",
            checksum="fuzz-stem-1",
        )
        typo = _index(
            backend,
            title="B",
            content="universties of europe",
            checksum="fuzz-stem-2",
        )
        _index(
            backend,
            title="C",
            content="univalent chemical bonds",
            checksum="fuzz-stem-3",
        )
        _index(
            backend,
            title="D",
            content="unicycle repair manual",
            checksum="fuzz-stem-4",
        )

        assert _matched_ids(backend, "universities") == {wanted.pk, typo.pk}

    def test_a_hyphenated_term_still_reaches_the_clause(
        self,
        backend: TantivyBackend,
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
        misspelled = _index(
            backend,
            title="A",
            content="covidx testing results",
            checksum="fuzz-hyphen-1",
        )

        assert _matched_ids(backend, "COVID-19") == {misspelled.pk}

    def test_a_phrase_still_reaches_the_clause(
        self,
        backend: TantivyBackend,
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
        near_miss = _index(
            backend,
            title="A",
            content="taxation reportage weekly",
            checksum="fuzz-phrase-1",
        )

        assert _matched_ids(backend, '"tax reports"') == {near_miss.pk}


class TestBooleanKeywordsInRawText:
    """Tantivy's boolean keywords used to reach its parser with their case
    intact, through the word string the old clause was re-parsed from, so a
    quoted phrase could smuggle grammar in. Leaves are built as AST nodes
    now, which closes that off structurally; these pin it shut."""

    @pytest.fixture
    def corpus(self, backend: TantivyBackend) -> dict[str, int]:
        both = _index(
            backend,
            title="A",
            content="taxation reportage weekly",
            checksum="fuzz-kw-1",
        )
        tax_only = _index(
            backend,
            title="B",
            content="taxation only here",
            checksum="fuzz-kw-2",
        )
        report_only = _index(
            backend,
            title="C",
            content="reportage only here",
            checksum="fuzz-kw-3",
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
        backend: TantivyBackend,
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
        assert _matched_ids(backend, keyword_spelling) == _matched_ids(
            backend,
            ordinary_spelling,
        )

    def test_a_phrase_needs_a_near_match_for_every_word(
        self,
        backend: TantivyBackend,
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
        assert _matched_ids(backend, '"tax reports"') == {corpus["both"]}

    def test_a_trailing_keyword_is_just_a_word(
        self,
        backend: TantivyBackend,
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
        assert _matched_ids(backend, '"tax AND"') == _matched_ids(
            backend,
            '"tax and"',
        )
