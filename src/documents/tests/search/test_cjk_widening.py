"""CJK terms in QUERY-mode searches, matched through their bigram fields
in place inside the parsed query.

The content analyzer keeps an unspaced CJK run as one token, so a CJK
term is only findable through the bigram fields. Each CJK leaf is widened
where it sits, so everything around it (AND, NOT, REQUIRE, boosts,
fielding) constrains the bigram match exactly as it constrains the
original term.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Correspondent
from documents.models import Document

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import SettingsWrapper


pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestNegationSymmetry:
    def test_not_excludes_what_the_positive_term_matches(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document whose 東京 sits inside a longer unspaced run
              (indexed as one content token), and a latin-only document,
              both matching "invoice"
        WHEN:
            - "東京" and "invoice NOT 東京" are searched
        THEN:
            - 東京 finds the CJK document, and NOT 東京 excludes that same
              document. A content-only negation never fires here, since
              the content field holds the whole run, not 東京
        """
        cjk = index_document(
            title="A",
            content="東京都の公共文書について invoice",
        )
        latin = index_document(title="B", content="invoice only")

        assert matched_ids("東京") == {cjk.pk}
        assert matched_ids("invoice NOT 東京") == {latin.pk}

    def test_bigram_approximation_is_the_same_on_both_sides(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document mentioning 東京 and 京都 separately, never 東京都
        WHEN:
            - "東京都" and "invoice NOT 東京都" are searched
        THEN:
            - 東京都 matches it (both of its bigrams are present, and the
              bigram match ignores position), and NOT 東京都 excludes it.
              An accepted approximation: a query and its negation agree
        """
        separate = index_document(
            title="A",
            content="東京 と 京都 invoice",
        )
        latin = index_document(title="B", content="invoice only")

        assert matched_ids("東京都") == {separate.pk}
        assert matched_ids("invoice NOT 東京都") == {latin.pk}

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("invoice NOT 東京都", id="term"),
            pytest.param('invoice NOT "東京都"', id="phrase"),
        ],
    )
    def test_a_negated_multi_bigram_run_needs_every_bigram_to_exclude(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        query: str,
    ) -> None:
        """
        GIVEN:
            - A document containing 東京都, and one containing only 京都
              (one of 東京都's two bigrams)
        WHEN:
            - 東京都 is excluded, as a bare term or a quoted phrase
        THEN:
            - Only the 東京都 document is excluded. Sharing one bigram
              with the excluded run is not enough to be excluded
        """
        full = index_document(
            title="A",
            content="東京都の公共文書について invoice",
        )
        partial = index_document(
            title="B",
            content="京都の invoice",
        )

        assert matched_ids("invoice") == {full.pk, partial.pk}
        assert matched_ids(query) == {partial.pk}

    def test_a_run_past_the_length_limit_is_matched_and_excluded(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        long_cjk_run: str,
    ) -> None:
        """
        GIVEN:
            - A document holding a CJK run longer than the content
              analyzer's remove_long limit, and a latin-only document
        WHEN:
            - The long run is searched bare, and excluded with NOT
        THEN:
            - Bare, it matches the document; negated, it excludes that
              document and nothing else. The content side of the run
              analyzes to nothing, which must not erase the NOT
        """
        long = index_document(
            title="A",
            content=f"{long_cjk_run} invoice",
        )
        latin = index_document(title="B", content="invoice only")

        assert matched_ids(long_cjk_run) == {long.pk}
        assert matched_ids(f"invoice NOT {long_cjk_run}") == {latin.pk}


class TestTokenizerDroppedCodepoints:
    @pytest.fixture
    def invoice(self, index_document: Callable[..., Document]) -> Document:
        """One latin "invoice" document, with no U+2E80 anywhere in it."""
        return index_document(title="A", content="invoice only")

    def test_a_regex_only_match_finds_nothing(
        self,
        invoice: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document whose content has nothing resembling U+2E80 (a
              CJK Radicals Supplement codepoint that matches _CJK_RE but
              that the content analyzer's simple tokenizer yields no
              token for at all)
        WHEN:
            - "⺀" is searched
        THEN:
            - Nothing matches: _widen_leaf finds no CJK pieces to widen
              with and returns the leaf as it is, which analyzes to the
              same nothing it always did
        """
        assert matched_ids("⺀") == set()

    def test_not_a_regex_only_match_excludes_nothing(
        self,
        invoice: Document,
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document with no U+2E80 in it
        WHEN:
            - "invoice NOT ⺀" is searched
        THEN:
            - The document still matches: the negated leaf widens to
              nothing extra, exactly as an unwidened NOT of a term with
              no matches would behave
        """
        assert matched_ids("invoice NOT ⺀") == {invoice.pk}


class TestStructureConstrainsTheCjkMatch:
    @pytest.fixture
    def pks(self, index_document: Callable[..., Document]) -> dict[str, int]:
        """One document with both 東京 and "invoice", one with only 東京."""
        return {
            "both": index_document(title="A", content="東京都の請求書 invoice").pk,
            "cjk_only": index_document(title="B", content="東京 report").pk,
        }

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            pytest.param("東京 AND invoice", {"both"}, id="and"),
            pytest.param("東京 REQUIRE invoice", {"both"}, id="require"),
            pytest.param("東京^2 AND invoice", {"both"}, id="boosted"),
            pytest.param("東京 ANDMAYBE invoice", {"both", "cjk_only"}, id="andmaybe"),
        ],
    )
    def test_a_latin_operand_still_constrains_the_cjk_term(
        self,
        matched_ids: Callable[[str], set[int]],
        pks: dict[str, int],
        query: str,
        expected: set[str],
    ) -> None:
        """
        GIVEN:
            - One document with both 東京 and "invoice", one with only 東京
        WHEN:
            - 東京 is combined with "invoice" by AND, REQUIRE, a boosted
              AND, or ANDMAYBE
        THEN:
            - AND and REQUIRE (boosted or not) need "invoice" too, so only
              the document with both matches; ANDMAYBE leaves "invoice"
              optional, so both match
        """
        assert matched_ids(query) == {pks[label] for label in expected}


class TestFieldedTerms:
    def test_a_fielded_multi_run_term_matches_through_either_run(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with 東京 and 大阪, and one with only 東京, both
              containing "report"
        WHEN:
            - "content:東京・大阪 AND report" is searched (the content
              analyzer splits 東京・大阪 into two tokens)
        THEN:
            - Both match. The original side still ANDs its two content
              tokens, pinned in test_cjk_leaf_rewrite.py, but the bigram
              side accepts either run, so the 東京-only document comes
              back through it. The AND still binds: "report" is required
              of both. This is what the separate bigram clause returned
              before this change
        """
        both = index_document(title="A", content="東京 大阪 report")
        one = index_document(title="B", content="東京 report")

        assert matched_ids("content:東京・大阪 AND report") == {
            both.pk,
            one.pk,
        }

    def test_a_run_is_matched_wherever_it_appears_in_the_text(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document holding 大阪 and 東京 apart, inside one unspaced
              run (大阪府と東京都), a document with only 東京, and one
              with neither
        WHEN:
            - "content:東京・大阪" is searched
        THEN:
            - The first two match and the third does not. Each run is
              searched on its own, so no bigram spanning the gap between
              the runs is required, and either run on its own is enough
        """
        apart = index_document(title="A", content="大阪府と東京都")
        one = index_document(title="B", content="東京 report")
        index_document(title="C", content="report only")

        assert matched_ids("content:東京・大阪") == {apart.pk, one.pk}

    def test_an_unfielded_multi_run_term_matches_on_either_run(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with both CJK runs, one with only the first run,
              and one with neither, all containing "invoice"
        WHEN:
            - The two runs are searched as one unfielded term (東京・大阪)
        THEN:
            - Both CJK documents match. An unfielded term is copied across
              the default fields inside an Or, so the leaf's own semantics
              are "either"; the bigram side matches that, and returns what
              the separate bigram clause returned before this change
        """
        both = index_document(
            title="A",
            content="大阪府と東京都の報告 invoice",
        )
        one = index_document(
            title="B",
            content="東京都の報告書 invoice",
        )
        index_document(title="C", content="invoice only")

        assert matched_ids("東京・大阪") == {both.pk, one.pk}

    def test_a_negated_multi_run_term_excludes_on_either_run(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Documents containing both runs of a glued mixed term, only
              its first run, only its second run, and neither, all
              containing "invoice"
        WHEN:
            - "invoice NOT 東京report資料" is searched
        THEN:
            - Only the document with neither run survives. The negation
              excludes exactly what the positive term matches, and the
              positive term matches on either run, so the exclusion is
              wider than an "only documents holding both" reading. Today
              this query excludes nothing at all
        """
        index_document(
            title="A",
            content="東京都のreport資料です invoice",
        )
        index_document(title="B", content="東京都の報告 invoice")
        index_document(title="C", content="参考資料の一覧 invoice")
        neither = index_document(title="D", content="invoice only")

        assert matched_ids("invoice NOT 東京report資料") == {neither.pk}

    def test_a_bigram_field_name_is_not_query_syntax(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document holding 東京 in its content
        WHEN:
            - A query naming an internal bigram field as a field prefix is
              searched end to end (bigram_content:東京)
        THEN:
            - Nothing matches. The prefix is not query syntax, so the
              whole thing is plain text: the literal token
              "bigram_content" is required on the leaf's own field, and no
              document holds it. Asserted through the real search path, so
              that parsing with the emit registry instead of the public
              one would fail this test. A unit-level wc.parse() assertion
              would not: it pins whoosh-compat's handling of an unknown
              prefix rather than our choice of parse registry
        """
        index_document(title="A", content="東京都の報告書")

        assert matched_ids("bigram_content:東京") == set()


class TestMixedScript:
    def test_separated_latin_is_required(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with 東京 and "report" as separate words, and one
              with 東京 but no "report"
        WHEN:
            - "東京-report" is searched (the content analyzer splits it into
              東京 and report)
        THEN:
            - Only the document with both matches: the latin piece is
              required beside the CJK run's bigrams
        """
        both = index_document(title="A", content="東京都の report")
        index_document(title="B", content="東京都の invoice")

        assert matched_ids("東京-report") == {both.pk}

    def test_glued_latin_is_not_required(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document where the latin text is glued to other CJK text
              (東京都のreport資料, one content token), and one with 東京
              but no "report" at all
        WHEN:
            - "東京report" is searched (one token: latin glued to CJK)
        THEN:
            - Both match through 東京's bigrams. Glued latin is only ever
              indexed inside a whole unspaced token, so requiring it would
              have lost the first document
        """
        glued = index_document(
            title="A",
            content="東京都のreport資料",
        )
        other = index_document(
            title="B",
            content="東京都の invoice",
        )

        assert matched_ids("東京report") == {glued.pk, other.pk}

    def test_not_a_separated_mixed_term_excludes_only_documents_with_both(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Three "invoice" documents: with 東京 and "report", with 東京
              only, and latin only
        WHEN:
            - "invoice NOT 東京-report" is searched
        THEN:
            - Only the document with both is excluded, not every document
              mentioning 東京
        """
        index_document(
            title="A",
            content="東京都の report invoice",
        )
        cjk_only = index_document(
            title="B",
            content="東京都の invoice",
        )
        latin = index_document(title="C", content="invoice only")

        assert matched_ids("invoice NOT 東京-report") == {
            cjk_only.pk,
            latin.pk,
        }

    def test_a_one_character_run_is_not_required(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document containing 大阪 but not 東
        WHEN:
            - "content:東・大阪" is searched
        THEN:
            - It matches: a one-character run has no bigram, so only 大阪
              is required. An accepted gap, the same under NOT
        """
        osaka = index_document(title="A", content="大阪府の報告書")

        assert matched_ids("content:東・大阪") == {osaka.pk}


class TestQuotedPhrase:
    """A quoted CJK phrase must not match more than the same words unquoted.

    The bigram fields put every token at position 0, so no alternative
    built from them can enforce adjacency. Requiring both runs is the
    tightest thing available, and the floor: the parser's default group is
    And, so anything looser would make quoting widen the search.
    """

    @pytest.fixture
    def pks(self, index_document: Callable[..., Document]) -> dict[str, int]:
        return {
            "tokyo": index_document(
                title="A",
                content="東京都の報告書 invoice",
            ).pk,
            "osaka": index_document(
                title="B",
                content="大阪府の報告書 invoice",
            ).pk,
            "both": index_document(
                title="C",
                content="東京都と大阪府の報告書 invoice",
            ).pk,
        }

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("東京都 大阪府", id="unquoted"),
            pytest.param('"東京都 大阪府"', id="quoted"),
        ],
    )
    def test_both_words_are_required_either_way(
        self,
        matched_ids: Callable[[str], set[int]],
        pks: dict[str, int],
        query: str,
    ) -> None:
        """
        GIVEN:
            - Three documents, holding only the first word, only the
              second, and both
        WHEN:
            - The two words are searched unquoted and as a quoted phrase
        THEN:
            - Only the document holding both matches, either way. Quoting
              asks for more than the bare words, never less
        """
        assert matched_ids(query) == {pks["both"]}

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("invoice NOT (東京都 大阪府)", id="unquoted"),
            pytest.param('invoice NOT "東京都 大阪府"', id="quoted"),
        ],
    )
    def test_the_negation_excludes_only_what_the_phrase_matches(
        self,
        matched_ids: Callable[[str], set[int]],
        pks: dict[str, int],
        query: str,
    ) -> None:
        """
        GIVEN:
            - The same three documents, all matching "invoice"
        WHEN:
            - The two words are excluded, grouped and as a quoted phrase
        THEN:
            - Only the document holding both words is excluded. The
              negation is the mirror of the positive side, so a phrase
              that required either word would take the two single-word
              documents out with it
        """
        assert matched_ids(query) == {pks["tokyo"], pks["osaka"]}


class TestOtherDefaultFields:
    @pytest.mark.parametrize("where", ["title", "correspondent"])
    def test_not_excludes_a_cjk_match_outside_content(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        where: str,
    ) -> None:
        """
        GIVEN:
            - An "invoice" document whose only 東京 is inside a longer run
              in its title or its correspondent, and a latin-only one
        WHEN:
            - "invoice NOT 東京" is searched
        THEN:
            - The CJK document is excluded: every default field's bigram
              companion is widened, not only content's
        """
        kwargs: dict[str, object] = {
            "title": "A",
            "content": "invoice",
        }
        if where == "title":
            kwargs["title"] = "東京都の報告書"
        else:
            kwargs["correspondent"] = Correspondent.objects.create(name="東京電力")
        index_document(**kwargs)
        latin = index_document(
            title="B",
            content="invoice only",
        )

        assert matched_ids("invoice NOT 東京") == {latin.pk}


class TestFuzzyDoesNotReadmit:
    @pytest.mark.parametrize(
        ("query", "threshold", "expected"),
        [
            pytest.param("invoice NOT 東京", None, {"latin"}, id="not_fuzzy_off"),
            pytest.param("invoice NOT 東京", 0.0, {"latin"}, id="not_fuzzy_on"),
            pytest.param("東京 AND invoice", None, {"cjk"}, id="and_fuzzy_off"),
            pytest.param(
                "東京 AND invoice",
                0.0,
                {"cjk"},
                id="and_fuzzy_on",
            ),
        ],
    )
    def test_fuzzy_on_matches_fuzzy_off_for_structure(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        settings: SettingsWrapper,
        query: str,
        threshold: float | None,
        expected: set[str],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document whose 東京 is inside a longer unspaced
              run, a 東京-only document and a latin-only "invoice"
              document, with fuzzy search off or on
        WHEN:
            - "invoice NOT 東京" or "東京 AND invoice" is searched
        THEN:
            - The result is the same whether fuzzy is on or off: fuzzy
              widening happens inside the tree now, so a CJK NOT or AND
              still constrains both the exact and the fuzzy side, and
              neither re-admits what the structure excludes
        """
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = threshold
        cjk = index_document(
            title="A",
            content="東京都の公共文書について invoice",
        )
        cjk_only = index_document(
            title="B",
            content="東京都の報告書",
        )
        latin = index_document(title="C", content="invoice only")
        pks = {"cjk": cjk.pk, "cjk_only": cjk_only.pk, "latin": latin.pk}

        assert matched_ids(query) == {pks[label] for label in expected}
