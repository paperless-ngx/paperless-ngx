"""Fuzzy matching applied inside the parsed query rather than beside it.

With a threshold set, every leaf gains a near-match alternative where it
sits, so fielding, negation, AND and positive filters all constrain the
fuzzy match exactly as they constrain the exact one. The old clause was a
flat bag of words OR'd in at the top level, which none of them reached.

Threshold is 0.0 here so these tests see the matching behavior, not the
score filter. The filter has its own file, test_fuzzy_scoring.py.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from documents.models import Document
from documents.models import StoragePath

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import SettingsWrapper


pytestmark = [pytest.mark.search, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _fuzzy_on(settings: SettingsWrapper) -> None:
    settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.0


class TestStructureIsHonoured:
    @pytest.fixture
    def near_matches_both(
        self,
        index_document: Callable[..., Document],
    ) -> Document:
        """One document near-matching both query words, one only the first."""
        both = index_document(title="A", content="invoices report")
        index_document(title="B", content="invoices only")
        return both

    def test_a_fielded_term_fuzzes_only_that_field(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - One document with a near-miss of the word in its title, one
              with a near-miss in its content only
        WHEN:
            - "title:invoce" is searched
        THEN:
            - Only the title document matches. The old clause searched a
              fielded word across every default field
        """
        titled = index_document(title="Invoces", content="nothing")
        index_document(title="Nothing", content="invoces here")

        assert matched_ids("title:invoce") == {titled.pk}

    def test_every_word_needs_a_near_match(
        self,
        near_matches_both: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document near-matching both words, and one near-matching
              only the first
        WHEN:
            - "invoce reprot" is searched (both words misspelled)
        THEN:
            - Only the document near-matching both survives. The old
              clause OR'd the words, so anything near one of them matched
        """
        assert matched_ids("invoce reprot") == {near_matches_both.pk}

    def test_a_negated_word_is_not_fuzzed(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document containing "taxi" and one containing "tax"
        WHEN:
            - "invoice NOT tax" is searched
        THEN:
            - The "taxi" document survives and the "tax" one does not. A
              negated leaf keeps its exact side only: fuzzing it with
              prefix matching would exclude every word starting near it
        """
        taxi = index_document(title="A", content="invoice taxi fare")
        index_document(title="B", content="invoice tax return")

        assert matched_ids("invoice NOT tax") == {taxi.pk}

    def test_a_negation_inside_a_branch_still_binds(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document containing "secret", one without, and
              a "bill" document
        WHEN:
            - "(invoce AND NOT secret) OR bill" is searched
        THEN:
            - The secret document stays out. The old clause restated only
              top-level conjunctive exclusions, so an Or branch's NOT was
              never applied to the fuzzy side
        """
        index_document(title="A", content="invoices secret")
        clean = index_document(title="B", content="invoices only")
        bill = index_document(title="C", content="bill")

        assert matched_ids("(invoce AND NOT secret) OR bill") == {
            clean.pk,
            bill.pk,
        }

    def test_a_structured_filter_constrains_the_fuzzy_match(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two near-miss documents created in different years
        WHEN:
            - "created:2024 invoce" is searched
        THEN:
            - Only the 2024 one matches. The old blend restated negations
              above the fuzzy clause but never positive constraints, so a
              filter did not reach the fuzzy side at all.

              created is the right field to test with: it is a DATE field,
              so it has no fuzzy side of its own and cannot be widened.
              type: would not test this, because it is an alias for
              document_type, which is one of the five default search
              fields and so gets widened like any other leaf
        """
        matching = index_document(
            title="A",
            content="invoices",
            created=datetime.date(2024, 6, 1),
        )
        index_document(
            title="B",
            content="invoices",
            created=datetime.date(2023, 6, 1),
        )

        assert matched_ids("created:2024 invoce") == {matching.pk}

    def test_a_filter_on_a_non_default_field_constrains_the_fuzzy_match(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two near-miss documents with different storage paths
        WHEN:
            - "path:archive invoce" is searched
        THEN:
            - Only the matching one comes back. storage_path is a TEXT
              field that is NOT one of the default search fields, so it
              gets no fuzzy side; the release note promises this case and
              the date test above does not cover it
        """
        archive = StoragePath.objects.create(name="archive", path="archive/{title}")
        other = StoragePath.objects.create(name="misc", path="misc/{title}")
        matching = index_document(
            title="A",
            content="invoices",
            storage_path=archive,
        )
        index_document(
            title="B",
            content="invoices",
            storage_path=other,
        )

        assert matched_ids("path:archive invoce") == {matching.pk}

    def test_a_require_filters_on_the_widened_side_too(
        self,
        near_matches_both: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document near-matching both words and one near-matching
              only the scored side
        WHEN:
            - "invoce REQUIRE reprot" is searched
        THEN:
            - Only the document near-matching both comes back. The
              filter-only side is unscored but still filters, and it is
              widened like any other leaf, so a near miss satisfies it
        """
        assert matched_ids("invoce REQUIRE reprot") == {near_matches_both.pk}


class TestRecallIsKept:
    def test_a_typo_still_finds_its_document(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A correctly spelled document
        WHEN:
            - A one-edit misspelling is searched
        THEN:
            - It matches. This is what the whole feature is for
        """
        doc = index_document(title="A", content="invoice total")

        assert matched_ids("invoce") == {doc.pk}

    def test_a_hyphenated_term_matches_on_one_word(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document holding a near-miss of one half of a hyphenated
              term
        WHEN:
            - "COVID-19" is searched
        THEN:
            - It matches. The words inside a term are OR'd on the fuzzy
              side, which is the per-word recall the old clause had
        """
        doc = index_document(title="A", content="covidx cases")

        assert matched_ids("COVID-19") == {doc.pk}

    def test_a_word_the_index_cannot_hold_does_not_narrow_the_query(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document
        WHEN:
            - "invoice __" is searched, where __ is characters the
              tokenizer discards entirely
        THEN:
            - It still matches. If such a word got a fuzzy alternative,
              the leaf would collapse to a required clause that can never
              match and the query would return less with fuzzy on than off
        """
        doc = index_document(title="A", content="invoice total")

        assert matched_ids("invoice __") == {doc.pk}

    def test_a_one_character_word_no_longer_matches_everything(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two unrelated documents
        WHEN:
            - "x invoice" is searched, where x is a one-character word no
              document holds
        THEN:
            - Nothing matches. One-character words get no fuzzy side, and
              the exact side requires a term no document has. Today this
              query matches the whole corpus, because a one-character
              prefix fuzzy term matches every term in the field
        """
        index_document(title="A", content="invoice total")
        index_document(title="B", content="unrelated")

        assert matched_ids("x invoice") == set()


class TestCjkAndFuzzyTogether:
    def test_a_cjk_term_keeps_its_bigram_side_with_fuzzy_on(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with a CJK term inside an unspaced run
        WHEN:
            - That term is searched with fuzzy on
        THEN:
            - It matches through the bigram side, which sits in the same
              Or as the fuzzy side and is unaffected by it
        """
        doc = index_document(
            title="A",
            content="東京都の公共文書について",
        )

        assert matched_ids("東京") == {doc.pk}

    def test_a_negated_cjk_term_keeps_its_bigram_side(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document whose only 東京 is inside a run, and
              one with no 東京 at all
        WHEN:
            - "invoice NOT 東京" is searched with fuzzy on
        THEN:
            - The 東京 document is excluded. A negated leaf loses its
              fuzzy side but keeps its CJK one, so the exclusion still
              reaches inside the run
        """
        index_document(title="A", content="invoice 東京都の報告書")
        clean = index_document(title="B", content="invoice only")

        assert matched_ids("invoice NOT 東京") == {clean.pk}


class TestTheHookIsSkipped:
    def test_a_plain_query_passes_no_hook(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        settings: SettingsWrapper,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - Fuzzy off and a query with no CJK in it
        WHEN:
            - It is parsed
        THEN:
            - emit() is called once, with rewrite_leaf=None. Nothing is
              widened, so the query is exactly what it was before any of
              this work
        """
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = None
        from documents.search import _query

        calls: list[object] = []
        real = _query.tantivy_emit

        def spy(*args: object, **kwargs: object) -> object:
            calls.append(kwargs.get("rewrite_leaf"))
            return real(*args, **kwargs)

        monkeypatch.setattr(_query, "tantivy_emit", spy)
        index_document(title="A", content="invoice")

        matched_ids("invoice")

        assert calls == [None]


class TestTheEmitRegistryIsInvisible:
    def test_a_non_cjk_query_gives_the_same_result_under_either_registry(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - A plain latin document and a non-CJK query with fuzzy on,
              which now selects the registry carrying the internal bigram
              fields even though nothing in the query is CJK
        WHEN:
            - The same query runs with that selection forced back to the
              public registry
        THEN:
            - The same documents come back. The bigram fields are absent
              from PUBLIC_FIELDS and the two registries agree on every
              field a query can name, so adding them changes nothing for
              a query that never reaches them
        """
        from documents.search import _query
        from documents.search._registry import get_field_registry

        index_document(title="A", content="invoice total")
        index_document(title="B", content="unrelated")

        with_bigram_fields = matched_ids("invoce")

        monkeypatch.setattr(
            _query,
            "_get_emit_field_registry",
            lambda language: get_field_registry(language),
        )

        assert matched_ids("invoce") == with_bigram_fields


class TestQuotingDoesNotWiden:
    @pytest.fixture
    def pks(self, index_document: Callable[..., Document]) -> dict[str, int]:
        """One document per word, and one holding both."""
        return {
            "tax": index_document(title="A", content="tax invoice").pk,
            "report": index_document(title="B", content="report invoice").pk,
            "both": index_document(title="C", content="tax report").pk,
        }

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("tax report", id="unquoted"),
            pytest.param('"tax report"', id="quoted"),
        ],
    )
    def test_a_quoted_phrase_needs_every_word_like_the_bare_words(
        self,
        matched_ids: Callable[[str], set[int]],
        pks: dict[str, int],
        query: str,
    ) -> None:
        """
        GIVEN:
            - A document per word, and one holding both
        WHEN:
            - The words are searched unquoted and as a quoted phrase
        THEN:
            - Only the document holding both matches, either way. With
              the phrase's words Or'd on the fuzzy side, the quoted form
              matched every document, including near-misses of one word
        """
        assert matched_ids(query) == {pks["both"]}


class TestCjkIsNotFuzzed:
    def test_a_cjk_term_does_not_match_a_run_sharing_its_start(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document holding 東京都 and one holding only 京都, each
              inside a longer unspaced run
        WHEN:
            - "東京" is searched with fuzzy on
        THEN:
            - Only the 東京都 document matches. A prefix Fuzzy over the
              whole run would match the 京都 document too, undoing what
              the bigram fields' multitoken=AND guarantees with fuzzy off
        """
        tokyo = index_document(title="A", content="東京都の報告書")
        index_document(title="B", content="京都の観光案内について")

        assert matched_ids("東京") == {tokyo.pk}
