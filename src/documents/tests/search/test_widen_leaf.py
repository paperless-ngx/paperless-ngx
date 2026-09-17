"""_widen_leaf, the hook that adds a CJK alternative, a fuzzy one, or both.

The alternatives are independent: a leaf can qualify for either, and a
negated leaf keeps its CJK side while losing its fuzzy one.
"""

from __future__ import annotations

import pytest
import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

from documents.search._query import _cjk_alternative
from documents.search._query import _fuzzy_alternative
from documents.search._query import _widen_leaf

pytestmark = pytest.mark.search

_CONTENT = wc.FieldRef("content")
_NOTES = wc.FieldRef("notes", "note")


def _content(text: str) -> wc_ast.Term:
    return wc_ast.Term(field=_CONTENT, text=text)


def _widen(
    leaf: wc_ast.Term,
    *,
    fuzzy: bool = True,
    negated: frozenset[int] = frozenset(),
) -> wc_ast.Node:
    return _widen_leaf(leaf, fuzzy=fuzzy, negated=negated)


class TestWhichAlternativesAreAdded:
    def test_a_latin_leaf_gains_only_the_fuzzy_side(self) -> None:
        """
        GIVEN:
            - A latin term, which has no CJK in it
        WHEN:
            - The hook runs with fuzzy on
        THEN:
            - The Or holds the leaf and the boosted fuzzy alternative,
              and nothing else
        """
        leaf = _content("invoice")

        assert _widen(leaf) == wc_ast.Or(
            children=(
                leaf,
                wc_ast.Boosted(child=_fuzzy_alternative(leaf), boost=0.1),
            ),
        )

    def test_a_cjk_leaf_gains_only_the_cjk_side_when_fuzzy_is_off(self) -> None:
        """
        GIVEN:
            - A CJK term
        WHEN:
            - The hook runs with fuzzy off
        THEN:
            - Only the bigram alternative is added, which is exactly what
              the CJK work shipped
        """
        leaf = _content("東京")

        assert _widen(leaf, fuzzy=False) == wc_ast.Or(
            children=(leaf, _cjk_alternative(leaf)),
        )

    def test_a_cjk_leaf_gains_only_its_bigram_side(self) -> None:
        """
        GIVEN:
            - A CJK term
        WHEN:
            - The hook runs with fuzzy on
        THEN:
            - The Or holds the leaf and the bigram alternative, and no
              fuzzy one. A prefix Fuzzy over a whole unspaced run matches
              any run within one edit of its start, and _cjk_alternative
              already supplies the in-run recall
        """
        leaf = _content("東京")

        assert _fuzzy_alternative(leaf) is None
        assert _widen(leaf) == wc_ast.Or(children=(leaf, _cjk_alternative(leaf)))

    def test_a_negated_leaf_keeps_cjk_and_loses_fuzzy(self) -> None:
        """
        GIVEN:
            - A CJK term whose id is in the negated set
        WHEN:
            - The hook runs with fuzzy on
        THEN:
            - The bigram alternative survives and the fuzzy one does not.
              NOT X should exclude what X matches, which needs the bigram
              side, but prefix fuzzy matching would exclude far more
        """
        leaf = _content("東京")

        assert _widen(leaf, negated=frozenset({id(leaf)})) == wc_ast.Or(
            children=(leaf, _cjk_alternative(leaf)),
        )

    def test_a_negated_latin_leaf_is_returned_unchanged(self) -> None:
        """
        GIVEN:
            - A latin term whose id is in the negated set
        WHEN:
            - The hook runs with fuzzy on
        THEN:
            - The leaf itself comes back. It qualifies for no alternative
              at all, so there is no Or to build
        """
        leaf = _content("tax")

        assert _widen(leaf, negated=frozenset({id(leaf)})) is leaf

    def test_a_leaf_outside_the_default_fields_is_returned_unchanged(self) -> None:
        """
        GIVEN:
            - A term on a JSON subpath field, which is not one of the five
              default search fields
        WHEN:
            - The hook runs with fuzzy on
        THEN:
            - The leaf comes back untouched. Widening is scoped to the
              default search fields, as it was for CJK
        """
        leaf = wc_ast.Term(field=_NOTES, text="invoice")

        assert _widen(leaf) is leaf
