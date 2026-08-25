"""Wildcard patterns must match a stemmed index.

Query patterns are normalized but were not stemmed, while index terms are
stemmed, so the natural spelling of a prefix search matched nothing:
``invoice*`` found no document although ``invoic*`` did. v2's index was
UNSTEMMED (whoosh ``TEXT()`` defaults to ``StandardAnalyzer``), so this
regressed against both baselines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Document
from documents.search._registry import _make_pattern_normalizer
from documents.search._tokenizer import ascii_fold
from documents.search._tokenizer import paperless_text_analyzer
from documents.search._tokenizer import stem_pattern_text

if TYPE_CHECKING:
    from whoosh_compat import PatternNormalizer

    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

CONTENT = (
    "invoice total due for electricity from both companies, "
    "payments made to the university library, copies attached"
)


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


@pytest.fixture
def indexed_doc(backend: TantivyBackend) -> Document:
    doc = Document.objects.create(
        title="Invoice 2020 productname",
        content=CONTENT,
        checksum="pattern-stemming-1",
        archive_serial_number=900,
    )
    backend.add_or_update(doc)
    return doc


class TestPrefixStemming:
    @pytest.mark.parametrize(
        "query",
        [
            "invoice*",
            "electricity*",
            "companies*",
            "payments*",
            "library*",
            "title:Invoice*",
        ],
    )
    def test_full_word_prefix_matches_its_stem(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
        query: str,
    ) -> None:
        assert _matched_ids(backend, query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["invoic*", "electr*", "payment*"])
    def test_already_stemmed_prefix_still_matches(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
        query: str,
    ) -> None:
        assert _matched_ids(backend, query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["univers*", "librar*"])
    def test_partial_prefix_reaches_the_stemmed_term(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
        query: str,
    ) -> None:
        """A prefix shorter than a whole word still matches, and neither of
        these needs the two-alternative path to do it.

        Measured under "en": the stemmer leaves "librar" alone, so it has one
        form, and that form is a prefix of the "librari" the index holds for
        "library". "univers" stems to the *shorter* "univ", and the run as
        typed and its stem are both prefixes of the "univers" the index holds
        for "university". The case where the two forms genuinely diverge, and
        only one of them matches, is
        test_stem_substitution_reaches_both_the_inflection_and_the_compound.
        """
        assert _matched_ids(backend, query) == {indexed_doc.id}

    def test_full_word_reaches_the_stem_but_a_fragment_of_it_does_not(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """The alternatives widen recall without turning a wildcard into a
        prefix search over the original text.

        "university" is stored as "univers". The stem of "universities" is
        that same "univers", so the longer word matches; "universit" is a
        prefix of neither its own stem nor the stored term, so the *shorter*
        fragment matches nothing. usage.md names this pair, so a reader told
        that `universit*` fails is also told which spelling works.
        """
        assert _matched_ids(backend, "universities*") == {indexed_doc.id}
        assert _matched_ids(backend, "universit*") == set()

    def test_pattern_past_the_stem_boundary_is_documented_not_fixed(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """produ*name cannot match a stemmed index ("productname" is indexed as
        "productnam"); usage.md must not advertise it. Pinned so the limitation
        is deliberate, not accidental."""
        assert _matched_ids(backend, "produ*name") == set()

    def test_stem_substitution_reaches_both_the_inflection_and_the_compound(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """English stemming substitutes as well as truncates: "copy" and
        "copies" both index as "copi", while "copyright" keeps its literal "y".
        Neither form is a prefix of the other, so no single normalized string
        reaches both. The run is therefore emitted as a disjunction of the
        folded and stemmed forms, and "copy*" reaches the base word, its
        inflections and the compound alike.
        """
        compound = Document.objects.create(
            title="Copyright notice",
            content="copyright notice for the work",
            checksum="pattern-stemming-2",
            archive_serial_number=901,
        )
        backend.add_or_update(compound)

        assert _matched_ids(backend, "copy*") == {indexed_doc.id, compound.id}
        assert _matched_ids(backend, "copyright*") == {compound.id}


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
        assert _forms(_make_pattern_normalizer("en"), text) == expected

    def test_run_that_yields_no_token_falls_back_to_the_typed_run(self) -> None:
        """A run past the remove_long limit analyzes to zero tokens, so there is
        no stem to offer and only the folded run remains."""
        over_long = "invoices" * 20
        assert _forms(_make_pattern_normalizer("en"), over_long) == (over_long,)

    @pytest.mark.parametrize("language", [None, "klingon"])
    def test_unstemmed_language_folds_only(self, language: str | None) -> None:
        """With no stemmer configured, or one this build has no stemmer for, the
        index holds surface forms and the pattern must keep them too."""
        assert _forms(_make_pattern_normalizer(language), "Invoices") == ("invoices",)

    @pytest.mark.parametrize("char", ["a", "Z", "é"])
    def test_a_single_character_collapses_to_one_folded_form(self, char: str) -> None:
        """A bracket class body is normalized one character at a time and the
        answer is used only when it is a single one-character form, so a
        stemmer that changed a lone character would silently disable folding
        inside classes."""
        forms = _forms(_make_pattern_normalizer("en"), char)
        assert len(forms) == 1
        assert len(forms[0]) == 1


class TestBracketClassStillFolds:
    def test_class_body_matches_case_insensitively(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """The class body is folded per character, which the alternatives
        contract preserves only because a lone character stems to itself."""
        assert _matched_ids(backend, "title:[IP]nvoice*") == {indexed_doc.id}
