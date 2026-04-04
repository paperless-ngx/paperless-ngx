from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
import tantivy

from documents.search._tokenizer import _bigram_analyzer
from documents.search._tokenizer import _paperless_text
from documents.search._tokenizer import _simple_search_analyzer
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

pytestmark = pytest.mark.search


class TestTokenizers:
    @pytest.fixture
    def content_index(self) -> tantivy.Index:
        """Index with just a content field for ASCII folding tests."""
        sb = tantivy.SchemaBuilder()
        sb.add_text_field("content", stored=True, tokenizer_name="paperless_text")
        schema = sb.build()
        idx = tantivy.Index(schema, path=None)
        idx.register_tokenizer("paperless_text", _paperless_text(""))
        return idx

    @pytest.fixture
    def bigram_index(self) -> tantivy.Index:
        """Index with bigram field for CJK tests."""
        sb = tantivy.SchemaBuilder()
        sb.add_text_field(
            "bigram_content",
            stored=False,
            tokenizer_name="bigram_analyzer",
        )
        schema = sb.build()
        idx = tantivy.Index(schema, path=None)
        idx.register_tokenizer("bigram_analyzer", _bigram_analyzer())
        return idx

    @pytest.fixture
    def simple_search_index(self) -> tantivy.Index:
        """Index with simple-search field for Latin substring tests."""
        sb = tantivy.SchemaBuilder()
        sb.add_text_field(
            "simple_content",
            stored=False,
            tokenizer_name="simple_search_analyzer",
        )
        schema = sb.build()
        idx = tantivy.Index(schema, path=None)
        idx.register_tokenizer("simple_search_analyzer", _simple_search_analyzer())
        return idx

    def test_ascii_fold_finds_accented_content(
        self,
        content_index: tantivy.Index,
    ) -> None:
        """ASCII folding allows searching accented text with plain ASCII queries."""
        writer = content_index.writer()
        doc = tantivy.Document()
        doc.add_text("content", "café résumé")
        writer.add_document(doc)
        writer.commit()
        content_index.reload()
        q = content_index.parse_query("cafe resume", ["content"])
        assert content_index.searcher().search(q, limit=5).count == 1

    def test_bigram_finds_cjk_substring(self, bigram_index: tantivy.Index) -> None:
        """Bigram tokenizer enables substring search in CJK languages without whitespace delimiters."""
        writer = bigram_index.writer()
        doc = tantivy.Document()
        doc.add_text("bigram_content", "東京都")
        writer.add_document(doc)
        writer.commit()
        bigram_index.reload()
        q = bigram_index.parse_query("東京", ["bigram_content"])
        assert bigram_index.searcher().search(q, limit=5).count == 1

    def test_simple_search_analyzer_supports_regex_substrings(
        self,
        simple_search_index: tantivy.Index,
    ) -> None:
        """Whitespace-preserving simple search analyzer supports substring regex matching."""
        writer = simple_search_index.writer()
        doc = tantivy.Document()
        doc.add_text("simple_content", "tag:invoice password-reset")
        writer.add_document(doc)
        writer.commit()
        simple_search_index.reload()
        q = tantivy.Query.regex_query(
            simple_search_index.schema,
            "simple_content",
            ".*sswo.*",
        )
        assert simple_search_index.searcher().search(q, limit=5).count == 1

    def test_unsupported_language_logs_warning(self, caplog: LogCaptureFixture) -> None:
        """Unsupported language codes should log a warning and disable stemming gracefully."""
        sb = tantivy.SchemaBuilder()
        sb.add_text_field("content", stored=True, tokenizer_name="paperless_text")
        schema = sb.build()
        idx = tantivy.Index(schema, path=None)

        with caplog.at_level(logging.WARNING, logger="paperless.search"):
            register_tokenizers(idx, "klingon")
        assert "klingon" in caplog.text
