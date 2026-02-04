import datetime
import logging
from typing import Any

import pytest
import pytest_mock

from documents.plugins.date_parsing.base import DateParserConfig
from documents.plugins.date_parsing.regex_parser import RegexDateParserPlugin


@pytest.mark.date_parsing
class TestParseString:
    """Tests for DateParser._parse_string method via RegexDateParser."""

    @pytest.mark.parametrize(
        ("date_string", "date_order", "expected_year"),
        [
            pytest.param("15/01/2024", "DMY", 2024, id="dmy_slash"),
            pytest.param("01/15/2024", "MDY", 2024, id="mdy_slash"),
            pytest.param("2024/01/15", "YMD", 2024, id="ymd_slash"),
            pytest.param("January 15, 2024", "DMY", 2024, id="month_name_comma"),
            pytest.param("15 Jan 2024", "DMY", 2024, id="day_abbr_month_year"),
            pytest.param("15.01.2024", "DMY", 2024, id="dmy_dot"),
            pytest.param("2024-01-15", "YMD", 2024, id="ymd_dash"),
        ],
    )
    def test_parse_string_valid_formats(
        self,
        regex_parser: RegexDateParserPlugin,
        date_string: str,
        date_order: str,
        expected_year: int,
    ) -> None:
        """Should correctly parse various valid date formats."""
        result = regex_parser._parse_string(date_string, date_order)

        assert result is not None
        assert result.year == expected_year

    @pytest.mark.parametrize(
        "invalid_string",
        [
            pytest.param("not a date", id="plain_text"),
            pytest.param("32/13/2024", id="invalid_day_month"),
            pytest.param("", id="empty_string"),
            pytest.param("abc123xyz", id="alphanumeric_gibberish"),
            pytest.param("99/99/9999", id="out_of_range"),
        ],
    )
    def test_parse_string_invalid_input(
        self,
        regex_parser: RegexDateParserPlugin,
        invalid_string: str,
    ) -> None:
        """Should return None for invalid date strings."""
        result = regex_parser._parse_string(invalid_string, "DMY")

        assert result is None

    def test_parse_string_handles_exceptions(
        self,
        caplog: pytest.LogCaptureFixture,
        mocker: pytest_mock.MockerFixture,
        regex_parser: RegexDateParserPlugin,
    ) -> None:
        """Should handle and log exceptions from dateparser gracefully."""
        with caplog.at_level(
            logging.ERROR,
            logger="documents.plugins.date_parsing.base",
        ):
            # We still need to mock dateparser.parse to force the exception
            mocker.patch(
                "documents.plugins.date_parsing.base.dateparser.parse",
                side_effect=ValueError(
                    "Parsing error: 01/01/2024",
                ),
            )

            # 1. Execute the function under test
            result = regex_parser._parse_string("01/01/2024", "DMY")

            assert result is None

            # Check if an error was logged
            assert len(caplog.records) == 1
            assert caplog.records[0].levelname == "ERROR"

            # Check if the specific error message is present
            assert "Error while parsing date string" in caplog.text
            # Optional: Check for the exact exception message if it's included in the log
            assert "Parsing error: 01/01/2024" in caplog.text


@pytest.mark.date_parsing
class TestFilterDate:
    """Tests for DateParser._filter_date method via RegexDateParser."""

    @pytest.mark.parametrize(
        ("date", "expected_output"),
        [
            # Valid Dates
            pytest.param(
                datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc),
                datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc),
                id="valid_past_date",
            ),
            pytest.param(
                datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
                datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
                id="exactly_at_reference",
            ),
            pytest.param(
                datetime.datetime(1901, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(1901, 1, 1, tzinfo=datetime.timezone.utc),
                id="year_1901_valid",
            ),
            # Date is > reference_time
            pytest.param(
                datetime.datetime(2024, 1, 16, tzinfo=datetime.timezone.utc),
                None,
                id="future_date_day_after",
            ),
            # date.date() in ignore_dates
            pytest.param(
                datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
                None,
                id="ignored_date_midnight_jan1",
            ),
            pytest.param(
                datetime.datetime(2024, 1, 1, 10, 30, 0, tzinfo=datetime.timezone.utc),
                None,
                id="ignored_date_midday_jan1",
            ),
            pytest.param(
                datetime.datetime(2024, 12, 25, 15, 0, 0, tzinfo=datetime.timezone.utc),
                None,
                id="ignored_date_dec25_future",
            ),
            # date.year <= 1900
            pytest.param(
                datetime.datetime(1899, 12, 31, tzinfo=datetime.timezone.utc),
                None,
                id="year_1899",
            ),
            pytest.param(
                datetime.datetime(1900, 1, 1, tzinfo=datetime.timezone.utc),
                None,
                id="year_1900_boundary",
            ),
            # date is None
            pytest.param(None, None, id="none_input"),
        ],
    )
    def test_filter_date_validation_rules(
        self,
        config_with_ignore_dates: DateParserConfig,
        date: datetime.datetime | None,
        expected_output: datetime.datetime | None,
    ) -> None:
        """Should correctly validate dates against various rules."""
        parser = RegexDateParserPlugin(config_with_ignore_dates)
        result = parser._filter_date(date)
        assert result == expected_output

    def test_filter_date_respects_ignore_dates(
        self,
        config_with_ignore_dates: DateParserConfig,
    ) -> None:
        """Should filter out dates in the ignore_dates set."""
        parser = RegexDateParserPlugin(config_with_ignore_dates)

        ignored_date = datetime.datetime(
            2024,
            1,
            1,
            12,
            0,
            tzinfo=datetime.timezone.utc,
        )
        another_ignored = datetime.datetime(
            2024,
            12,
            25,
            15,
            30,
            tzinfo=datetime.timezone.utc,
        )
        allowed_date = datetime.datetime(
            2024,
            1,
            2,
            12,
            0,
            tzinfo=datetime.timezone.utc,
        )

        assert parser._filter_date(ignored_date) is None
        assert parser._filter_date(another_ignored) is None
        assert parser._filter_date(allowed_date) == allowed_date

    def test_filter_date_timezone_aware(
        self,
        regex_parser: RegexDateParserPlugin,
    ) -> None:
        """Should work with timezone-aware datetimes."""
        date_utc = datetime.datetime(2024, 1, 10, 12, 0, tzinfo=datetime.timezone.utc)

        result = regex_parser._filter_date(date_utc)

        assert result is not None
        assert result.tzinfo is not None


@pytest.mark.date_parsing
class TestRegexDateParser:
    @pytest.mark.parametrize(
        ("filename", "content", "expected"),
        [
            pytest.param(
                "report-2023-12-25.txt",
                "Event recorded on 25/12/2022.",
                [
                    datetime.datetime(2023, 12, 25, tzinfo=datetime.timezone.utc),
                    datetime.datetime(2022, 12, 25, tzinfo=datetime.timezone.utc),
                ],
                id="filename-y-m-d_and_content-d-m-y",
            ),
            pytest.param(
                "img_2023.01.02.jpg",
                "Taken on 01/02/2023",
                [
                    datetime.datetime(2023, 1, 2, tzinfo=datetime.timezone.utc),
                    datetime.datetime(2023, 2, 1, tzinfo=datetime.timezone.utc),
                ],
                id="ambiguous-dates-respect-orders",
            ),
            pytest.param(
                "notes.txt",
                "bad date 99/99/9999 and 25/12/2022",
                [
                    datetime.datetime(2022, 12, 25, tzinfo=datetime.timezone.utc),
                ],
                id="parse-exception-skips-bad-and-yields-good",
            ),
        ],
    )
    def test_parse_returns_expected_dates(
        self,
        base_config: DateParserConfig,
        mocker: pytest_mock.MockerFixture,
        filename: str,
        content: str,
        expected: list[datetime.datetime],
    ) -> None:
        """
        High-level tests that exercise RegexDateParser.parse only.
        dateparser.parse is mocked so tests are deterministic.
        """
        parser = RegexDateParserPlugin(base_config)

        # Patch the dateparser.parse
        target = "documents.plugins.date_parsing.base.dateparser.parse"

        def fake_parse(
            date_string: str,
            settings: dict[str, Any] | None = None,
            locales: None = None,
        ) -> datetime.datetime | None:
            date_order = settings.get("DATE_ORDER") if settings else None

            # Filename-style YYYY-MM-DD / YYYY.MM.DD
            if (
                "2023-12-25" in date_string
                or "2023.12.25" in date_string
                or "2023-12-25" in date_string
            ):
                return datetime.datetime(2023, 12, 25, tzinfo=datetime.timezone.utc)

            # content DMY 25/12/2022
            if "25/12/2022" in date_string or "25-12-2022" in date_string:
                return datetime.datetime(2022, 12, 25, tzinfo=datetime.timezone.utc)

            # filename YMD 2023.01.02
            if "2023.01.02" in date_string or "2023-01-02" in date_string:
                return datetime.datetime(2023, 1, 2, tzinfo=datetime.timezone.utc)

            # ambiguous 01/02/2023 -> respect DATE_ORDER setting
            if "01/02/2023" in date_string:
                if date_order == "DMY":
                    return datetime.datetime(2023, 2, 1, tzinfo=datetime.timezone.utc)
                if date_order == "YMD":
                    return datetime.datetime(2023, 1, 2, tzinfo=datetime.timezone.utc)
                # fallback
                return datetime.datetime(2023, 2, 1, tzinfo=datetime.timezone.utc)

            # simulate parse failure for malformed input
            if "99/99/9999" in date_string or "bad date" in date_string:
                raise Exception("parse failed for malformed date")

            return None

        mocker.patch(target, side_effect=fake_parse)

        results = list(parser.parse(filename, content))

        assert results == expected
        for dt in results:
            assert dt.tzinfo is not None

    def test_parse_filters_future_and_ignored_dates(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        Ensure parser filters out:
          - dates after reference_time
          - dates whose .date() are in ignore_dates
        """
        cfg = DateParserConfig(
            languages=["en"],
            timezone_str="UTC",
            ignore_dates={datetime.date(2023, 12, 10)},
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
        parser = RegexDateParserPlugin(cfg)

        target = "documents.plugins.date_parsing.base.dateparser.parse"

        def fake_parse(
            date_string: str,
            settings: dict[str, Any] | None = None,
            locales: None = None,
        ) -> datetime.datetime | None:
            if "10/12/2023" in date_string or "10-12-2023" in date_string:
                # ignored date
                return datetime.datetime(2023, 12, 10, tzinfo=datetime.timezone.utc)
            if "01/02/2024" in date_string or "01-02-2024" in date_string:
                # future relative to reference_time -> filtered
                return datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
            if "05/01/2023" in date_string or "05-01-2023" in date_string:
                # valid
                return datetime.datetime(2023, 1, 5, tzinfo=datetime.timezone.utc)
            return None

        mocker.patch(target, side_effect=fake_parse)

        content = "Ignored: 10/12/2023, Future: 01/02/2024, Keep: 05/01/2023"
        results = list(parser.parse("whatever.txt", content))

        assert results == [datetime.datetime(2023, 1, 5, tzinfo=datetime.timezone.utc)]

    def test_parse_handles_no_matches_and_returns_empty_list(
        self,
        base_config: DateParserConfig,
    ) -> None:
        """
        When there are no matching date-like substrings, parse should yield nothing.
        """
        parser = RegexDateParserPlugin(base_config)
        results = list(
            parser.parse("no-dates.txt", "this has no dates whatsoever"),
        )
        assert results == []

    def test_parse_skips_filename_when_filename_date_order_none(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        When filename_date_order is None the parser must not attempt to parse the filename.
        Only dates found in the content should be passed to dateparser.parse.
        """
        cfg = DateParserConfig(
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
            filename_date_order=None,
            content_date_order="DMY",
        )
        parser = RegexDateParserPlugin(cfg)

        # Patch the module's dateparser.parse so we can inspect calls
        target = "documents.plugins.date_parsing.base.dateparser.parse"

        def fake_parse(
            date_string: str,
            settings: dict[str, Any] | None = None,
            locales: None = None,
        ) -> datetime.datetime | None:
            # return distinct datetimes so we can tell which source was parsed
            if "25/12/2022" in date_string:
                return datetime.datetime(2022, 12, 25, tzinfo=datetime.timezone.utc)
            if "2023-12-25" in date_string:
                return datetime.datetime(2023, 12, 25, tzinfo=datetime.timezone.utc)
            return None

        mock = mocker.patch(target, side_effect=fake_parse)

        filename = "report-2023-12-25.txt"
        content = "Event recorded on 25/12/2022."

        results = list(parser.parse(filename, content))

        # Only the content date should have been parsed -> one call
        assert mock.call_count == 1

        # # first call, first positional arg
        called_date_string = mock.call_args_list[0][0][0]
        assert "25/12/2022" in called_date_string
        # And the parser should have yielded the corresponding datetime
        assert results == [
            datetime.datetime(2022, 12, 25, tzinfo=datetime.timezone.utc),
        ]
