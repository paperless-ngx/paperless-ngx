from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning
from django.core.checks import register

from documents.signals import document_consumer_declaration
from documents.templating.utils import convert_format_str_to_template_format


@register()
def parser_check(app_configs, **kwargs):
    parsers = []
    for response in document_consumer_declaration.send(None):
        parsers.append(response[1])

    if len(parsers) == 0:
        return [
            Error(
                "No parsers found. This is a bug. The consumer won't be "
                "able to consume any documents without parsers.",
            ),
        ]
    else:
        return []


@register()
def filename_format_check(app_configs, **kwargs):
    if settings.FILENAME_FORMAT:
        converted_format = convert_format_str_to_template_format(
            settings.FILENAME_FORMAT,
        )
        if converted_format != settings.FILENAME_FORMAT:
            return [
                Warning(
                    f"Filename format {settings.FILENAME_FORMAT} is using the old style, please update to use double curly brackets",
                    hint=converted_format,
                ),
            ]
    return []
