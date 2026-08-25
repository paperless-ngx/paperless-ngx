"""The words the fuzzy blend clause hands back to tantivy's parser.

The clause re-parses a word string through tantivy, which analyzes it
again, so the words must be the query's raw text rather than the analyzed
text (analysis is not idempotent), and must still be split into plain
words so that hyphenated, dotted and quoted terms keep contributing.
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
        """'universities' stems to 'univers'; feeding that back to tantivy
        stems it again to 'univ', whose fuzzy prefix reaches unrelated
        words. The clause must stay wide enough for a typo and no wider."""
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
        """'COVID-19' is one raw token: unless it is split into words, it
        carries characters the re-parse would read as grammar, is dropped,
        and the whole query loses its fuzzy clause."""
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
        """A phrase is one raw token carrying a space, and is the whole
        query's only free text here."""
        near_miss = _index(
            backend,
            title="A",
            content="taxation reportage weekly",
            checksum="fuzz-phrase-1",
        )

        assert _matched_ids(backend, '"tax reports"') == {near_miss.pk}


class TestBooleanKeywordsInRawText:
    """Tantivy's boolean keywords are word runs, so they survive the cut
    into words and its own parser reads them as grammar. Raw query text
    reaches that parser with its case intact, so a quoted phrase can carry
    them in."""

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
        "query",
        [
            pytest.param('"tax AND reports"', id="and"),
            pytest.param('"tax OR reports"', id="or"),
            pytest.param('"tax NOT reports"', id="not"),
            pytest.param('"tax IN reports"', id="in"),
        ],
    )
    def test_a_keyword_inside_a_phrase_stays_an_ordinary_word(
        self,
        backend: TantivyBackend,
        corpus: dict[str, int],
        query: str,
    ) -> None:
        """The phrase asks for three words, so the clause must stay the
        disjunction it is for '"tax reports"': AND must not turn it into a
        conjunction, NOT must not give it its own exclusion, IN must not
        fail the parse."""
        assert _matched_ids(backend, '"tax reports"') == set(corpus.values())
        assert _matched_ids(backend, query) == set(corpus.values())

    def test_a_trailing_keyword_does_not_drop_the_clause(
        self,
        backend: TantivyBackend,
        corpus: dict[str, int],
    ) -> None:
        """'tax AND' is a syntax error to tantivy's parser, which would
        cost the whole query its fuzzy clause."""
        assert _matched_ids(backend, '"tax AND"') == {
            corpus["both"],
            corpus["tax_only"],
        }
