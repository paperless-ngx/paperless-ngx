import logging
from functools import lru_cache
from importlib.metadata import EntryPoint
from importlib.metadata import entry_points
from typing import Final

from django.conf import settings
from django.utils import timezone

from documents.plugins.date_parsing.base import DateParserConfig
from documents.plugins.date_parsing.base import DateParserPluginBase
from documents.plugins.date_parsing.regex_parser import RegexDateParserPlugin
from paperless.config import OcrConfig
from paperless.utils import ocr_to_dateparser_languages

logger = logging.getLogger(__name__)

DATE_PARSER_ENTRY_POINT_GROUP: Final = "paperless_ngx.date_parsers"


@lru_cache(maxsize=1)
def _discover_parser_class() -> type[DateParserPluginBase]:
    """
    Discovers the date parser plugin class to use.

    - If one or more plugins are found, sorts them by name and returns the first.
    - If no plugins are found, returns the default RegexDateParser.
    """

    eps: tuple[EntryPoint, ...]
    try:
        eps = entry_points(group=DATE_PARSER_ENTRY_POINT_GROUP)
    except Exception as e:
        # Log a warning
        logger.warning(f"Could not query entry points for date parsers: {e}")
        eps = ()

    valid_plugins: list[EntryPoint] = []
    for ep in eps:
        try:
            plugin_class = ep.load()
            if plugin_class and issubclass(plugin_class, DateParserPluginBase):
                valid_plugins.append(ep)
            else:
                logger.warning(f"Plugin {ep.name} does not subclass DateParser.")
        except Exception as e:
            logger.error(f"Unable to load date parser plugin {ep.name}: {e}")

    if not valid_plugins:
        return RegexDateParserPlugin

    valid_plugins.sort(key=lambda ep: ep.name)

    if len(valid_plugins) > 1:
        logger.warning(
            f"Multiple date parsers found: "
            f"{[ep.name for ep in valid_plugins]}. "
            f"Using the first one by name: '{valid_plugins[0].name}'.",
        )

    return valid_plugins[0].load()


def get_date_parser() -> DateParserPluginBase:
    """
    Factory function to get an initialized date parser instance.

    This function is responsible for:
    1. Discovering the correct parser class (plugin or default).
    2. Loading configuration from Django settings.
    3. Instantiating the parser with the configuration.
    """
    # 1. Discover the class (this is cached)
    parser_class = _discover_parser_class()

    # 2. Load configuration from settings
    # TODO: Get the language from the settings and/or configuration object, depending
    ocr_config = OcrConfig()
    languages = settings.DATE_PARSER_LANGUAGES or ocr_to_dateparser_languages(
        ocr_config.language,
    )

    config = DateParserConfig(
        languages=languages,
        timezone_str=settings.TIME_ZONE,
        ignore_dates=settings.IGNORE_DATES,
        reference_time=timezone.now(),
        filename_date_order=settings.FILENAME_DATE_ORDER,
        content_date_order=settings.DATE_ORDER,
    )

    # 3. Instantiate the discovered class with the config
    return parser_class(config=config)


__all__ = [
    "DateParserConfig",
    "DateParserPluginBase",
    "RegexDateParserPlugin",
    "get_date_parser",
]
