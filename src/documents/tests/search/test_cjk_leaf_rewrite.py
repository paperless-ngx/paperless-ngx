"""_widen_cjk_leaf, the rewrite_leaf hook that makes CJK runs matchable in
QUERY mode.

Unit tests against hand-built trees, no index needed: the hook on its own,
then the tree wc.analyze() builds around it. Result-level proof against a
real corpus lives in test_cjk_widening.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

from documents.search._query import _DEFAULT_SEARCH_FIELDS
from documents.search._query import _FIELD_BOOSTS
from documents.search._query import _get_emit_field_registry
from documents.search._query import _widen_leaf
from documents.search._registry import get_field_registry
from documents.tests.search._ast_helpers import BIGRAM_CONTENT
from documents.tests.search._ast_helpers import BIGRAM_TITLE
from documents.tests.search._ast_helpers import CONTENT
from documents.tests.search._ast_helpers import NOTES
from documents.tests.search._ast_helpers import TITLE
from documents.tests.search._ast_helpers import bigram
from documents.tests.search._ast_helpers import content

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.search


def _widened(original: wc_ast.Node, bigram_side: wc_ast.Node) -> wc_ast.Or:
    return wc_ast.Or(children=(original, bigram_side))


def _widen_cjk_leaf(leaf: wc_ast.Term | wc_ast.Phrase) -> wc_ast.Node:
    """The hook as the CJK work used it: no fuzzy side, nothing negated."""
    return _widen_leaf(leaf, fuzzy=False, negated=frozenset())


def _analyze(tree: wc_ast.Node) -> wc_ast.Node:
    return wc.analyze(
        tree,
        _get_emit_field_registry(None),
        rewrite_leaf=_widen_cjk_leaf,
    )


class TestTheHook:
    @pytest.mark.parametrize(
        "leaf",
        [
            pytest.param(content("invoice"), id="latin_term"),
            pytest.param(
                wc_ast.Term(field=NOTES, text="東京"),
                id="non_default_field",
            ),
            pytest.param(wc_ast.Term(field=None, text="東京"), id="unfielded"),
        ],
    )
    def test_leaf_is_returned_unchanged(self, leaf: wc_ast.Term) -> None:
        """
        GIVEN:
            - A leaf with no CJK text, a CJK term on a field outside the
              default search fields, or an unfielded CJK term
        WHEN:
            - The hook is called with it
        THEN:
            - It returns the very same object, which tells analyze() to
              keep the leaf's ordinary analysis
        """
        assert _widen_cjk_leaf(leaf) is leaf

    def test_a_leaf_the_tokenizer_drops_entirely_is_returned_unchanged(self) -> None:
        """
        GIVEN:
            - A term whose text matches _CJK_RE (U+2E80, a CJK Radicals
              Supplement codepoint, so _has_cjk is True) but which the
              content analyzer's simple tokenizer yields no token for at
              all: a few hundred codepoints across the CJK blocks share
              this gap between the regex and the tokenizer
        WHEN:
            - The hook is called with it
        THEN:
            - Neither cjk_terms nor latin_terms gains a piece, and the
              leaf is returned unchanged rather than becoming an empty Or
        """
        leaf = content("⺀")

        assert _widen_cjk_leaf(leaf) is leaf

    def test_the_original_leaf_object_is_the_first_alternative(self) -> None:
        """
        GIVEN:
            - A CJK term on content
        WHEN:
            - The hook widens it
        THEN:
            - The Or's first child is the leaf object itself, not an equal
              copy: analyze() only keeps the leaf's own enclosing-group
              analysis for that exact object
        """
        leaf = content("東京")

        widened = _widen_cjk_leaf(leaf)

        assert isinstance(widened, wc_ast.Or)
        assert widened.children[0] is leaf

    def test_a_cjk_term_gains_a_bigram_alternative_on_its_own_field(self) -> None:
        """
        GIVEN:
            - A CJK term on title
        WHEN:
            - The hook widens it
        THEN:
            - The bigram side targets bigram_title, the leaf's own field's
              companion, so a fielded term stays fielded
        """
        leaf = wc_ast.Term(field=TITLE, text="東京")

        assert _widen_cjk_leaf(leaf) == _widened(
            leaf,
            wc_ast.Term(field=BIGRAM_TITLE, text="東京"),
        )

    def test_each_cjk_run_gets_its_own_bigram_leaf(self) -> None:
        """
        GIVEN:
            - One term whose text holds two CJK runs split by an
              interpunct (東京・大阪)
        WHEN:
            - The hook widens it
        THEN:
            - The bigram side is Or(bigram 東京, bigram 大阪), one leaf
              per run. Joining the runs with a space into one leaf would
              produce bigrams spanning the space, which only exist when
              the two runs sit side by side in a document. The runs are
              alternatives, not requirements: a multi-run term matches on
              any one of its runs, which is what the separate bigram
              clause did before this change
        """
        leaf = content("東京・大阪")

        assert _widen_cjk_leaf(leaf) == _widened(
            leaf,
            wc_ast.Or(children=(bigram("東京"), bigram("大阪"))),
        )

    def test_each_run_keeps_its_own_bigrams_required(self) -> None:
        """
        GIVEN:
            - A term whose two runs each produce more than one bigram
              (東京都・大阪府)
        WHEN:
            - The hook widens it and the tree is analyzed
        THEN:
            - Each run's bigrams stay And-combined inside the cross-run
              Or. The Or is between runs only; multitoken=AND on the
              bigram FieldSpec is what requires a run's own bigrams, and
              it does not inherit from the enclosing group. Without this,
              東京都 would match a document holding only 京都
        """
        assert _analyze(content("東京都・大阪府")) == wc_ast.Or(
            children=(
                wc_ast.And(children=(content("東京都"), content("大阪府"))),
                wc_ast.And(children=(bigram("東京"), bigram("京都"))),
                wc_ast.And(children=(bigram("大阪"), bigram("阪府"))),
            ),
        )

    def test_a_phrase_widens_to_a_bigram_term_not_a_bigram_phrase(self) -> None:
        """
        GIVEN:
            - A quoted CJK phrase on content
        WHEN:
            - The hook widens it
        THEN:
            - The bigram side is a plain Term: the bigram analyzer puts
              every token at position 0, so a positional Phrase against it
              could never match
        """
        leaf = wc_ast.Phrase(field=CONTENT, text="東京都")

        assert _widen_cjk_leaf(leaf) == _widened(leaf, bigram("東京都"))

    def test_a_multi_word_phrase_requires_every_run(self) -> None:
        """
        GIVEN:
            - A quoted CJK phrase holding two words
        WHEN:
            - The hook widens it
        THEN:
            - The runs are And-combined, where a Term's runs are
              Or-combined (test_each_cjk_run_gets_its_own_bigram_leaf).
              The parser's default group is And, so an Or here would let
              the quoted phrase match strictly more than the same two
              words unquoted, and quoting must not widen a search
        """
        leaf = wc_ast.Phrase(field=CONTENT, text="東京都 大阪府")

        assert _widen_cjk_leaf(leaf) == _widened(
            leaf,
            wc_ast.And(children=(bigram("東京都"), bigram("大阪府"))),
        )

    @pytest.mark.parametrize(
        ("leaf", "alternative"),
        [
            pytest.param(
                content("東京-report"),
                wc_ast.And(children=(bigram("東京"), content("report"))),
                id="separated_term",
            ),
            pytest.param(
                wc_ast.Phrase(field=CONTENT, text="東京 report"),
                wc_ast.And(children=(bigram("東京"), content("report"))),
                id="phrase",
            ),
            pytest.param(content("東京report"), bigram("東京"), id="glued"),
        ],
    )
    def test_latin_is_required_only_where_the_analyzer_splits_it_off(
        self,
        leaf: wc_ast.Term | wc_ast.Phrase,
        alternative: wc_ast.Node,
    ) -> None:
        """
        GIVEN:
            - A leaf mixing CJK and latin text, either split into separate
              tokens by the content analyzer (東京-report, "東京 report")
              or glued into one token (東京report)
        WHEN:
            - The hook widens it
        THEN:
            - A separate latin token is required on the leaf's own field
              beside the CJK run's bigrams. Glued latin is not required:
              the index only holds it inside the whole unspaced token, so
              requiring it would lose documents the CJK run finds
        """
        assert _widen_cjk_leaf(leaf) == _widened(leaf, alternative)

    def test_only_latin_pieces_after_a_tokenizer_drop_still_widens(self) -> None:
        """
        GIVEN:
            - A term combining a tokenizer-dropped CJK codepoint (U+2E80)
              with a latin word (⺀report): _has_cjk matches on the
              leading codepoint, but the tokenizer discards it and keeps
              only the "report" token, so no run ever reaches cjk_terms
        WHEN:
            - The hook widens it
        THEN:
            - The alternative is the lone latin term itself, not wrapped
              in And (a single piece collapses to itself), even though
              the CJK side contributed nothing
        """
        leaf = content("⺀report")

        assert _widen_cjk_leaf(leaf) == _widened(leaf, content("report"))

    def test_new_nodes_carry_the_leaf_span(self) -> None:
        """
        GIVEN:
            - A CJK term with a source span, split into two pieces
        WHEN:
            - The hook widens it
        THEN:
            - The Or, the alternative and each piece carry the leaf's
              span, so an emit-time diagnostic still points into the
              query text
        """
        leaf = wc_ast.Term(field=CONTENT, text="東京・大阪", startchar=3, endchar=8)

        widened = _widen_cjk_leaf(leaf)

        assert isinstance(widened, wc_ast.Or)
        alternative = widened.children[1]
        assert isinstance(alternative, wc_ast.Or)
        spans = {
            (node.startchar, node.endchar)
            for node in (widened, alternative, *alternative.children)
        }
        assert spans == {(3, 8)}


class TestAnalyzedTree:
    @pytest.mark.parametrize(
        "node",
        [
            pytest.param(wc_ast.Prefix(field=CONTENT, text="東京"), id="cjk_prefix"),
            pytest.param(
                wc_ast.Wildcard(field=CONTENT, pattern="東*"),
                id="cjk_wildcard",
            ),
        ],
    )
    def test_patterns_are_never_widened(self, node: wc_ast.Node) -> None:
        """
        GIVEN:
            - A CJK prefix or wildcard pattern on content
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - It comes back unchanged: analyze() only offers Term and
              Phrase leaves to the hook
        """
        assert _analyze(node) == node

    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(lambda node: node, id="bare"),
            pytest.param(lambda node: wc_ast.Not(child=node), id="negated"),
        ],
    )
    def test_a_run_past_the_length_limit_keeps_its_bigram_side(
        self,
        build: Callable[[wc_ast.Node], wc_ast.Node],
        long_cjk_run: str,
    ) -> None:
        """
        GIVEN:
            - A CJK run longer than the content analyzer's remove_long
              limit, bare or under NOT
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - The content side drops out and the bigram side stands alone,
              still negated under NOT. A NOT left holding nothing would
              turn into "match everything" instead
        """
        resolved = _get_emit_field_registry(None).resolve(BIGRAM_CONTENT)
        assert resolved is not None
        bigrams = resolved.spec.analyzer(long_cjk_run)

        assert _analyze(build(content(long_cjk_run))) == build(
            wc_ast.And(
                children=tuple(bigram(token) for token in dict.fromkeys(bigrams)),
            ),
        )

    def test_a_one_character_run_drops_out_of_the_alternative(self) -> None:
        """
        GIVEN:
            - A term whose runs are 東 (one character) and 大阪
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - Only 大阪 is required on the bigram side: a one-character run
              has no bigram. An accepted gap, the same on the positive and
              the negated side
        """
        analyzed = _analyze(content("東・大阪"))

        assert analyzed == _widened(
            wc_ast.And(children=(content("東"), content("大阪"))),
            bigram("大阪"),
        )

    def test_the_title_boost_wraps_the_widened_title_leaf(self) -> None:
        """
        GIVEN:
            - An unfielded CJK query parsed the way parse_user_query parses
              it: copied onto every default field, title boosted
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - Each field copy is widened on its own bigram field, and the
              title boost wraps the title copy's whole widened Or, so a
              title bigram match scores like a title match
        """
        parsed = wc.parse(
            "東京",
            registry=get_field_registry(None),
            default_fields=_DEFAULT_SEARCH_FIELDS,
            field_boosts=_FIELD_BOOSTS,
        ).ast

        analyzed = _analyze(parsed)

        assert isinstance(analyzed, wc_ast.Or)
        assert (
            wc_ast.Boosted(
                child=_widened(
                    wc_ast.Term(field=TITLE, text="東京"),
                    wc_ast.Term(field=BIGRAM_TITLE, text="東京"),
                ),
                boost=_FIELD_BOOSTS["title"],
            )
            in analyzed.children
        )
        assert {BIGRAM_CONTENT, wc.FieldRef("bigram_tag")} <= {
            child.field for child in analyzed.children if isinstance(child, wc_ast.Term)
        }

    def test_under_and_the_original_side_keeps_and(self) -> None:
        """
        GIVEN:
            - A term the content analyzer splits into two tokens
              (東京・大阪), inside an And group
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - The original side still ANDs its two tokens. Wrapping the
              leaf in the hook's Or must not turn that into an Or of them.
              The cross-run Or flattens into the widening Or, so the
              alternative is not a single child here and _widened() does
              not fit; the tree is written out literally
        """
        tree = wc_ast.And(children=(content("東京・大阪"), content("report")))

        assert _analyze(tree) == wc_ast.And(
            children=(
                wc_ast.Or(
                    children=(
                        wc_ast.And(children=(content("東京"), content("大阪"))),
                        bigram("東京"),
                        bigram("大阪"),
                    ),
                ),
                content("report"),
            ),
        )

    def test_under_or_the_original_side_keeps_or(self) -> None:
        """
        GIVEN:
            - The same two-token term inside an Or group
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - The original side ORs its tokens, as the group says, and the
              hook's Or flattens into the group
        """
        tree = wc_ast.Or(children=(content("東京・大阪"), content("report")))

        assert _analyze(tree) == wc_ast.Or(
            children=(
                content("東京"),
                content("大阪"),
                bigram("東京"),
                bigram("大阪"),
                content("report"),
            ),
        )

    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(lambda leaf: wc_ast.Not(child=leaf), id="not"),
            pytest.param(
                lambda leaf: wc_ast.AndNot(positive=content("invoice"), negative=leaf),
                id="andnot",
            ),
            pytest.param(
                lambda leaf: wc_ast.AndMaybe(
                    required=content("invoice"),
                    optional=leaf,
                ),
                id="andmaybe",
            ),
            pytest.param(
                lambda leaf: wc_ast.Require(
                    scored=leaf,
                    filter_only=content("invoice"),
                ),
                id="require",
            ),
            pytest.param(
                lambda leaf: wc_ast.Boosted(child=leaf, boost=2.0),
                id="boosted",
            ),
        ],
    )
    def test_the_widened_leaf_stays_where_it_was(
        self,
        build: Callable[[wc_ast.Node], wc_ast.Node],
        long_cjk_run: str,
    ) -> None:
        """
        GIVEN:
            - A CJK term under Not, AndNot, AndMaybe, Require or Boosted,
              beside a latin term
        WHEN:
            - The tree is analyzed with the hook
        THEN:
            - The node keeps its type, its latin operand is untouched, and
              only the CJK leaf is replaced by its widened Or, in the same
              position. A negated CJK leaf is widened too, so a negation
              excludes exactly what the positive search would match
        """
        assert _analyze(build(content("東京"))) == build(
            _widened(content("東京"), bigram("東京")),
        )
