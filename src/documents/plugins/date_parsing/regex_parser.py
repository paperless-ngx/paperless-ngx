import datetime
import re
from collections.abc import Iterator
from re import Match

from documents.plugins.date_parsing.base import DateParserPluginBase


class RegexDateParserPlugin(DateParserPluginBase):
    """
    The default date parser, using a series of regular expressions.

    It is configured entirely by the DateParserConfig object
    passed to its constructor.
    """

    DATE_REGEX = re.compile(
        r"(\b|(?!=([_-])))(\d{1,2})[\.\/-](\d{1,2})[\.\/-](\d{4}|\d{2})(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))(\d{4}|\d{2})[\.\/-](\d{1,2})[\.\/-](\d{1,2})(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))(\d{1,2}[\. ]+[a-zéûäëčžúřěáíóńźçŞğü]{3,9} \d{4}|[a-zéûäëčžúřěáíóńźçŞğü]{3,9} \d{1,2}, \d{4})(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))([^\W\d_]{3,9} \d{1,2}, (\d{4}))(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))([^\W\d_]{3,9} \d{4})(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))(\d{1,2}[^ 0-9]{2}[\. ]+[^ ]{3,9}[ \.\/-]\d{4})(\b|(?=([_-])))|"
        r"(\b|(?!=([_-])))(\b\d{1,2}[ \.\/-][a-zéûäëčžúřěáíóńźçŞğü]{3}[ \.\/-]\d{4})(\b|(?=([_-])))",
        re.IGNORECASE,
    )

    def _process_match(
        self,
        match: Match[str],
        date_order: str,
    ) -> datetime.datetime | None:
        """
        Processes a single regex match using the base class helpers.
        """
        date_string = match.group(0)
        date = self._parse_string(date_string, date_order)
        return self._filter_date(date)

    def _process_content(
        self,
        content: str,
        date_order: str,
    ) -> Iterator[datetime.datetime]:
        """
        Finds all regex matches in content and yields valid dates.
        """
        for m in re.finditer(self.DATE_REGEX, content):
            date = self._process_match(m, date_order)
            if date is not None:
                yield date

    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        """
        Implementation of the abstract parse method.

        Reads its configuration from `self.config`.
        """
        if self.config.filename_date_order:
            yield from self._process_content(
                filename,
                self.config.filename_date_order,
            )

        yield from self._process_content(content, self.config.content_date_order)
