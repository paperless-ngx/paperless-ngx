import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

from paperless.settings import _get_allauth_trusted_proxy_count
from paperless.settings import _get_search_language_setting
from paperless.settings import _parse_paperless_url
from paperless.settings import default_threads_per_worker

_SRC_DIR = Path(__file__).parents[3]


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


def test_explicit_search_language_during_settings_import() -> None:
    code = (
        "from paperless.settings import SEARCH_LANGUAGE; assert SEARCH_LANGUAGE == 'de'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=_SRC_DIR,
        env={
            **os.environ,
            "PAPERLESS_SEARCH_LANGUAGE": "de",
            "PAPERLESS_SECRET_KEY": "test-secret-key",
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr


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
