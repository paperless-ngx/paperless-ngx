import re
from datetime import date
from datetime import datetime

from babel import Locale
from babel import dates
from django.utils.dateparse import parse_date


def convert_format_str_to_template_format(old_format: str) -> str:
    """
    Converts old Python string format (with {}) to Jinja2 template style (with {{ }}),
    while ignoring existing {{ ... }} placeholders.

    :param old_format: The old style format string (e.g., "{title} by {author}")
    :return: Converted string in Django Template style (e.g., "{{ title }} by {{ author }}")
    """

    # Step 1: Match placeholders with single curly braces but not those with double braces
    pattern = r"(?<!\{)\{(\w*)\}(?!\})"  # Matches {var} but not {{var}}

    # Step 2: Replace the placeholders with {{ var }} or {{ }}
    def replace_with_django(match):
        variable = match.group(1)  # The variable inside the braces
        return f"{{{{ {variable} }}}}"  # Convert to {{ variable }}

    # Apply the substitution
    converted_format = re.sub(pattern, replace_with_django, old_format)

    return converted_format


def localize_date(value: date | datetime | str, format: str, locale: str) -> str:
    """
    Format a date, datetime or str object into a localized string using Babel.

    Args:
        value (date | datetime | str): The date or datetime to format. If a datetime
            is provided, it should be timezone-aware (e.g., UTC from a Django DB object).
            if str is provided is is parsed as date.
        format (str): The format to use. Can be one of Babel's preset formats
            ('short', 'medium', 'long', 'full') or a custom pattern string.
        locale (str): The locale code (e.g., 'en_US', 'fr_FR') to use for
            localization.

    Returns:
        str: The localized, formatted date string.

    Raises:
        TypeError: If `value` is not a date, datetime or str instance.
    """
    if isinstance(value, str):
        value = parse_date(value)

    try:
        Locale.parse(locale)
    except Exception as e:
        raise ValueError(f"Invalid locale identifier: {locale}") from e

    if isinstance(value, datetime):
        return dates.format_datetime(value, format=format, locale=locale)
    elif isinstance(value, date):
        return dates.format_date(value, format=format, locale=locale)
    else:
        raise TypeError(f"Unsupported type {type(value)} for localize_date")


def format_datetime(value: str | datetime, format: str) -> str:
    if isinstance(value, str):
        value = parse_date(value)
    return value.strftime(format=format)


def get_cf_value(
    custom_field_data: dict[str, dict[str, str]],
    name: str,
    default: str | None = None,
) -> str | None:
    if name in custom_field_data and custom_field_data[name]["value"] is not None:
        return custom_field_data[name]["value"]
    elif default is not None:
        return default
    return None
