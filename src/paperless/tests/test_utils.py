import pytest

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
    ],
)
def test_ocr_to_dateparser_languages(ocr_language, expected):
    assert sorted(ocr_to_dateparser_languages(ocr_language)) == sorted(expected)
