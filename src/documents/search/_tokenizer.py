from __future__ import annotations

import logging

import tantivy

logger = logging.getLogger("paperless.search")

# Mapping of ISO 639-1 codes (and common aliases) -> Tantivy Snowball name
_LANGUAGE_MAP: dict[str, str] = {
    "ar": "Arabic",
    "arabic": "Arabic",
    "da": "Danish",
    "danish": "Danish",
    "nl": "Dutch",
    "dutch": "Dutch",
    "en": "English",
    "english": "English",
    "fi": "Finnish",
    "finnish": "Finnish",
    "fr": "French",
    "french": "French",
    "de": "German",
    "german": "German",
    "el": "Greek",
    "greek": "Greek",
    "hu": "Hungarian",
    "hungarian": "Hungarian",
    "it": "Italian",
    "italian": "Italian",
    "no": "Norwegian",
    "norwegian": "Norwegian",
    "pt": "Portuguese",
    "portuguese": "Portuguese",
    "ro": "Romanian",
    "romanian": "Romanian",
    "ru": "Russian",
    "russian": "Russian",
    "es": "Spanish",
    "spanish": "Spanish",
    "sv": "Swedish",
    "swedish": "Swedish",
    "ta": "Tamil",
    "tamil": "Tamil",
    "tr": "Turkish",
    "turkish": "Turkish",
}

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(_LANGUAGE_MAP)


def register_tokenizers(index: tantivy.Index, language: str | None) -> None:
    """
    Register all custom tokenizers required by the paperless schema.

    Must be called on every Index instance since Tantivy requires tokenizer
    re-registration after each index open/creation. Registers tokenizers for
    full-text search, sorting, CJK language support, and fast-field indexing.

    Args:
        index: Tantivy index instance to register tokenizers on
        language: ISO 639-1 language code for stemming (None to disable)

    Note:
        simple_analyzer is registered as both a text and fast-field tokenizer
        since sort shadow fields (title_sort, correspondent_sort, type_sort)
        use fast=True and Tantivy requires fast-field tokenizers to exist
        even for documents that omit those fields.
    """
    index.register_tokenizer("paperless_text", _paperless_text(language))
    index.register_tokenizer("simple_analyzer", _simple_analyzer())
    index.register_tokenizer("bigram_analyzer", _bigram_analyzer())
    index.register_tokenizer("simple_search_analyzer", _simple_search_analyzer())
    # Fast-field tokenizer required for fast=True text fields in the schema
    index.register_fast_field_tokenizer("simple_analyzer", _simple_analyzer())


def _paperless_text(language: str | None) -> tantivy.TextAnalyzer:
    """Main full-text tokenizer for content, title, etc: simple -> remove_long(65) -> lowercase -> ascii_fold [-> stemmer]"""
    builder = (
        tantivy.TextAnalyzerBuilder(tantivy.Tokenizer.simple())
        .filter(tantivy.Filter.remove_long(65))
        .filter(tantivy.Filter.lowercase())
        .filter(tantivy.Filter.ascii_fold())
    )
    if language:
        tantivy_lang = _LANGUAGE_MAP.get(language.lower())
        if tantivy_lang:
            builder = builder.filter(tantivy.Filter.stemmer(tantivy_lang))
        else:
            logger.warning(
                "Unsupported search language '%s' - stemming disabled. Supported: %s",
                language,
                ", ".join(sorted(SUPPORTED_LANGUAGES)),
            )
    return builder.build()


def _simple_analyzer() -> tantivy.TextAnalyzer:
    """Tokenizer for shadow sort fields (title_sort, correspondent_sort, type_sort): simple -> lowercase -> ascii_fold."""
    return (
        tantivy.TextAnalyzerBuilder(tantivy.Tokenizer.simple())
        .filter(tantivy.Filter.lowercase())
        .filter(tantivy.Filter.ascii_fold())
        .build()
    )


def _bigram_analyzer() -> tantivy.TextAnalyzer:
    """Enables substring search in CJK text: ngram(2,2) -> lowercase. CJK / no-whitespace language support."""
    return (
        tantivy.TextAnalyzerBuilder(
            tantivy.Tokenizer.ngram(min_gram=2, max_gram=2, prefix_only=False),
        )
        .filter(tantivy.Filter.lowercase())
        .build()
    )


def _simple_search_analyzer() -> tantivy.TextAnalyzer:
    """Tokenizer for simple substring search fields: non-whitespace chunks -> remove_long(65) -> lowercase -> ascii_fold."""
    return (
        tantivy.TextAnalyzerBuilder(
            tantivy.Tokenizer.regex(r"\S+"),
        )
        .filter(tantivy.Filter.remove_long(65))
        .filter(tantivy.Filter.lowercase())
        .filter(tantivy.Filter.ascii_fold())
        .build()
    )
