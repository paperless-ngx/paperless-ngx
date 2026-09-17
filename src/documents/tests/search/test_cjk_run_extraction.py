"""Which characters count as part of a CJK run.

_CJK_RE decides both what is indexed into the bigram fields
(extract_cjk_text) and how a query's CJK text is cut into runs
(_widen_cjk_leaf). A character it misses splits a word in two on both
sides. For the katakana prolonged sound mark that leaves one-character
runs, which have no bigrams, so the word could not be found through the
bigram fields at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._query import extract_cjk_text

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document


pytestmark = pytest.mark.search


class TestRunExtraction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("コーヒーを飲む", "コーヒーを飲む", id="prolonged_sound_mark"),
            pytest.param("ｺｰﾋｰ", "ｺｰﾋｰ", id="halfwidth_prolonged_sound_mark"),
            pytest.param("ｺﾞﾙﾌ", "ｺﾞﾙﾌ", id="halfwidth_voiced_mark"),
            pytest.param("ﾊﾟﾝ", "ﾊﾟﾝ", id="halfwidth_semi_voiced_mark"),
            pytest.param("締め切り〆日", "締め切り〆日", id="closing_mark"),
            pytest.param("人々の生活", "人々の生活", id="iteration_mark"),
            pytest.param("東京・大阪", "東京 大阪", id="interpunct_still_splits"),
            pytest.param("東京、大阪", "東京 大阪", id="comma_still_splits"),
        ],
    )
    def test_japanese_word_marks_stay_inside_the_run(
        self,
        text: str,
        expected: str,
    ) -> None:
        """
        GIVEN:
            - Japanese text containing ー (U+30FC), its halfwidth form
              (U+FF70), the halfwidth voiced and semi-voiced marks
              (U+FF9E, U+FF9F), 〆 or 々, or a separator between two runs
        WHEN:
            - Its CJK runs are extracted for the bigram fields
        THEN:
            - The marks stay inside their word's run. Every one of them
              has Unicode script Common, so the script classes alone miss
              them. Punctuation such as ・ and 、 still separates runs
        """
        assert extract_cjk_text(text) == expected


@pytest.mark.django_db
class TestProlongedSoundMarkSearch:
    @pytest.mark.parametrize(
        ("query", "content"),
        [
            pytest.param("コーヒー", "コーヒーを飲む", id="fullwidth"),
            pytest.param("サーバー", "サーバーの設定を変更", id="fullwidth_two_marks"),
            pytest.param("ｺｰﾋｰ", "ｺｰﾋｰを飲む", id="halfwidth"),
        ],
    )
    def test_a_word_with_the_mark_is_found_inside_running_text(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        query: str,
        content: str,
    ) -> None:
        """
        GIVEN:
            - A document containing a katakana word with ー inside a
              longer unspaced run, and an unrelated latin document
        WHEN:
            - The word is searched
        THEN:
            - The document matches through the bigram fields. Without the
              mark in _CJK_RE, the word splits into one-character runs
              with no bigrams, and only a standalone content token could
              match
        """
        match = index_document(title="A", content=content)
        index_document(title="B", content="invoice only")

        assert matched_ids(query) == {match.pk}

    def test_not_excludes_a_word_with_the_mark(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - An "invoice" document containing コーヒー inside a longer
              run, and a latin-only "invoice" document
        WHEN:
            - "invoice NOT コーヒー" is searched
        THEN:
            - Only the latin document matches: the negation excludes what
              the positive search finds
        """
        index_document(
            title="A",
            content="コーヒーを飲む invoice",
        )
        latin = index_document(title="B", content="invoice only")

        assert matched_ids("invoice NOT コーヒー") == {latin.pk}

    def test_a_different_word_sharing_only_the_edges_does_not_match(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document with コード and ヒント, two separate words
        WHEN:
            - "コーヒー" is searched
        THEN:
            - Nothing matches. With ー outside _CJK_RE, both sides reduce
              to runs like コ and ヒ joined by spaces, and the space
              bigrams that produces could match unrelated words
        """
        index_document(title="A", content="コード ヒント")

        assert matched_ids("コーヒー") == set()


@pytest.mark.django_db
class TestHalfwidthVoicedMarkSearch:
    """Halfwidth katakana, as legacy systems and bank statements write it.

    Its voiced marks are separate codepoints with no precomposed form, so
    NFC leaves them where they are and the character class has to cover
    them. A word like ﾊﾟﾝ is three codepoints, and splitting it at the mark
    leaves two one-character runs with no bigrams, so it is not merely
    imprecise but unfindable.
    """

    @pytest.mark.parametrize(
        ("query", "content"),
        [
            pytest.param("ｺﾞﾙﾌ", "ｺﾞﾙﾌ場の利用料金", id="voiced_mark"),
            pytest.param("ﾊﾟﾝ", "ﾊﾟﾝと牛乳の購入", id="semi_voiced_mark"),
        ],
    )
    def test_a_word_with_the_mark_is_found_inside_running_text(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        query: str,
        content: str,
    ) -> None:
        """
        GIVEN:
            - A document holding a halfwidth katakana word inside a longer
              unspaced run, and an unrelated latin document
        WHEN:
            - The word is searched
        THEN:
            - The document matches. Without the mark in _CJK_RE the word
              splits at it, and ﾊﾟﾝ in particular loses both halves to the
              one-character rule and can never be found
        """
        match = index_document(title="A", content=content)
        index_document(title="B", content="invoice only")

        assert matched_ids(query) == {match.pk}

    def test_the_whole_word_is_searched_not_just_the_tail(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
    ) -> None:
        """
        GIVEN:
            - A document holding ｺﾞﾙﾌ, and one holding ﾙﾌﾅﾞｰ , which
              shares the ﾙﾌ pair that splitting ｺﾞﾙﾌ at its mark leaves
              behind
        WHEN:
            - "ｺﾞﾙﾌ" is searched
        THEN:
            - Only the first matches. Splitting at the mark would search
              the ﾙﾌ fragment alone, which silently degrades the query
              into a two-character substring search
        """
        golf = index_document(title="A", content="ｺﾞﾙﾌ場の利用料金")
        index_document(title="B", content="ﾙﾌﾅﾞｰの修理")

        assert matched_ids("ｺﾞﾙﾌ") == {golf.pk}
