import os
from unittest import TestCase
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

from paperless.settings import _get_allauth_trusted_proxy_count
from paperless.settings import _get_classifier_language_setting
from paperless.settings import _get_llm_extra_params
from paperless.settings import _get_search_language_setting
from paperless.settings import _parse_paperless_url
from paperless.settings import default_threads_per_worker


class TestThreadCalculation(TestCase):
    def test_workers_threads(self) -> None:
        """
        GIVEN:
            - Certain CPU counts
        WHEN:
            - Threads per worker is calculated
        THEN:
            - Threads per worker less than or equal to CPU count
            - At least 1 thread per worker
        """
        default_workers = 1

        for i in range(1, 64):
            with mock.patch(
                "paperless.settings.multiprocessing.cpu_count",
            ) as cpu_count:
                cpu_count.return_value = i

                default_threads = default_threads_per_worker(default_workers)

                self.assertGreaterEqual(default_threads, 1)

                self.assertLessEqual(default_workers * default_threads, i)


class TestClassifierLanguageSetting:
    @pytest.mark.parametrize(
        ("ocr_language", "expected"),
        [
            pytest.param("dan", "danish", id="danish"),
            pytest.param("nld", "dutch", id="dutch"),
            pytest.param("eng", "english", id="english"),
            pytest.param("fin", "finnish", id="finnish"),
            pytest.param("fra", "french", id="french"),
            pytest.param("deu", "german", id="german"),
            pytest.param("ita", "italian", id="italian"),
            pytest.param("nor", "norwegian", id="norwegian"),
            pytest.param("por", "portuguese", id="portuguese"),
            pytest.param("rus", "russian", id="russian"),
            pytest.param("spa", "spanish", id="spanish"),
            pytest.param("swe", "swedish", id="swedish"),
            pytest.param("eng+deu", "english", id="primary-english"),
            pytest.param("deu+eng", "german", id="primary-german"),
            pytest.param("ell", None, id="greek-unsupported"),
            pytest.param("chi_sim", None, id="chinese-unsupported"),
        ],
    )
    def test_maps_primary_ocr_language(
        self,
        ocr_language: str,
        expected: str | None,
    ) -> None:
        """
        GIVEN:
            - An OCR language setting, possibly listing several languages
        WHEN:
            - The classifier language is determined
        THEN:
            - The first OCR language maps to its classifier language, or None
              if unsupported
        """
        assert _get_classifier_language_setting(ocr_language) == expected


def test_allauth_trusted_proxy_count_defaults_to_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PAPERLESS_ALLAUTH_TRUSTED_PROXY_COUNT", raising=False)

    assert _get_allauth_trusted_proxy_count(["proxy-v4", "proxy-v6"]) == 2


def test_allauth_trusted_proxy_count_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPERLESS_ALLAUTH_TRUSTED_PROXY_COUNT", "1")

    assert _get_allauth_trusted_proxy_count(["proxy-v4", "proxy-v6"]) == 1


def test_allauth_trusted_proxy_count_rejects_negative_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPERLESS_ALLAUTH_TRUSTED_PROXY_COUNT", "-1")

    with pytest.raises(ImproperlyConfigured, match="must be zero or greater"):
        _get_allauth_trusted_proxy_count([])


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("en", "en"),
        ("de", "de"),
        ("fr", "fr"),
        ("swedish", "swedish"),
    ],
)
def test_get_search_language_setting_explicit_valid(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
    expected: str,
) -> None:
    """
    GIVEN:
        - PAPERLESS_SEARCH_LANGUAGE is set to a valid Tantivy stemmer language
    WHEN:
        - _get_search_language_setting is called
    THEN:
        - The explicit value is returned regardless of the OCR language
    """
    monkeypatch.setenv("PAPERLESS_SEARCH_LANGUAGE", env_value)
    assert _get_search_language_setting("deu") == expected


def test_get_search_language_setting_explicit_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN:
        - PAPERLESS_SEARCH_LANGUAGE is set to an unsupported language code
    WHEN:
        - _get_search_language_setting is called
    THEN:
        - ValueError is raised
    """
    monkeypatch.setenv("PAPERLESS_SEARCH_LANGUAGE", "klingon")
    with pytest.raises(ValueError, match="klingon"):
        _get_search_language_setting("eng")


class TestPaperlessURLSettings(TestCase):
    def test_paperless_url(self) -> None:
        """
        GIVEN:
            - PAPERLESS_URL is set
        WHEN:
            - The URL is parsed
        THEN:
            - The URL is returned and present in related settings
        """
        with mock.patch.dict(
            os.environ,
            {
                "PAPERLESS_URL": "https://example.com",
            },
        ):
            url = _parse_paperless_url()
            self.assertEqual("https://example.com", url)
            from django.conf import settings

            self.assertIn(url, settings.CSRF_TRUSTED_ORIGINS)
            self.assertIn(url, settings.CORS_ALLOWED_ORIGINS)


class TestLlmExtraParams:
    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            pytest.param(None, {}, id="unset"),
            pytest.param(
                '{"reasoning_effort": "none"}',
                {"reasoning_effort": "none"},
                id="json-object",
            ),
        ],
    )
    def test_parses(
        self,
        monkeypatch,
        env_value,
        expected,
    ):
        if env_value is None:
            monkeypatch.delenv("PAPERLESS_AI_LLM_EXTRA_PARAMS", raising=False)
        else:
            monkeypatch.setenv("PAPERLESS_AI_LLM_EXTRA_PARAMS", env_value)
        assert _get_llm_extra_params() == expected

    @pytest.mark.parametrize(
        ("env_value", "match"),
        [
            pytest.param("reasoning_effort=none", "valid JSON", id="invalid-json"),
            pytest.param('["none"]', "JSON object", id="not-an-object"),
        ],
    )
    def test_invalid_raises(
        self,
        monkeypatch,
        env_value,
        match,
    ):
        monkeypatch.setenv("PAPERLESS_AI_LLM_EXTRA_PARAMS", env_value)
        with pytest.raises(ImproperlyConfigured, match=match):
            _get_llm_extra_params()
