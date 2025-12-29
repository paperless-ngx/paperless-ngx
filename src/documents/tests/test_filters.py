import datetime
from typing import Any
from typing import Literal

import pytest

from documents.templating.filters import localize_date


class TestDateLocalization:
    """
    Groups all tests related to the `localize_date` function.
    """

    TEST_DATE = datetime.date(2023, 10, 26)

    TEST_DATETIME = datetime.datetime(
        2023,
        10,
        26,
        14,
        30,
        5,
        tzinfo=datetime.timezone.utc,
    )

    TEST_DATETIME_STRING: str = "2023-10-26T14:30:05+00:00"

    TEST_DATE_STRING: str = "2023-10-26"

    @pytest.mark.parametrize(
        "value, format_style, locale_str, expected_output",
        [
            pytest.param(
                TEST_DATE,
                "EEEE, MMM d, yyyy",
                "en_US",
                "Thursday, Oct 26, 2023",
                id="date-en_US-custom",
            ),
            pytest.param(
                TEST_DATE,
                "dd.MM.yyyy",
                "de_DE",
                "26.10.2023",
                id="date-de_DE-custom",
            ),
            # German weekday and month name translation
            pytest.param(
                TEST_DATE,
                "EEEE",
                "de_DE",
                "Donnerstag",
                id="weekday-de_DE",
            ),
            pytest.param(
                TEST_DATE,
                "MMMM",
                "de_DE",
                "Oktober",
                id="month-de_DE",
            ),
            # French weekday and month name translation
            pytest.param(
                TEST_DATE,
                "EEEE",
                "fr_FR",
                "jeudi",
                id="weekday-fr_FR",
            ),
            pytest.param(
                TEST_DATE,
                "MMMM",
                "fr_FR",
                "octobre",
                id="month-fr_FR",
            ),
        ],
    )
    def test_localize_date_with_date_objects(
        self,
        value: datetime.date,
        format_style: str,
        locale_str: str,
        expected_output: str,
    ):
        """
        Tests `localize_date` with `date` objects across different locales and formats.
        """
        assert localize_date(value, format_style, locale_str) == expected_output

    @pytest.mark.parametrize(
        "value, format_style, locale_str, expected_output",
        [
            pytest.param(
                TEST_DATETIME,
                "yyyy.MM.dd G 'at' HH:mm:ss zzz",
                "en_US",
                "2023.10.26 AD at 14:30:05 UTC",
                id="datetime-en_US-custom",
            ),
            pytest.param(
                TEST_DATETIME,
                "dd.MM.yyyy",
                "fr_FR",
                "26.10.2023",
                id="date-fr_FR-custom",
            ),
            # Spanish weekday and month translation
            pytest.param(
                TEST_DATETIME,
                "EEEE",
                "es_ES",
                "jueves",
                id="weekday-es_ES",
            ),
            pytest.param(
                TEST_DATETIME,
                "MMMM",
                "es_ES",
                "octubre",
                id="month-es_ES",
            ),
            # Italian weekday and month translation
            pytest.param(
                TEST_DATETIME,
                "EEEE",
                "it_IT",
                "giovedì",
                id="weekday-it_IT",
            ),
            pytest.param(
                TEST_DATETIME,
                "MMMM",
                "it_IT",
                "ottobre",
                id="month-it_IT",
            ),
        ],
    )
    def test_localize_date_with_datetime_objects(
        self,
        value: datetime.datetime,
        format_style: str,
        locale_str: str,
        expected_output: str,
    ):
        # To handle the non-breaking space in French and other locales
        result = localize_date(value, format_style, locale_str)
        assert result.replace("\u202f", " ") == expected_output.replace("\u202f", " ")

    @pytest.mark.parametrize(
        "invalid_value",
        [
            1698330605,
            None,
            [],
            {},
        ],
    )
    def test_localize_date_raises_type_error_for_invalid_input(
        self,
        invalid_value: None | list[object] | dict[Any, Any] | Literal[1698330605],
    ):
        with pytest.raises(TypeError) as excinfo:
            localize_date(invalid_value, "medium", "en_US")

        assert f"Unsupported type {type(invalid_value)}" in str(excinfo.value)

    def test_localize_date_raises_error_for_invalid_locale(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            localize_date(self.TEST_DATE, "medium", "invalid_locale_code")

        assert "Invalid locale identifier" in str(excinfo.value)

    @pytest.mark.parametrize(
        "value, format_style, locale_str, expected_output",
        [
            pytest.param(
                TEST_DATETIME_STRING,
                "EEEE, MMM d, yyyy",
                "en_US",
                "Thursday, Oct 26, 2023",
                id="date-en_US-custom",
            ),
            pytest.param(
                TEST_DATETIME_STRING,
                "dd.MM.yyyy",
                "de_DE",
                "26.10.2023",
                id="date-de_DE-custom",
            ),
            # German weekday and month name translation
            pytest.param(
                TEST_DATETIME_STRING,
                "EEEE",
                "de_DE",
                "Donnerstag",
                id="weekday-de_DE",
            ),
            pytest.param(
                TEST_DATETIME_STRING,
                "MMMM",
                "de_DE",
                "Oktober",
                id="month-de_DE",
            ),
            # French weekday and month name translation
            pytest.param(
                TEST_DATETIME_STRING,
                "EEEE",
                "fr_FR",
                "jeudi",
                id="weekday-fr_FR",
            ),
            pytest.param(
                TEST_DATETIME_STRING,
                "MMMM",
                "fr_FR",
                "octobre",
                id="month-fr_FR",
            ),
        ],
    )
    def test_localize_date_with_datetime_string(
        self,
        value: str,
        format_style: str,
        locale_str: str,
        expected_output: str,
    ):
        """
        Tests `localize_date` with `date` string across different locales and formats.
        """
        assert localize_date(value, format_style, locale_str) == expected_output

    @pytest.mark.parametrize(
        "value, format_style, locale_str, expected_output",
        [
            pytest.param(
                TEST_DATE_STRING,
                "EEEE, MMM d, yyyy",
                "en_US",
                "Thursday, Oct 26, 2023",
                id="date-en_US-custom",
            ),
            pytest.param(
                TEST_DATE_STRING,
                "dd.MM.yyyy",
                "de_DE",
                "26.10.2023",
                id="date-de_DE-custom",
            ),
            # German weekday and month name translation
            pytest.param(
                TEST_DATE_STRING,
                "EEEE",
                "de_DE",
                "Donnerstag",
                id="weekday-de_DE",
            ),
            pytest.param(
                TEST_DATE_STRING,
                "MMMM",
                "de_DE",
                "Oktober",
                id="month-de_DE",
            ),
            # French weekday and month name translation
            pytest.param(
                TEST_DATE_STRING,
                "EEEE",
                "fr_FR",
                "jeudi",
                id="weekday-fr_FR",
            ),
            pytest.param(
                TEST_DATE_STRING,
                "MMMM",
                "fr_FR",
                "octobre",
                id="month-fr_FR",
            ),
        ],
    )
    def test_localize_date_with_date_string(
        self,
        value: str,
        format_style: str,
        locale_str: str,
        expected_output: str,
    ):
        """
        Tests `localize_date` with `date` string across different locales and formats.
        """
        assert localize_date(value, format_style, locale_str) == expected_output
