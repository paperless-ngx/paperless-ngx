import datetime
from unittest import TestCase

from paperless.settings import _parse_ignore_dates


class TestIgnoreDateParsing(TestCase):
    """
    Tests the parsing of the PAPERLESS_IGNORE_DATES setting value
    """

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
            ("1985-05-01", [datetime.date(1985, 5, 1)]),
            (
                "1985-05-01,1991-12-05",
                [datetime.date(1985, 5, 1), datetime.date(1991, 12, 5)],
            ),
            ("2010-12-13", [datetime.date(2010, 12, 13)]),
        ]
        for env_str, expected_dates in test_cases:
            expected_date_set = set()

            for expected_date in expected_dates:
                expected_date_set.add(expected_date)

            self.assertSetEqual(
                _parse_ignore_dates(env_str),
                expected_date_set,
            )
