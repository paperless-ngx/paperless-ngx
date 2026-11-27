from decimal import Decimal
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


def uri_validator(value: str, allowed_schemes: set[str] | None = None) -> None:
    """
    Validates that the given value parses as a URI with required components
    and optionally restricts to specific schemes.

    Args:
        value: The URI string to validate
        allowed_schemes: Optional set/list of allowed schemes (e.g. {'http', 'https'}).
                        If None, all schemes are allowed.

    Raises:
        ValidationError: If the URI is invalid or uses a disallowed scheme
    """
    try:
        parts = urlparse(value)
        if not parts.scheme:
            raise ValidationError(
                _("Unable to parse URI %(value)s, missing scheme"),
                params={"value": value},
            )
        elif not parts.netloc and not parts.path:
            raise ValidationError(
                _("Unable to parse URI %(value)s, missing net location or path"),
                params={"value": value},
            )

        if allowed_schemes and parts.scheme not in allowed_schemes:
            raise ValidationError(
                _(
                    "URI scheme '%(scheme)s' is not allowed. Allowed schemes: %(allowed)s",
                ),
                params={
                    "value": value,
                    "scheme": parts.scheme,
                    "allowed": ", ".join(sorted(allowed_schemes)),
                },
            )

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(
            _("Unable to parse URI %(value)s"),
            params={"value": value},
        ) from e


def url_validator(value) -> None:
    """
    Validates that the given value is a valid HTTP or HTTPS URL.

    Args:
        value: The URL string to validate

    Raises:
        ValidationError: If the URL is invalid or not using http/https scheme
    """
    uri_validator(value, allowed_schemes={"http", "https"})


def monetary_validator(value: str) -> None:
    """
    Validates the stored value of a monetary custom field.

    Accepts either a plain decimal with at most 12 digits and 2 decimal places
    (the legacy format), or a two-decimal number prefixed by a three letter
    uppercase currency code, e.g. GBP123.45 or USD-12.50.

    Args:
        value: The monetary value to validate

    Raises:
        ValidationError: If the value matches neither format
    """
    try:
        # First try to validate as a number from legacy format
        DecimalValidator(max_digits=12, decimal_places=2)(Decimal(str(value)))
    except Exception:
        # If that fails, try to validate as a monetary string
        RegexValidator(
            regex=r"^[A-Z]{3}-?\d+(\.\d{1,2})$",
            message="Must be a two-decimal number with optional currency code e.g. GBP123.45",
        )(value)
