"""The CJK bigram clause blended into QUERY-mode searches.

The clause exists so CJK runs are matchable at all (the default analyzers
keep a whitespace-free CJK run as one indivisible token), but it must not
widen the query beyond what the user asked for: a CJK term the query
excludes, or restricts to one field, must not come back through it.
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


class TestCjkParseFailureDegradesGracefully:
    def test_a_cjk_run_tantivy_cannot_parse_drops_the_clause_only(self) -> None:
        """
        GIVEN:
            - A CJK run and an index-like object whose parse_query is
              forced to raise
        WHEN:
            - _parse_cjk_text is called
        THEN:
            - It returns None instead of propagating, so a CJK run tantivy
              cannot parse only drops the bigram clause rather than
              failing the whole query. Broad on purpose (bare except
              Exception), unlike the fuzzy blend's narrower ValueError
              guard: a CJK run is not filtered to a guaranteed-safe token
              set the way the fuzzy blend's word string is, so the exact
              failure mode tantivy could raise here is not pinned down
        """
        from documents.search._query import _parse_cjk_text

        class _RaisingIndex:
            def parse_query(self, *args: object, **kwargs: object) -> object:
                raise RuntimeError("synthetic parse failure")

        assert _parse_cjk_text(_RaisingIndex(), "東京", ["bigram_content"]) is None

    def test_no_cjk_text_at_all_returns_none_without_parsing(self) -> None:
        """
        GIVEN:
            - A raw query string with no CJK characters at all
        WHEN:
            - _build_cjk_query (the simple TEXT/TITLE-mode builder) is
              called directly
        THEN:
            - It returns None without ever attempting to parse anything.
              The only real caller already guards this with _has_cjk(),
              so this is defensive: it keeps the function safe to call on
              its own, not a path a real search currently reaches
        """
        from documents.search._query import _build_cjk_query

        assert _build_cjk_query(None, "invoice total due", ["bigram_content"]) is None


class TestCjkClauseFollowsTheParsedQuery:
    def test_negated_cjk_term_is_excluded(self, backend: TantivyBackend) -> None:
        """
        GIVEN:
            - Two documents both matching "invoice", one whose content
              also contains 漢字
        WHEN:
            - "invoice NOT 漢字" is searched
        THEN:
            - Only the document without 漢字 matches; 'invoice NOT 漢字'
              must not return the document containing 漢字
        """
        with_cjk = _index(
            backend,
            title="Invoice A",
            content="invoice total 漢字",
            checksum="cjk-neg-1",
        )
        without_cjk = _index(
            backend,
            title="Invoice B",
            content="invoice total only",
            checksum="cjk-neg-2",
        )

        assert _matched_ids(backend, "invoice") == {with_cjk.pk, without_cjk.pk}
        assert _matched_ids(backend, "invoice NOT 漢字") == {without_cjk.pk}

    @pytest.mark.parametrize(
        ("threshold", "expected"),
        [
            pytest.param(None, {"titled"}, id="fuzzy_off"),
            pytest.param(0.0, {"titled", "content_only"}, id="fuzzy_on"),
        ],
    )
    def test_fielded_cjk_term_searches_only_that_field(
        self,
        backend: TantivyBackend,
        settings: SettingsWrapper,
        threshold: float | None,
        expected: set[str],
    ) -> None:
        """
        GIVEN:
            - One document with 東京 in its title, another with 東京 only
              in its content, and ADVANCED_FUZZY_SEARCH_THRESHOLD either
              off or on
        WHEN:
            - "title:東京" is searched
        THEN:
            - With fuzzy off, only the titled document matches: the CJK
              clause honours the field, so 'title:東京' must not match a
              document whose 東京 is only in the content. With fuzzy on,
              the content-only document is also readmitted, because the
              fuzzy clause contributes every free-text term UNFIELDED by
              design (see _try_parse_fuzzy_query) on its own
              0.1-boosted terms -- a documented trade-off, pinned here so
              it stays deliberate
        """
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = threshold
        content_only = _index(
            backend,
            title="Tokyo report",
            content="東京都の人口は約1400万人です",
            checksum="cjk-field-1",
        )
        titled = _index(
            backend,
            title="東京都の報告書",
            content="an english summary",
            checksum="cjk-field-2",
        )
        pks = {"titled": titled.pk, "content_only": content_only.pk}

        assert _matched_ids(backend, "東京") == set(pks.values())
        assert _matched_ids(backend, "title:東京") == {pks[label] for label in expected}

    def test_cjk_on_a_non_default_field_builds_no_clause(
        self,
        backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A document with 東京 in its content
        WHEN:
            - "notes:東京" is searched (a field outside the default
              search fields)
        THEN:
            - Nothing matches; a CJK term restricted to a field outside
              the default search fields has nothing to contribute to the
              bigram clause, so it must not fall back to matching 東京 in
              the content
        """
        _index(
            backend,
            title="Tokyo report",
            content="東京都の人口は約1400万人です",
            checksum="cjk-notes-1",
        )

        assert _matched_ids(backend, "notes:東京") == set()

    def test_bare_cjk_term_still_matches_every_default_field(
        self,
        backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - One document with 重要 in its content, another with 重要 in
              its title
        WHEN:
            - "重要" and "重要 OR report" are each searched unfielded
        THEN:
            - Both documents match either way; the clause's reason for
              existing is that an unfielded CJK run matches wherever it
              is indexed, and does so alongside a latin term
        """
        in_content = _index(
            backend,
            title="report",
            content="本文に重要な情報",
            checksum="cjk-bare-1",
        )
        in_title = _index(
            backend,
            title="重要な報告書",
            content="english only",
            checksum="cjk-bare-2",
        )

        assert _matched_ids(backend, "重要") == {in_content.pk, in_title.pk}
        assert _matched_ids(backend, "重要 OR report") == {
            in_content.pk,
            in_title.pk,
        }
