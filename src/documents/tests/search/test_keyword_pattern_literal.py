"""Wildcard patterns on KEYWORD fields must stay literal.

``checksum`` is the only KEYWORD field: it is indexed with the raw tokenizer,
so its terms are never lowercased, folded or stemmed. Running its wildcard
patterns through the stemming normalizer rewrote hex prefixes ("ceded" ->
"cede") and returned documents whose checksum did not start with what the user
typed, which for an identity field is a wrong answer.

This covers only the registry-level normalizer, which is all that exists to
prove at this point in the stack: user queries are not yet routed through
whoosh-compat (that lands with the query-layer PR), so the same fact proven
end to end against real indexed documents lives in
``test_checksum_prefix_queries.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._registry import get_field_registry

if TYPE_CHECKING:
    from whoosh_compat import FieldRegistry
    from whoosh_compat import PatternNormalizer

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _normalizer(registry: FieldRegistry, name: str) -> PatternNormalizer:
    ref = registry.make_ref(name)
    assert ref is not None
    resolved = registry.resolve(ref)
    assert resolved is not None
    assert resolved.spec.pattern_normalizer is not None
    return resolved.spec.pattern_normalizer


class TestKeywordPatternNormalizer:
    @pytest.mark.parametrize(
        "run",
        [
            pytest.param("ceded", id="stems_to_cede"),
            pytest.param("added", id="stems_to_ad"),
            pytest.param("cafed", id="stems_to_cafe"),
        ],
    )
    def test_keyword_runs_are_folded_not_stemmed(self, run: str) -> None:
        """One form, the run as typed: a KEYWORD pattern must never be widened
        to a stem, which would return checksums that do not start with what
        the user typed."""
        normalize = _normalizer(get_field_registry("en"), "checksum")
        assert normalize(run) == run

    def test_text_runs_still_offer_their_stem(self) -> None:
        """A TEXT field offers the stem alongside the typed run, so a term
        matching either one is reachable."""
        normalize = _normalizer(get_field_registry("en"), "title")
        assert tuple(normalize("Running")) == ("running", "run")
