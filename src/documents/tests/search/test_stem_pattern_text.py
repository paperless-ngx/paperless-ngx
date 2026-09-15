from __future__ import annotations

import pytest

from documents.search._tokenizer import stem_pattern_text

pytestmark = pytest.mark.search


class TestStemPatternText:
    def test_unsupported_language_returns_text_unchanged(self) -> None:
        """
        GIVEN:
            - A language code with no Snowball stemmer mapping
        WHEN:
            - A pattern run is stemmed for that language
        THEN:
            - The run is returned unchanged, since the stemming gate that
              disables stemming for an unsupported language also disables
              the pattern-side stemmer
        """
        assert stem_pattern_text("running", "klingon") == "running"

    def test_run_past_remove_long_limit_returns_text_unchanged(self) -> None:
        """
        GIVEN:
            - A supported language and a run longer than the remove_long
              filter's limit (129 characters, matching Document.title's
              max_length)
        WHEN:
            - The over-long run is stemmed
        THEN:
            - The remove_long filter drops the token entirely, leaving no
              stem to substitute, so the run is returned unchanged
        """
        long_run = "a" * 130
        assert stem_pattern_text(long_run, "en") == long_run
