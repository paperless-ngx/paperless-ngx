import datetime
import logging
from abc import ABC
from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from types import TracebackType

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

import dateparser

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DateParserConfig:
    """
    Configuration for a DateParser instance.

    This object is created by the factory and passed to the
    parser's constructor, decoupling the parser from settings.
    """

    languages: list[str]
    timezone_str: str
    ignore_dates: set[datetime.date]

    # A "now" timestamp for filtering future dates.
    # Passed in by the factory.
    reference_time: datetime.datetime

    # Settings for the default RegexDateParser
    # Other plugins should use or consider these, but it is not required
    filename_date_order: str | None
    content_date_order: str


class DateParserPluginBase(ABC):
    """
    Abstract base class for date parsing strategies.

    Instances are configured via a DateParserConfig object.
    """

    def __init__(self, config: DateParserConfig):
        """
        Initializes the parser with its configuration.
        """
        self.config = config

    def __enter__(self) -> Self:
        """
        Enter the runtime context related to this object.

        Subclasses can override this to acquire resources (connections, handles).
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit the runtime context related to this object.

        Subclasses can override this to release resources.
        """
        # Default implementation does nothing.
        # Returning None implies exceptions are propagated.

    def _parse_string(
        self,
        date_string: str,
        date_order: str,
    ) -> datetime.datetime | None:
        """
        Helper method to parse a single date string using dateparser.

        Uses configuration from `self.config`.
        """
        try:
            return dateparser.parse(
                date_string,
                settings={
                    "DATE_ORDER": date_order,
                    "PREFER_DAY_OF_MONTH": "first",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "TIMEZONE": self.config.timezone_str,
                },
                locales=self.config.languages,
            )
        except Exception as e:
            logger.error(f"Error while parsing date string '{date_string}': {e}")
            return None

    def _filter_date(
        self,
        date: datetime.datetime | None,
    ) -> datetime.datetime | None:
        """
        Helper method to validate a parsed datetime object.

        Uses configuration from `self.config`.
        """
        if (
            date is not None
            and date.year > 1900
            and date <= self.config.reference_time
            and date.date() not in self.config.ignore_dates
        ):
            return date
        return None

    @abstractmethod
    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        """
        Parses a document's filename and content, yielding valid datetime objects.
        """
