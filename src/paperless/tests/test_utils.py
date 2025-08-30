import logging

import pytest

from paperless import utils
from paperless.utils import ocr_to_dateparser_languages


@pytest.mark.parametrize(
    ("ocr_language", "expected"),
    [
        # One language
        ("eng", ["en"]),
        # Multiple languages
        ("fra+ita+lao", ["fr", "it", "lo"]),
        # Languages that don't have a two-letter equivalent
        ("fil", ["fil"]),
        # Languages with a script part supported by dateparser
        ("aze_cyrl+srp_latn", ["az-Cyrl", "sr-Latn"]),
        # Languages with a script part not supported by dateparser
        # In this case, default to the language without script
        ("deu_frak", ["de"]),
        # Traditional and simplified chinese don't have the same name in dateparser,
        # so they're converted to the general chinese language
        ("chi_tra+chi_sim", ["zh"]),
        # If a language is not supported by dateparser, fallback to the supported ones
        ("eng+unsupported_language+por", ["en", "pt"]),
        # If no language is supported, fallback to default
        ("unsupported1+unsupported2", []),
        # Duplicate languages, should not duplicate in result
        ("eng+eng", ["en"]),
        # Language with script, but script is not mapped
        ("ita_unknownscript", ["it"]),
    ],
)
def test_ocr_to_dateparser_languages(ocr_language, expected):
    assert sorted(ocr_to_dateparser_languages(ocr_language)) == sorted(expected)


def test_ocr_to_dateparser_languages_exception(monkeypatch, caplog):
    # Patch LocaleDataLoader.get_locale_map to raise an exception
    class DummyLoader:
        def get_locale_map(self, locales=None):
            raise RuntimeError("Simulated error")

    with caplog.at_level(logging.WARNING):
        monkeypatch.setattr(utils, "LocaleDataLoader", lambda: DummyLoader())
        result = utils.ocr_to_dateparser_languages("eng+fra")
        assert result == []
        assert (
            "Set PAPERLESS_DATE_PARSER_LANGUAGES parameter to avoid this" in caplog.text
        )
