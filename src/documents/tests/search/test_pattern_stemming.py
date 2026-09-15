"""Wildcard patterns must match a stemmed index, end to end.

Query patterns are normalized but were not stemmed, while index terms are
stemmed, so the natural spelling of a prefix search matched nothing:
``invoice*`` found no document although ``invoic*`` did. v2's index was
UNSTEMMED (whoosh ``TEXT()`` defaults to ``StandardAnalyzer``), so this
regressed against both baselines.

These are end-to-end tests against a real indexed document and a real
query, proving the pattern normalizer's stem-alternates contract actually
reaches a stemmed index term. The pure unit tests against the normalizer
function itself live in ``test_pattern_normalizer.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Document

if TYPE_CHECKING:
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
        """
        GIVEN:
            - A document indexed with content containing "invoice",
              "electricity", "companies", "payments", "library" and title
              "Invoice 2020 productname"
        WHEN:
            - A prefix wildcard on the full, unstemmed word is queried
              (e.g. "invoice*", "title:Invoice*")
        THEN:
            - The document matches, since the pattern normalizer offers
              the word's stem as an alternative alongside the typed run,
              reaching the stemmed index term
        """
        assert _matched_ids(backend, query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["invoic*", "electr*", "payment*"])
    def test_already_stemmed_prefix_still_matches(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
        query: str,
    ) -> None:
        """
        GIVEN:
            - The same indexed document
        WHEN:
            - A prefix wildcard is typed already in its stemmed spelling
              (e.g. "invoic*")
        THEN:
            - The document still matches, since the typed-run alternative
              is itself a prefix of the stored stemmed term
        """
        assert _matched_ids(backend, query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["univers*", "librar*"])
    def test_partial_prefix_reaches_the_stemmed_term(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
        query: str,
    ) -> None:
        """
        GIVEN:
            - The same indexed document
        WHEN:
            - A prefix shorter than a whole word is queried ("univers*",
              "librar*")
        THEN:
            - It still matches, and neither case needs the two-alternative
              path to do it: measured under "en", the stemmer leaves
              "librar" alone, so it has one form, and that form is a
              prefix of the "librari" the index holds for "library";
              "univers" stems to the *shorter* "univ", and the run as
              typed and its stem are both prefixes of the "univers" the
              index holds for "university". The case where the two forms
              genuinely diverge, and only one of them matches, is
              test_stem_substitution_reaches_both_the_inflection_and_the_compound
        """
        assert _matched_ids(backend, query) == {indexed_doc.id}

    def test_full_word_reaches_the_stem_but_a_fragment_of_it_does_not(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """
        GIVEN:
            - The same indexed document, storing "university" as "univers"
        WHEN:
            - "universities*" and "universit*" are each queried
        THEN:
            - "universities*" matches, since the stem of "universities" is
              that same "univers"; "universit*" matches nothing, since
              "universit" is a prefix of neither its own stem nor the
              stored term. The alternatives widen recall without turning
              a wildcard into a prefix search over the original text, and
              usage.md names this exact pair so a reader told that
              `universit*` fails is also told which spelling works
        """
        assert _matched_ids(backend, "universities*") == {indexed_doc.id}
        assert _matched_ids(backend, "universit*") == set()

    def test_pattern_past_the_stem_boundary_is_documented_not_fixed(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """
        GIVEN:
            - The same indexed document, with "productname" indexed as
              "productnam"
        WHEN:
            - "produ*name" (a pattern straddling the stem boundary) is
              queried
        THEN:
            - It matches nothing; produ*name cannot match a stemmed
              index, and usage.md must not advertise it. Pinned so the
              limitation is deliberate, not accidental
        """
        assert _matched_ids(backend, "produ*name") == set()

    def test_stem_substitution_reaches_both_the_inflection_and_the_compound(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """
        GIVEN:
            - The indexed document (containing "copies") plus a second
              document titled "Copyright notice" with content "copyright
              notice for the work"
        WHEN:
            - "copy*" and "copyright*" are each queried
        THEN:
            - "copy*" matches both documents, and "copyright*" matches
              only the compound one. English stemming substitutes as well
              as truncates: "copy" and "copies" both index as "copi",
              while "copyright" keeps its literal "y". Neither form is a
              prefix of the other, so no single normalized string reaches
              both; the run is therefore emitted as a disjunction of the
              folded and stemmed forms, and "copy*" reaches the base
              word, its inflections and the compound alike
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


class TestBracketClassStillFolds:
    def test_class_body_matches_case_insensitively(
        self,
        backend: TantivyBackend,
        indexed_doc: Document,
    ) -> None:
        """
        GIVEN:
            - The indexed document, titled "Invoice 2020 productname"
        WHEN:
            - A bracket-class pattern mixing case is queried
              ("title:[IP]nvoice*")
        THEN:
            - It matches: the class body is folded per character, which
              the alternatives contract preserves only because a lone
              character stems to itself
        """
        assert _matched_ids(backend, "title:[IP]nvoice*") == {indexed_doc.id}
