"""_negated_leaf_ids, the pre-scan that tells the widening hook which
leaves sit under a negation.

A negated leaf keeps its CJK alternative but gets no fuzzy one: with
prefix matching, NOT tax would otherwise exclude "taxi" and "taxonomy",
which is not what excluding a word means. The hook cannot see a leaf's
context, so the tree is walked once up front and the hook compares by
identity.
"""

from __future__ import annotations

import pytest
import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

from documents.search._query import _negated_leaf_ids

pytestmark = pytest.mark.search

_CONTENT = wc.FieldRef("content")


def _term(text: str) -> wc_ast.Term:
    return wc_ast.Term(field=_CONTENT, text=text)


class TestCollection:
    def test_a_bare_tree_has_no_negated_leaves(self) -> None:
        """
        GIVEN:
            - A tree with no negation in it
        WHEN:
            - It is pre-scanned
        THEN:
            - The set is empty
        """
        tree = wc_ast.And(children=(_term("invoice"), _term("report")))

        assert _negated_leaf_ids(tree) == frozenset()

    def test_a_leaf_under_not_is_collected(self) -> None:
        """
        GIVEN:
            - A term under a Not
        WHEN:
            - The tree is pre-scanned
        THEN:
            - That leaf's id is collected, and the positive one is not
        """
        positive = _term("invoice")
        negated = _term("secret")
        tree = wc_ast.And(children=(positive, wc_ast.Not(child=negated)))

        ids = _negated_leaf_ids(tree)

        assert id(negated) in ids
        assert id(positive) not in ids

    def test_the_negative_side_of_andnot_is_collected(self) -> None:
        """
        GIVEN:
            - An AndNot, whose positive and negative sides are both terms
        WHEN:
            - The tree is pre-scanned
        THEN:
            - Only the negative side is collected
        """
        positive = _term("invoice")
        negated = _term("secret")
        tree = wc_ast.AndNot(positive=positive, negative=negated)

        ids = _negated_leaf_ids(tree)

        assert id(negated) in ids
        assert id(positive) not in ids

    def test_every_leaf_beneath_a_negation_is_collected(self) -> None:
        """
        GIVEN:
            - A Not whose child is a group of several leaves, one of them
              a Phrase
        WHEN:
            - The tree is pre-scanned
        THEN:
            - All of them are collected, at any depth and whatever the
              leaf type
        """
        a = _term("alpha")
        b = _term("beta")
        phrase = wc_ast.Phrase(field=_CONTENT, text="gamma delta")
        tree = wc_ast.Not(
            child=wc_ast.Or(
                children=(a, wc_ast.And(children=(b, phrase))),
            ),
        )

        assert _negated_leaf_ids(tree) == frozenset({id(a), id(b), id(phrase)})

    def test_a_double_negation_stays_collected(self) -> None:
        """
        GIVEN:
            - A term under two nested Nots
        WHEN:
            - The tree is pre-scanned
        THEN:
            - It is still collected. The rule is parity-blind on purpose:
              the cost of over-collecting is a lost widening, while
              under-collecting would make a negation exclude far more than
              the user asked
        """
        leaf = _term("tax")
        tree = wc_ast.Not(child=wc_ast.Not(child=leaf))

        assert _negated_leaf_ids(tree) == frozenset({id(leaf)})

    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(
                lambda leaf: wc_ast.Boosted(child=leaf, boost=2.0),
                id="boosted",
            ),
            pytest.param(
                lambda leaf: wc_ast.Require(scored=leaf, filter_only=leaf),
                id="require",
            ),
            pytest.param(
                lambda leaf: wc_ast.AndMaybe(required=leaf, optional=leaf),
                id="andmaybe",
            ),
        ],
    )
    def test_containers_that_are_not_negations_collect_nothing(
        self,
        build,
    ) -> None:
        """
        GIVEN:
            - A leaf inside a container that is not a negation
        WHEN:
            - The tree is pre-scanned
        THEN:
            - Nothing is collected. Only Not.child and AndNot.negative are
              negative positions
        """
        leaf = _term("invoice")

        assert _negated_leaf_ids(build(leaf)) == frozenset()

    def test_a_bare_leaf_is_accepted(self) -> None:
        """
        GIVEN:
            - A tree that is a single leaf, with no container at all
        WHEN:
            - It is pre-scanned
        THEN:
            - The set is empty and nothing raises
        """
        assert _negated_leaf_ids(_term("invoice")) == frozenset()


class TestTotality:
    @pytest.mark.parametrize(
        "node",
        [
            pytest.param(wc_ast.Every(), id="every"),
            pytest.param(wc_ast.Nothing(), id="nothing"),
            pytest.param(
                wc_ast.Wildcard(field=_CONTENT, pattern="inv*"),
                id="wildcard",
            ),
            pytest.param(
                wc_ast.Fuzzy(field=_CONTENT, text="invoce", distance=1, prefix=True),
                id="fuzzy",
            ),
        ],
    )
    def test_an_unrecognised_node_does_not_raise(self, node: wc_ast.Node) -> None:
        """
        GIVEN:
            - A node type the walk does not collect from, including one
              (Fuzzy) that this code will later build itself
        WHEN:
            - It is pre-scanned, bare and under a Not
        THEN:
            - Nothing raises. This function runs outside emit()'s error
              conversion, so an exception here is an unconverted 500
        """
        assert _negated_leaf_ids(node) == frozenset()
        assert _negated_leaf_ids(wc_ast.Not(child=node)) == frozenset()

    def test_a_deep_tree_does_not_exhaust_the_stack(self) -> None:
        """
        GIVEN:
            - A tree nested far deeper than the parser's 200-group cap
        WHEN:
            - It is pre-scanned
        THEN:
            - It completes. The walk is iterative, so depth costs heap
              rather than Python stack frames
        """
        leaf = _term("invoice")
        node: wc_ast.Node = leaf
        for _ in range(5000):
            node = wc_ast.Not(child=node)

        assert _negated_leaf_ids(node) == frozenset({id(leaf)})
