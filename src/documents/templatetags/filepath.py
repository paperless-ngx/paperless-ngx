import os
import re

from django import template

register = template.Library()


class FilePathNode(template.Node):
    """
    A custom tag to remove extra spaces before and after / as well as remove
    any newlines from the resulting string.

    https://docs.djangoproject.com/en/5.1/howto/custom-template-tags/#parsing-until-another-block-tag
    """

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        def clean_filepath(value):
            """
            Clean up a filepath by:
            1. Removing newlines and carriage returns
            2. Removing extra spaces before and after forward slashes
            3. Preserving spaces in other parts of the path
            """
            value = value.replace("\n", "").replace("\r", "")
            value = re.sub(r"\s*/\s*", "/", value)

            # We remove trailing and leading separators, as these are always relative paths, not absolute, even if the user
            # tries
            return value.strip().strip(os.sep)

        output = self.nodelist.render(context)
        return clean_filepath(output)


@register.tag(name="filepath")
def construct_filepath(parser, token):
    """
    The registered tag as {% filepath %}, which is always loaded around the user provided template string to
    render everything as a single line, with minimal spaces
    """
    nodelist = parser.parse(("endfilepath",))
    parser.delete_first_token()
    return FilePathNode(nodelist)


def convert_to_django_template_format(old_format: str) -> str:
    """
    Converts old Python string format (with {}) to Django template style (with {{ }}),
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
