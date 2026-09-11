"""_ConjunctiveNegations, the AST visitor that collects the subtrees a
query excludes from every document it matches, and _any_of, the clause-list
collapsing helper it feeds into.

Result-level proof that a negation reached through NOT/AND survives the
fuzzy/CJK blend lives in test_query_negation.py. These are direct unit
tests of the visitor's dispatch for the rarer grammar shapes
(AndNot/Boosted/AndMaybe/Require) that file's real-corpus queries don't
happen to exercise, plus the empty-clause-list case of _any_of.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import whoosh_compat.ast as wc_ast

from documents.models import Document
from documents.search._query import _any_of
from documents.search._query import _ConjunctiveNegations

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _term(text: str) -> wc_ast.Term:
    return wc_ast.Term(field=None, text=text)


class TestConjunctiveNegationsVisitor:
    def test_visit_andnot_hoists_the_negative_branch(self) -> None:
        """
        GIVEN:
            - An AndNot(positive=a, negative=b) node
        WHEN:
            - _ConjunctiveNegations visits it
        THEN:
            - The negative branch is collected as an exclusion, since
              AndNot requires positive and excludes negative
        """
        negative = _term("b")
        node = wc_ast.AndNot(positive=_term("a"), negative=negative)
        assert _ConjunctiveNegations().visit(node) == (negative,)

    def test_visit_andnot_also_collects_negations_already_in_the_positive_branch(
        self,
    ) -> None:
        """
        GIVEN:
            - An AndNot node whose positive branch already contains a NOT
        WHEN:
            - _ConjunctiveNegations visits it
        THEN:
            - Both the positive branch's own negation and the AndNot's
              negative branch are collected
        """
        excluded_in_positive = _term("excluded")
        negative = _term("negative")
        node = wc_ast.AndNot(
            positive=wc_ast.Not(child=excluded_in_positive),
            negative=negative,
        )
        assert _ConjunctiveNegations().visit(node) == (excluded_in_positive, negative)

    def test_visit_boosted_passes_through_to_the_child(self) -> None:
        """
        GIVEN:
            - A Boosted node (e.g. "(invoice NOT secret)^2") wrapping a
              NOT
        WHEN:
            - _ConjunctiveNegations visits it
        THEN:
            - The negation inside the boosted child is still collected: a
              boost must not shield an exclusion from being hoisted
        """
        excluded = _term("secret")
        node = wc_ast.Boosted(child=wc_ast.Not(child=excluded), boost=2.0)
        assert _ConjunctiveNegations().visit(node) == (excluded,)

    def test_visit_andmaybe_only_descends_into_required(self) -> None:
        """
        GIVEN:
            - An AndMaybe(required=a, optional=b) node where both required
              and optional contain their own NOT
        WHEN:
            - _ConjunctiveNegations visits it
        THEN:
            - Only the negation in the required branch is collected. The
              optional branch is not a conjunctive constraint on the whole
              query (documents that fail it still match), so hoisting a
              negation from it would exclude documents the query does not
              actually exclude
        """
        excluded_in_required = _term("excluded_in_required")
        excluded_in_optional = _term("excluded_in_optional")
        node = wc_ast.AndMaybe(
            required=wc_ast.Not(child=excluded_in_required),
            optional=wc_ast.Not(child=excluded_in_optional),
        )
        assert _ConjunctiveNegations().visit(node) == (excluded_in_required,)

    def test_visit_require_descends_into_both_branches(self) -> None:
        """
        GIVEN:
            - A Require(scored=a, filter_only=b) node where both scored
              and filter_only contain their own NOT
        WHEN:
            - _ConjunctiveNegations visits it
        THEN:
            - Both negations are collected: Require constrains the whole
              query with both branches, one merely scored and the other
              filter-only, so both are conjunctive
        """
        excluded_in_scored = _term("excluded_in_scored")
        excluded_in_filter = _term("excluded_in_filter")
        node = wc_ast.Require(
            scored=wc_ast.Not(child=excluded_in_scored),
            filter_only=wc_ast.Not(child=excluded_in_filter),
        )
        assert _ConjunctiveNegations().visit(node) == (
            excluded_in_scored,
            excluded_in_filter,
        )


class TestAnyOfEmptyClauseList:
    def test_no_clauses_returns_a_query_that_matches_nothing(
        self,
        backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - No clauses at all
        WHEN:
            - _any_of is called with an empty list
        THEN:
            - It returns tantivy's empty_query() rather than raising or
              wrapping zero clauses in a boolean_query, and running it
              against a real index matches no documents
        """
        doc = Document.objects.create(title="x", content="x", checksum="any-of-empty")
        backend.add_or_update(doc)

        query = _any_of([])
        results = backend._index.searcher().search(query, limit=10)
        assert len(results.hits) == 0
