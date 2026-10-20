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

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document

pytestmark = [pytest.mark.search, pytest.mark.django_db]

CONTENT = (
    "invoice total due for electricity from both companies, "
    "payments made to the university library, copies attached"
)


@pytest.fixture
def indexed_doc(index_document: Callable[..., Document]) -> Document:
    return index_document(
        title="Invoice 2020 productname",
        content=CONTENT,
        archive_serial_number=900,
    )


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
        matched_ids: Callable[[str], set[int]],
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
        assert matched_ids(query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["invoic*", "electr*", "payment*"])
    def test_already_stemmed_prefix_still_matches(
        self,
        matched_ids: Callable[[str], set[int]],
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
        assert matched_ids(query) == {indexed_doc.id}

    @pytest.mark.parametrize("query", ["univers*", "librar*"])
    def test_partial_prefix_reaches_the_stemmed_term(
        self,
        matched_ids: Callable[[str], set[int]],
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
        assert matched_ids(query) == {indexed_doc.id}

    def test_full_word_reaches_the_stem_but_a_fragment_of_it_does_not(
        self,
        matched_ids: Callable[[str], set[int]],
        indexed_doc: Document,
    ) -> None:
        """
        GIVEN:
            - The same indexed document, storing "university" as "univers"
        WHEN:
            - "universities*", "universit*" and "univers*" are each queried
        THEN:
            - "universities*" matches, since the stem of "universities" is
              that same "univers"; "universit*" matches nothing, since
              "universit" is a prefix of neither its own stem nor the
              stored term. The alternatives widen recall without turning
              a wildcard into a prefix search over the original text.
              usage.md tells a reader whose `universit*` finds nothing to
              shorten it to `univers*`, which matches
        """
        assert matched_ids("universities*") == {indexed_doc.id}
        assert matched_ids("universit*") == set()
        assert matched_ids("univers*") == {indexed_doc.id}

    def test_pattern_past_the_stem_boundary_is_documented_not_fixed(
        self,
        matched_ids: Callable[[str], set[int]],
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
        assert matched_ids("produ*name") == set()

    def test_stem_substitution_reaches_both_the_inflection_and_the_compound(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
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
        compound = index_document(
            title="Copyright notice",
            content="copyright notice for the work",
            archive_serial_number=901,
        )

        assert matched_ids("copy*") == {indexed_doc.id, compound.id}
        assert matched_ids("copyright*") == {compound.id}


class TestBracketClassStillFolds:
    def test_class_body_matches_case_insensitively(
        self,
        matched_ids: Callable[[str], set[int]],
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
        assert matched_ids("title:[IP]nvoice*") == {indexed_doc.id}
