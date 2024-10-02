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
            return value.strip()

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
