import os
from unittest import TestCase
from unittest import mock

import pytest

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
