import logging

import pytest

from paperless import utils
from paperless.utils import ocr_to_dateparser_languages


@pytest.mark.parametrize(
    ("ocr_language", "expected"),
    [
        pytest.param("eng", ["en"], id="single-language"),
        pytest.param("fra+ita+lao", ["fr", "it", "lo"], id="multiple-languages"),
        pytest.param("fil", ["fil"], id="no-two-letter-equivalent"),
        pytest.param(
            "aze_cyrl+srp_latn",
            ["az-Cyrl", "sr-Latn"],
            id="script-supported-by-dateparser",
        ),
        pytest.param(
            "deu_frak",
            ["de"],
            id="script-not-supported-falls-back-to-language",
        ),
        pytest.param(
            "chi_tra+chi_sim",
            ["zh"],
            id="chinese-variants-collapse-to-general",
        ),
        pytest.param(
            "eng+unsupported_language+por",
            ["en", "pt"],
            id="unsupported-language-skipped",
        ),
        pytest.param(
            "unsupported1+unsupported2",
            [],
            id="all-unsupported-returns-empty",
        ),
        pytest.param("eng+eng", ["en"], id="duplicates-deduplicated"),
        pytest.param(
            "ita_unknownscript",
            ["it"],
            id="unknown-script-falls-back-to-language",
        ),
    ],
)
def test_ocr_to_dateparser_languages(ocr_language: str, expected: list[str]) -> None:
    assert sorted(ocr_to_dateparser_languages(ocr_language)) == sorted(expected)


def test_ocr_to_dateparser_languages_exception(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
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
