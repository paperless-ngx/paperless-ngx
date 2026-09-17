"""The emit-only FieldRegistry a CJK-widened query tree is emitted against.

It is the parse registry plus the internal bigram fields. These tests pin
what the bigram half has to get right on its own: combining a run's bigrams
with AND wherever the leaf sits, producing exactly the terms the index
holds, and naming only fields the index schema actually has.
"""

from __future__ import annotations

import pytest
import tantivy
import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

from documents.search._query import _CJK_BIGRAM_FIELDS
from documents.search._query import _get_emit_field_registry
from documents.search._schema import field_descriptors
from documents.search._tokenizer import register_tokenizers

pytestmark = pytest.mark.search

_BIGRAM_CONTENT = wc.FieldRef("bigram_content")
_CONTENT = wc.FieldRef("content")


class TestEmitFieldRegistry:
    def test_a_multi_bigram_run_requires_every_bigram_even_under_an_or(
        self,
    ) -> None:
        """
        GIVEN:
            - A three-character CJK run on bigram_content, sitting inside
              an Or (where the CJK widener always places it)
        WHEN:
            - The tree is analyzed against the emit registry
        THEN:
            - The run's two bigrams are combined with And, not Or. Left
              to Multitoken.DEFAULT they would inherit the enclosing Or,
              so "東京都" would match a document containing only 京都
        """
        tree = wc_ast.Or(
            children=(
                wc_ast.Term(field=_BIGRAM_CONTENT, text="東京都"),
                wc_ast.Term(field=_CONTENT, text="report"),
            ),
        )

        analyzed = wc_ast.analyze(tree, _get_emit_field_registry(None))

        assert analyzed == wc_ast.Or(
            children=(
                wc_ast.And(
                    children=(
                        wc_ast.Term(field=_BIGRAM_CONTENT, text="東京"),
                        wc_ast.Term(field=_BIGRAM_CONTENT, text="京都"),
                    ),
                ),
                wc_ast.Term(field=_CONTENT, text="report"),
            ),
        )

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("東京都の公共文書", id="japanese"),
            pytest.param("北京市人民政府", id="chinese"),
            pytest.param("서울특별시", id="korean"),
        ],
    )
    def test_every_query_bigram_is_a_term_the_index_holds(self, text: str) -> None:
        """
        GIVEN:
            - A document whose bigram_content was indexed by the tokenizer
              register_tokenizers() installs
        WHEN:
            - The emit registry's bigram analyzer tokenizes the same text
        THEN:
            - Every token it produces is found as an indexed term. The
              query side and the index side each build their own bigram
              analyzer, so this pins the two staying equivalent
        """
        sb = tantivy.SchemaBuilder()
        sb.add_text_field(
            "bigram_content",
            stored=False,
            tokenizer_name="bigram_analyzer",
        )
        index = tantivy.Index(sb.build(), path=None)
        register_tokenizers(index, None)
        writer = index.writer()
        doc = tantivy.Document()
        doc.add_text("bigram_content", text)
        writer.add_document(doc)
        writer.commit()
        index.reload()

        resolved = _get_emit_field_registry(None).resolve(_BIGRAM_CONTENT)
        assert resolved is not None
        tokens = resolved.spec.analyzer(text)

        assert tokens
        searcher = index.searcher()
        for token in tokens:
            query = tantivy.Query.term_query(index.schema, "bigram_content", token)
            assert searcher.search(query, limit=1).count == 1, token

    def test_every_bigram_field_is_in_the_index_schema(self) -> None:
        """
        GIVEN:
            - The bigram fields the emit registry declares, and the index
              schema's field descriptors
        WHEN:
            - Each bigram field name is looked up in the schema
        THEN:
            - Every one is present. Every index is built from these
              descriptors, or rebuilt when its stored fingerprint of them
              differs, so this is what guarantees each widened bigram leaf
              names a field the index has
        """
        schema_names = {descriptor.name for descriptor in field_descriptors()}
        assert set(_CJK_BIGRAM_FIELDS.values()) <= schema_names
