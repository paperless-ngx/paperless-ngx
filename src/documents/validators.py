from urllib.parse import urlparse

from django.core.exceptions import ValidationError
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
                _(f"Unable to parse URI {value}, missing scheme"),
                params={"value": value},
            )
        elif not parts.netloc and not parts.path:
            raise ValidationError(
                _(f"Unable to parse URI {value}, missing net location or path"),
                params={"value": value},
            )

        if allowed_schemes and parts.scheme not in allowed_schemes:
            raise ValidationError(
                _(
                    f"URI scheme '{parts.scheme}' is not allowed. Allowed schemes: {', '.join(allowed_schemes)}",
                ),
                params={"value": value, "scheme": parts.scheme},
            )

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(
            _(f"Unable to parse URI {value}"),
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
