import datetime
from collections.abc import Generator
from typing import Any

import pytest
import pytest_django

from documents.plugins.date_parsing import _discover_parser_class
from documents.plugins.date_parsing.base import DateParserConfig
from documents.plugins.date_parsing.regex_parser import RegexDateParserPlugin


@pytest.fixture
def base_config() -> DateParserConfig:
    """Basic configuration for date parser testing."""
    return DateParserConfig(
        languages=["en"],
        timezone_str="UTC",
        ignore_dates=set(),
        reference_time=datetime.datetime(
            2024,
            1,
            15,
            12,
            0,
            0,
            tzinfo=datetime.timezone.utc,
        ),
        filename_date_order="YMD",
        content_date_order="DMY",
    )


@pytest.fixture
def config_with_ignore_dates() -> DateParserConfig:
    """Configuration with dates to ignore."""
    return DateParserConfig(
        languages=["en", "de"],
        timezone_str="America/New_York",
        ignore_dates={datetime.date(2024, 1, 1), datetime.date(2024, 12, 25)},
        reference_time=datetime.datetime(
            2024,
            1,
            15,
            12,
            0,
            0,
            tzinfo=datetime.timezone.utc,
        ),
        filename_date_order="DMY",
        content_date_order="MDY",
    )


@pytest.fixture
def regex_parser(base_config: DateParserConfig) -> RegexDateParserPlugin:
    """Instance of RegexDateParser with base config."""
    return RegexDateParserPlugin(base_config)


@pytest.fixture
def clear_lru_cache() -> Generator[None, None, None]:
    """
    Ensure the LRU cache for _discover_parser_class is cleared
    before and after any test that depends on it.
    """
    _discover_parser_class.cache_clear()
    yield
    _discover_parser_class.cache_clear()


@pytest.fixture
def mock_date_parser_settings(settings: pytest_django.fixtures.SettingsWrapper) -> Any:
    """
    Override Django settings for the duration of date parser tests.
    """
    settings.DATE_PARSER_LANGUAGES = ["en", "de"]
    settings.TIME_ZONE = "UTC"
    settings.IGNORE_DATES = [datetime.date(1900, 1, 1)]
    settings.FILENAME_DATE_ORDER = "YMD"
    settings.DATE_ORDER = "DMY"
    return settings
