import pytest
from django.core.exceptions import ValidationError

from documents.validators import monetary_validator


class TestMonetaryValidator:
    """Tests for the monetary_validator function."""

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("12", id="whole-number"),
            pytest.param("-12.50", id="negative"),
            pytest.param("9999999999.99", id="twelve-digits"),
            pytest.param("GBP123.45", id="code-with-amount"),
            pytest.param("USD-12.50", id="code-with-negative"),
            pytest.param("EUR12.5", id="code-with-one-decimal"),
        ],
    )
    def test_valid_values(self, value: str) -> None:
        """
        GIVEN:
            - A plain decimal or an amount prefixed with a currency code
        WHEN:
            - The value is validated
        THEN:
            - No error is raised
        """
        monetary_validator(value)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("12.345", id="too-many-decimals"),
            pytest.param("99999999999.99", id="too-many-digits"),
            pytest.param("GBP12.345", id="code-with-too-many-decimals"),
            pytest.param("GBP12", id="code-without-decimals"),
            pytest.param("gbp12.50", id="lowercase-code"),
            pytest.param("GB12.50", id="short-code"),
            pytest.param("abc", id="not-a-number"),
            pytest.param("NaN", id="nan"),
        ],
    )
    def test_invalid_values(self, value: str) -> None:
        """
        GIVEN:
            - A value that is neither a valid decimal nor a coded amount
        WHEN:
            - The value is validated
        THEN:
            - A ValidationError is raised
        """
        with pytest.raises(ValidationError):
            monetary_validator(value)
