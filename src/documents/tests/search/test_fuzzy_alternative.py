"""_fuzzy_alternative, the near-match side of the widening hook.

A leaf's words each become a Fuzzy leaf on the leaf's own field, so a
typo in one word of a term still finds the document while everything
around the term keeps constraining it. A Term's words are OR'd for
per-word recall; a Phrase's are AND-ed, because quoting must not widen a
search. CJK words get no fuzzy side at all.
"""

from __future__ import annotations

import pytest
import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

from documents.search._query import _fuzzy_alternative

pytestmark = pytest.mark.search

_CONTENT = wc.FieldRef("content")
_TITLE = wc.FieldRef("title")

# 130 characters, past the analyzer's 129-byte remove_long limit (128 is
# kept, 129 is dropped), so the index never holds it and neither side
# should search for it.
_TOO_LONG = "x" * 130


def _content(text: str) -> wc_ast.Term:
    return wc_ast.Term(field=_CONTENT, text=text)


def _fuzzy(field: wc.FieldRef, text: str) -> wc_ast.Fuzzy:
    return wc_ast.Fuzzy(field=field, text=text, distance=1, prefix=True)


class TestTheAlternative:
    def test_a_single_word_becomes_one_fuzzy_leaf(self) -> None:
        """
        GIVEN:
            - A one-word term
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - It is a single Fuzzy leaf on the same field, distance 1 and
              prefix matching, which is what the old clause used
        """
        assert _fuzzy_alternative(_content("invoice")) == _fuzzy(_CONTENT, "invoice")

    def test_the_leafs_own_field_is_used(self) -> None:
        """
        GIVEN:
            - A term fielded on title
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - The Fuzzy leaf is on title, not spread across the default
              fields. This is the fielding fix: today's clause searches a
              fielded word everywhere
        """
        assert _fuzzy_alternative(wc_ast.Term(field=_TITLE, text="invoice")) == _fuzzy(
            _TITLE,
            "invoice",
        )

    def test_several_words_are_ored(self) -> None:
        """
        GIVEN:
            - A hyphenated term the analyzer splits into two words
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - The words are OR'd. AND would be stricter than the exact
              side, which is OR'd for an unfielded term, and would lose
              today's per-word recall inside a term
        """
        assert _fuzzy_alternative(_content("COVID-19")) == wc_ast.Or(
            children=(_fuzzy(_CONTENT, "covid"), _fuzzy(_CONTENT, "19")),
        )

    def test_words_are_split_where_the_index_splits_them(self) -> None:
        """
        GIVEN:
            - A term the analyzer lowercases and folds
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - The Fuzzy text is the analyzer's output, not the raw text,
              so it is in the same shape as the index terms
        """
        assert _fuzzy_alternative(_content("Éclair")) == _fuzzy(_CONTENT, "eclair")

    def test_the_splitter_does_not_stem(self) -> None:
        """
        GIVEN:
            - A word the stemmer would change
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - The word is unstemmed. Fuzzy text goes through the field's
              pattern_normalizer, which stems it once; stemming here too
              would search for a term the index does not hold
        """
        assert _fuzzy_alternative(_content("universities")) == _fuzzy(
            _CONTENT,
            "universities",
        )

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("x", id="one_character"),
            pytest.param("__", id="only_dropped_characters"),
            pytest.param(_TOO_LONG, id="past_remove_long"),
            pytest.param("", id="empty"),
            pytest.param("   ", id="whitespace"),
        ],
    )
    def test_text_with_no_usable_word_gets_no_alternative(self, text: str) -> None:
        """
        GIVEN:
            - Text with no word the index could hold: a single character,
              characters the tokenizer drops, a word past remove_long, or
              nothing at all
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - None, so the leaf is left alone. Returning an alternative
              here would collapse Or(leaf, fuzzy) to a required clause
              that can never match, making a query return LESS with fuzzy
              on than off
        """
        assert _fuzzy_alternative(_content(text)) is None

    def test_a_one_character_word_is_dropped_from_a_longer_term(self) -> None:
        """
        GIVEN:
            - A term mixing a one-character word with a real one
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - Only the real word survives. A one-character prefix fuzzy
              term matches every term in the field
        """
        assert _fuzzy_alternative(_content("h52.1")) == _fuzzy(_CONTENT, "h52")

    def test_the_leaf_span_is_copied(self) -> None:
        """
        GIVEN:
            - A leaf with a source span, whose words both survive the
              one-character filter so there is an Or to inspect
        WHEN:
            - The fuzzy alternative is built
        THEN:
            - Every node it builds carries that span, so an emit-time
              diagnostic still points into the query text
        """
        leaf = wc_ast.Term(field=_CONTENT, text="ab-cd", startchar=4, endchar=9)

        alternative = _fuzzy_alternative(leaf)

        assert isinstance(alternative, wc_ast.Or)
        spans = {
            (node.startchar, node.endchar)
            for node in (alternative, *alternative.children)
        }
        assert spans == {(4, 9)}


class TestPhrasesAreNotWidened:
    def test_a_multi_word_phrase_requires_every_word(self) -> None:
        """
        GIVEN:
            - A quoted two-word phrase
        WHEN:
            - Its fuzzy alternative is built
        THEN:
            - The words are And-combined, where a Term's are Or-combined
              (test_a_hyphenated_term_matches_on_one_word pins that). The
              parser's default group is And, so an Or here would let the
              quoted phrase match strictly more than the same two words
              unquoted
        """
        leaf = wc_ast.Phrase(field=_CONTENT, text="tax report")

        assert _fuzzy_alternative(leaf) == wc_ast.And(
            children=(_fuzzy(_CONTENT, "tax"), _fuzzy(_CONTENT, "report")),
        )


class TestCjkGetsNoFuzzySide:
    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("東京", id="cjk_only"),
            pytest.param("東京都の報告書", id="longer_run"),
            pytest.param("서울", id="hangul"),
        ],
    )
    def test_a_cjk_word_is_skipped(self, text: str) -> None:
        """
        GIVEN:
            - A CJK term
        WHEN:
            - Its fuzzy alternative is built
        THEN:
            - There is none. The content analyzer keeps the run as one
              token, so a prefix Fuzzy over it would match any run within
              one edit of its start, which is the "東京都 matches 京都"
              failure the bigram fields exist to avoid
        """
        assert _fuzzy_alternative(_content(text)) is None

    def test_latin_beside_cjk_still_gets_its_fuzzy_side(self) -> None:
        """
        GIVEN:
            - A term mixing a CJK run and a latin word
        WHEN:
            - Its fuzzy alternative is built
        THEN:
            - Only the latin word is fuzzed. Skipping CJK words must not
              cost the latin half its near-match
        """
        leaf = _content("東京 report")

        assert _fuzzy_alternative(leaf) == _fuzzy(_CONTENT, "report")
