from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from whoosh_compat import FieldKind
from whoosh_compat import FieldRegistry

from documents.search._fields import PUBLIC_FIELDS
from documents.search._tokenizer import ascii_fold
from documents.search._tokenizer import paperless_text_analyzer
from documents.search._tokenizer import stem_pattern_text

if TYPE_CHECKING:
    from whoosh_compat import PatternNormalizer

_registry_cache: dict[str | None, FieldRegistry] = {}


def _identity_analyzer(text: str) -> list[str]:
    """Analyzer for KEYWORD fields indexed with the raw tokenizer (no splitting)."""
    return [text]


def _fold_normalizer(text: str) -> str:
    """Wildcard/regex literal-run normalizer for fields indexed without stemming."""
    return ascii_fold(text.lower())


def _make_pattern_normalizer(language: str | None) -> PatternNormalizer:
    """Build the wildcard/regex literal-run normalizer for a search language."""

    def _pattern_normalizer(text: str) -> tuple[str, ...]:
        """Normalize a literal run into the forms a term may match.

        TEXT index terms go through lowercase -> ascii_fold -> stem, so a
        pattern that skips stemming can never match one: "invoice*" would look
        for a term starting with "invoice" while the index holds "invoic". The
        run is therefore offered stemmed as well. KEYWORD fields are indexed
        raw and get _fold_normalizer instead, so their patterns stay literal.

        Both forms are returned, as alternatives, because neither is a prefix
        of the other in general: English stemming substitutes as well as
        truncates ("copy" -> "copi"), so the stem alone loses the compounds
        the typed run reaches ("copyright") while the typed run alone loses
        the inflections the stem reaches ("copies"). whoosh-compat ORs the
        alternatives per literal run and deduplicates them, so a run the
        stemmer leaves alone costs exactly the one branch it did before.

        Inside a bracket class the emitter calls this once per character and
        uses the answer only if it is a single one-character form; two forms
        there leave the character as typed. A stemmer does not change a lone
        character, so the two forms deduplicate to one and the class body is
        folded as before.
        """
        folded = ascii_fold(text.lower())
        stemmed = stem_pattern_text(folded, language)
        return (folded, stemmed)

    return _pattern_normalizer


def get_field_registry(language: str | None) -> FieldRegistry:
    """Build (or return the cached) FieldRegistry for the given search language.

    Cached keyed by language, rebuilt on the same trigger register_tokenizers()
    uses (settings.SEARCH_LANGUAGE change) — a fresh call with a new language
    builds and caches a new registry rather than mutating the old one.
    """
    if language in _registry_cache:
        return _registry_cache[language]

    text_analyzer = paperless_text_analyzer(language).analyze
    pattern_normalizer = _make_pattern_normalizer(language)

    specs = [
        dataclasses.replace(
            field,
            analyzer=_identity_analyzer
            if field.kind is FieldKind.KEYWORD
            else text_analyzer,
            pattern_normalizer=_fold_normalizer
            if field.kind is FieldKind.KEYWORD
            else pattern_normalizer,
        )
        for field in PUBLIC_FIELDS
    ]

    registry = FieldRegistry(specs)
    _registry_cache[language] = registry
    return registry
