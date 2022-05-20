import datetime
from unittest import TestCase

from paperless.settings import _parse_ignore_dates


class TestIgnoreDateParsing(TestCase):
    """
    Tests the parsing of the PAPERLESS_IGNORE_DATES setting value
    """

    def _parse_checker(self, test_cases):
        """
        Helper function to check ignore date parsing

        Args:
            test_cases (_type_): _description_
        """
        for env_str, date_format, expected_date_set in test_cases:

            self.assertSetEqual(
                _parse_ignore_dates(env_str, date_format),
                expected_date_set,
            )

    def test_no_ignore_dates_set(self):
        """
        GIVEN:
            - No ignore dates are set
        THEN:
            - No ignore dates are parsed
        """
        self.assertSetEqual(_parse_ignore_dates(""), set())

    def test_single_ignore_dates_set(self):
        """
        GIVEN:
            - Ignore dates are set per certain inputs
        THEN:
            - All ignore dates are parsed
        """
        test_cases = [
            ("1985-05-01", "YMD", {datetime.date(1985, 5, 1)}),
            (
                "1985-05-01,1991-12-05",
                "YMD",
                {datetime.date(1985, 5, 1), datetime.date(1991, 12, 5)},
            ),
            ("2010-12-13", "YMD", {datetime.date(2010, 12, 13)}),
            ("11.01.10", "DMY", {datetime.date(2010, 1, 11)}),
            (
                "11.01.2001,15-06-1996",
                "DMY",
                {datetime.date(2001, 1, 11), datetime.date(1996, 6, 15)},
            ),
        ]

        self._parse_checker(test_cases)
