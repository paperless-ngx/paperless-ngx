"""Negation must survive the blended query.

parse_user_query ORs an exact clause with optional fuzzy and CJK clauses.
Each of those is built from positive terms only, so unless the query's
exclusions are applied to the blend as a whole, a document the exact
clause excluded is re-admitted by whichever other clause is enabled.
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
        backend: TantivyBackend,
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
        secret = _index(
            backend,
            title="Invoice A",
            content="invoice total secret",
            checksum="neg-fuzzy-1",
        )
        public = _index(
            backend,
            title="Invoice B",
            content="invoice total public",
            checksum="neg-fuzzy-2",
        )

        assert _matched_ids(backend, "invoice") == {secret.pk, public.pk}
        assert _matched_ids(backend, "invoice NOT secret") == {public.pk}

    def test_cjk_clause_does_not_readmit_an_excluded_document(
        self,
        backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - Two documents both containing a CJK run, one of which also
              contains a word the query excludes
        WHEN:
            - A query combining the CJK term with a NOT exclusion is run
        THEN:
            - Only the document without the excluded word is returned;
              the CJK clause legitimately carries the CJK run, so
              rebuilding it from the AST cannot help here, only applying
              the exclusion above the blend keeps the excluded document
              out
        """
        secret = _index(
            backend,
            title="Tokyo A",
            content="東京都の秘密です secret",
            checksum="neg-cjk-1",
        )
        public = _index(
            backend,
            title="Tokyo B",
            content="東京都の報告書です public",
            checksum="neg-cjk-2",
        )

        assert _matched_ids(backend, "東京") == {secret.pk, public.pk}
        assert _matched_ids(backend, "東京 NOT secret") == {public.pk}

    @pytest.mark.usefixtures("fuzzy_enabled")
    def test_disjunctive_negation_still_admits_the_other_branch(
        self,
        backend: TantivyBackend,
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
        secret_invoice = _index(
            backend,
            title="Invoice A",
            content="invoice total secret",
            checksum="neg-or-1",
        )
        unrelated = _index(
            backend,
            title="Recipe",
            content="flour and water",
            checksum="neg-or-2",
        )

        assert _matched_ids(backend, "invoice OR NOT secret") == {
            secret_invoice.pk,
            unrelated.pk,
        }

    def test_a_negation_under_or_does_not_constrain_the_cjk_clause(
        self,
        backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - Two CJK documents, one of which also contains a word an OR
              branch's own NOT excludes, plus an unrelated latin document
        WHEN:
            - The exclusion is under a disjunctive OR branch, versus in
              conjunctive position
        THEN:
            - Under OR, the excluded document still matches through the
              CJK clause (an exclusion that is one branch's own condition
              cannot be restated above the blend without dropping
              documents the other branch matches, so it is left where it
              is and the CJK clause stays unconstrained by it -- this
              shows through here in a way it does not for latin text,
              since the exact clause cannot match a CJK run at all, so
              the CJK clause is the only thing matching the CJK
              documents, and the excluded one comes with it)
            - Under conjunctive "AND NOT", the same exclusion is hoisted
              and does constrain the CJK clause, pinning the deliberate
              limit of the hoist
        """
        secret = _index(
            backend,
            title="Tokyo A",
            content="東京都の秘密です secret",
            checksum="neg-or-cjk-1",
        )
        public = _index(
            backend,
            title="Tokyo B",
            content="東京都の報告書です public",
            checksum="neg-or-cjk-2",
        )
        bill = _index(
            backend,
            title="Bill",
            content="bill payment received",
            checksum="neg-or-cjk-3",
        )

        assert _matched_ids(backend, "(東京 AND NOT secret) OR bill") == {
            bill.pk,
            public.pk,
            secret.pk,
        }
        # The same exclusion in conjunctive position is hoisted, and does
        # constrain the CJK clause.
        assert _matched_ids(backend, "東京 AND NOT secret") == {public.pk}
