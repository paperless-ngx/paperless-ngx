"""Negation must survive the blended query.

parse_user_query ORs an exact clause with an optional fuzzy clause. That
clause is built from positive terms only, so unless the query's exclusions
are applied to the blend as a whole, a document the exact clause excluded
is re-admitted by it. CJK terms are widened inside the exact clause itself,
so the query's own structure constrains them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import SettingsWrapper

    from documents.models import Document


pytestmark = [pytest.mark.search, pytest.mark.django_db]


@pytest.fixture
def fuzzy_enabled(settings: SettingsWrapper) -> None:
    """Enable the fuzzy blend clause. The threshold doubles as a minimum
    score filter, so it is set to 0.0: every hit passes and the test sees
    the clause's matching behaviour, not the filter's."""
    settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.0


class TestNegationConstrainsEveryClause:
    @pytest.mark.usefixtures("fuzzy_enabled")
    def test_fuzzy_clause_does_not_readmit_an_excluded_document(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two documents both matching a positive term, one of which
              also contains a word the query excludes, with the fuzzy
              blend clause enabled
        WHEN:
            - A query combining the positive term with a NOT exclusion is
              run
        THEN:
            - Only the document without the excluded word is returned;
              the fuzzy clause (built from positive terms only) does not
              readmit the document the exact clause excluded
        """
        secret = index_document(
            title="Invoice A",
            content="invoice total secret",
        )
        public = index_document(
            title="Invoice B",
            content="invoice total public",
        )

        assert matched_ids("invoice") == {secret.pk, public.pk}
        assert matched_ids("invoice NOT secret") == {public.pk}

    def test_an_excluded_document_stays_out_of_a_cjk_match(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two documents both containing a CJK run, one of which also
              contains a word the query excludes
        WHEN:
            - A query combining the CJK term with a NOT exclusion is run
        THEN:
            - Only the document without the excluded word is returned;
              the CJK term's bigram match sits beside the NOT inside the
              same query, so the exclusion applies to it
        """
        secret = index_document(
            title="Tokyo A",
            content="東京都の秘密です secret",
        )
        public = index_document(
            title="Tokyo B",
            content="東京都の報告書です public",
        )

        assert matched_ids("東京") == {secret.pk, public.pk}
        assert matched_ids("東京 NOT secret") == {public.pk}

    @pytest.mark.usefixtures("fuzzy_enabled")
    def test_disjunctive_negation_still_admits_the_other_branch(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document matching a positive term and also containing a
              word a disjunctive NOT branch excludes, plus an unrelated
              document
        WHEN:
            - A query of the shape "term OR NOT excluded_word" is run
        THEN:
            - Both documents are returned; "invoice OR NOT secret"
              excludes nothing on its own, so a document matching the
              left branch stays in even though it contains the excluded
              word
        """
        secret_invoice = index_document(
            title="Invoice A",
            content="invoice total secret",
        )
        unrelated = index_document(
            title="Recipe",
            content="flour and water",
        )

        assert matched_ids("invoice OR NOT secret") == {
            secret_invoice.pk,
            unrelated.pk,
        }

    def test_a_negation_under_or_constrains_its_own_cjk_term(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - Two CJK documents, one of which also contains a word an OR
              branch's own NOT excludes, plus an unrelated latin document
        WHEN:
            - The exclusion is under a disjunctive OR branch, and in
              conjunctive position
        THEN:
            - Either way the excluded document is left out. The CJK
              term's bigram match is widened in place inside its own OR
              branch, so that branch's NOT applies to it; the other
              branch still admits the latin document
        """
        secret = index_document(
            title="Tokyo A",
            content="東京都の秘密です secret",
        )
        public = index_document(
            title="Tokyo B",
            content="東京都の報告書です public",
        )
        bill = index_document(
            title="Bill",
            content="bill payment received",
        )

        assert matched_ids("(東京 AND NOT secret) OR bill") == {
            bill.pk,
            public.pk,
        }
        assert matched_ids("東京 AND NOT secret") == {public.pk}
        assert secret.pk in matched_ids("東京")
