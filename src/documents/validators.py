from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def uri_validator(value) -> None:
    """
    Raises a ValidationError if the given value does not parse as an
    URI looking thing, which we're defining as a scheme and either network
    location or path value
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
    except Exception as e:
        raise ValidationError(
            _(f"Unable to parse URI {value}"),
            params={"value": value},
        ) from e
