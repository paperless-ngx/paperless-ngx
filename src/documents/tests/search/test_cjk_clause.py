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


class TestCjkClauseFollowsTheParsedQuery:
    def test_negated_cjk_term_is_excluded(self, backend: TantivyBackend) -> None:
        """'invoice NOT 漢字' must not return the document containing 漢字."""
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
        """'title:東京' must not match a document whose 東京 is in the content.

        The CJK clause honours the field. The fuzzy clause, when enabled,
        does not: it contributes every free-text term UNFIELDED by design
        (see _try_parse_fuzzy_query), so it brings the content-only
        document back on its own 0.1-boosted terms. That is the documented
        trade-off, pinned here so it stays deliberate.
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
        """A CJK term restricted to a field outside the default search fields
        has nothing to contribute to the bigram clause: 'notes:東京' must not
        fall back to matching 東京 in the content."""
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
        """The clause's reason for existing: an unfielded CJK run matches
        wherever it is indexed, and does so alongside a latin term."""
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
