import re


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
