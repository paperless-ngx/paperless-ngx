"""The pattern normalizer's stem-alternates contract, and its consistency
with the index-side analyzer.

Query patterns are normalized but were not stemmed, while index terms are
stemmed, so the natural spelling of a prefix search matched nothing:
``invoice*`` found no document although ``invoic*`` did. v2's index was
UNSTEMMED (whoosh ``TEXT()`` defaults to ``StandardAnalyzer``), so this
regressed against both baselines.

These are pure unit tests against ``_make_pattern_normalizer`` and
``stem_pattern_text`` directly, no query routing involved. The end-to-end
proof that a real wildcard query actually reaches a stemmed index term
lives in ``test_pattern_stemming.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._registry import _make_pattern_normalizer
from documents.search._tokenizer import ascii_fold
from documents.search._tokenizer import paperless_text_analyzer
from documents.search._tokenizer import stem_pattern_text

if TYPE_CHECKING:
    from whoosh_compat import PatternNormalizer


class TestStemsMatchTheIndexAnalyzer:
    """stem_pattern_text rebuilds paperless_text_analyzer's stemming tail rather
    than sharing it, so a filter added to the index analyzer alone would silently
    stop patterns from reaching the terms it produces.
    """

    @pytest.mark.parametrize(
        "language",
        ["en", "de", "fr", "es", "sv", None, "klingon"],
    )
    @pytest.mark.parametrize(
        "word",
        ["Copies", "copyright", "Companies", "Invoices", "laufen", "casas", "Straße"],
    )
    def test_stem_equals_the_index_term(self, word: str, language: str | None) -> None:
        """
        GIVEN:
            - A word, across several representative index languages
              ("en", "de", "fr", "es", "sv"), no language, and an
              unsupported language ("klingon")
        WHEN:
            - `stem_pattern_text` (the pattern-side stemmer) processes the
              folded word, and `paperless_text_analyzer` (the index-side
              analyzer) independently processes the same word
        THEN:
            - The two produce the identical term. `stem_pattern_text`
              rebuilds `paperless_text_analyzer`'s stemming tail rather
              than sharing it, so a filter added to the index analyzer
              alone would silently stop patterns from reaching the terms
              it produces; this pins the two staying in sync
        """
        indexed = paperless_text_analyzer(language).analyze(word)[0]
        assert stem_pattern_text(ascii_fold(word.lower()), language) == indexed


def _forms(normalize: PatternNormalizer, text: str) -> tuple[str, ...]:
    """The distinct forms a term may match, in order, the way the emitter reads
    the normalizer's answer (see whoosh_compat.PatternNormalizer)."""
    result = normalize(text)
    if isinstance(result, str):
        return (result,)
    return tuple(dict.fromkeys(result))


class TestPatternNormalizer:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Invoice", ("invoice", "invoic")),
            ("companies", ("companies", "compani")),
            # y -> i is a substitution, so both forms are needed: the index
            # holds "librari" for "library" and "library" for "librarian".
            ("library", ("library", "librari")),
            # A run the stemmer leaves alone collapses back to one form, so it
            # costs exactly the one regex branch it did before.
            ("invoic", ("invoic",)),
            ("Universit", ("universit",)),
            ("Café", ("cafe",)),
        ],
    )
    def test_offers_the_typed_run_and_its_stem(
        self,
        text: str,
        expected: tuple[str, ...],
    ) -> None:
        """
        GIVEN:
            - The "en" pattern normalizer
        WHEN:
            - It processes a literal run (e.g. "Invoice", "library",
              "Café")
        THEN:
            - It returns the folded run and, where it differs, the
              stemmed form, as distinct alternatives; a run the stemmer
              leaves alone (e.g. "invoic") collapses back to the single
              folded form. "library" needs both forms since y -> i is a
              substitution: the index holds "librari" for "library" and
              "library" for "librarian"
        """
        assert _forms(_make_pattern_normalizer("en"), text) == expected

    def test_run_that_yields_no_token_falls_back_to_the_typed_run(self) -> None:
        """
        GIVEN:
            - The "en" pattern normalizer
        WHEN:
            - It processes a run past the analyzer's remove_long limit
        THEN:
            - The run analyzes to zero tokens, so there is no stem to
              offer, and only the folded run remains
        """
        over_long = "invoices" * 20
        assert _forms(_make_pattern_normalizer("en"), over_long) == (over_long,)

    @pytest.mark.parametrize("language", [None, "klingon"])
    def test_unstemmed_language_folds_only(self, language: str | None) -> None:
        """
        GIVEN:
            - A pattern normalizer with no language configured, or one
              this build has no stemmer for ("klingon")
        WHEN:
            - It processes "Invoices"
        THEN:
            - Only the folded form ("invoices") is offered, since with no
              stemmer configured the index holds surface forms and the
              pattern must keep them too
        """
        assert _forms(_make_pattern_normalizer(language), "Invoices") == ("invoices",)

    @pytest.mark.parametrize("char", ["a", "Z", "é"])
    def test_a_single_character_collapses_to_one_folded_form(self, char: str) -> None:
        """
        GIVEN:
            - The "en" pattern normalizer
        WHEN:
            - It processes a single character
        THEN:
            - Exactly one, one-character form is returned. A bracket
              class body is normalized one character at a time and the
              answer is used only when it is a single one-character
              form, so a stemmer that changed a lone character would
              silently disable folding inside classes
        """
        forms = _forms(_make_pattern_normalizer("en"), char)
        assert len(forms) == 1
        assert len(forms[0]) == 1
