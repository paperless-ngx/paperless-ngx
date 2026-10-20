"""Search text is held in one Unicode normal form on both sides.

A bigram is a pair of codepoints, so decomposed and composed spellings of
the same Japanese word produce different bigrams. Unless the indexed text
and the query string are normalized the same way, a document written one
way is invisible to a query written the other.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

import pytest

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.search._query import normalize_search_text

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

# がっこうの書類 ("school documents"). The が is precomposed in NFC and
# か + U+3099 in NFD, so the two spellings differ by one codepoint.
_NFC = "がっこうの書類"
_NFD = unicodedata.normalize("NFD", _NFC)
# The bare word, for fielded queries against a name or filename.
_NFC_WORD = "がっこう"
_NFD_WORD = unicodedata.normalize("NFD", _NFC_WORD)


class TestTheNormalizer:
    def test_it_composes_decomposed_kana(self) -> None:
        """
        GIVEN:
            - The same word spelled decomposed and composed
        WHEN:
            - Each is normalized
        THEN:
            - Both become the composed spelling. The inputs really do
              differ, so the fixture is not vacuous
        """
        assert _NFD != _NFC
        assert normalize_search_text(_NFD) == _NFC
        assert normalize_search_text(_NFC) == _NFC

    def test_it_leaves_halfwidth_katakana_alone(self) -> None:
        """
        GIVEN:
            - A halfwidth katakana word carrying a voiced sound mark
        WHEN:
            - It is normalized
        THEN:
            - It is unchanged. Halfwidth katakana has no precomposed
              voiced form, which is why _CJK_RE still has to list the
              marks rather than rely on this
        """
        assert normalize_search_text("ﾊﾟﾝ") == "ﾊﾟﾝ"


class TestEitherSpellingFindsEither:
    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(_NFC, id="composed_document"),
            pytest.param(_NFD, id="decomposed_document"),
        ],
    )
    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("がっこう", id="composed_query"),
            pytest.param(
                unicodedata.normalize("NFD", "がっこう"),
                id="decomposed_query",
            ),
        ],
    )
    def test_a_document_is_found_whichever_way_each_side_is_spelled(
        self,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        content: str,
        query: str,
    ) -> None:
        """
        GIVEN:
            - A document holding the word inside a longer unspaced run,
              spelled composed or decomposed, and an unrelated document
        WHEN:
            - The word is searched, spelled composed or decomposed
        THEN:
            - It matches in all four combinations. Without normalizing
              both sides, the decomposed run splits at the combining mark
              and the two spellings produce different bigrams
        """
        match = index_document(title="A", content=content)
        index_document(title="B", content="invoice only")

        assert matched_ids(query) == {match.pk}


class TestEverySearchableFieldIsNormalized:
    """The query side is normalized in _parse_query, so every searchable
    field has to be normalized on the way in as well.

    A field left out is worse than normalizing nothing: both sides used to
    be decomposed and matched each other, so normalizing only the query
    turns a working search into no results. original_filename is the one
    most likely to hold NFD in practice, since macOS stores filenames
    decomposed.
    """

    @pytest.mark.parametrize(
        "field",
        [
            pytest.param("title", id="title"),
            pytest.param("content", id="content"),
            pytest.param("original_filename", id="original_filename"),
            pytest.param("correspondent", id="correspondent"),
            pytest.param("document_type", id="document_type"),
            pytest.param("storage_path", id="storage_path"),
            pytest.param("tag", id="tag"),
            pytest.param("custom_fields.value", id="custom_field"),
        ],
    )
    def test_a_composed_query_finds_a_decomposed_value(
        self,
        backend: TantivyBackend,
        index_document: Callable[..., Document],
        matched_ids: Callable[[str], set[int]],
        field: str,
    ) -> None:
        """
        GIVEN:
            - A document carrying a decomposed Japanese word in one
              searchable field, and an unrelated document
        WHEN:
            - The composed spelling is searched, fielded to that field
        THEN:
            - The document matches. The query is normalized either way, so
              a field left unnormalized on the way in can never be found
        """
        kwargs: dict[str, object] = {"title": "A", "content": "invoice"}
        if field == "correspondent":
            kwargs["correspondent"] = Correspondent.objects.create(name=_NFD_WORD)
        elif field == "document_type":
            kwargs["document_type"] = DocumentType.objects.create(name=_NFD_WORD)
        elif field == "storage_path":
            kwargs["storage_path"] = StoragePath.objects.create(
                name=_NFD_WORD,
                path="archive/",
            )
        elif field in {"title", "content", "original_filename"}:
            kwargs[field] = _NFD_WORD

        doc = index_document(**kwargs)

        if field == "tag":
            doc.tags.add(Tag.objects.create(name=_NFD_WORD))
        elif field == "custom_fields.value":
            CustomFieldInstance.objects.create(
                document=doc,
                field=CustomField.objects.create(
                    name="Note",
                    data_type=CustomField.FieldDataType.STRING,
                ),
                value_text=_NFD_WORD,
            )
        # The relations above are attached after the factory built the
        # document, so the index needs the newer state.
        backend.add_or_update(doc)
        index_document(title="B", content="invoice only")

        assert matched_ids(f"{field}:{_NFC_WORD}") == {doc.pk}
