import os

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag()
def custom_css():
    theme_path = os.path.join(
        settings.MEDIA_ROOT,
        "overrides.css"
    )
    if os.path.exists(theme_path):
        return mark_safe(
            '<link rel="stylesheet" type="text/css" href="{}" />'.format(
                os.path.join(settings.MEDIA_URL, "overrides.css")
            )
        )
    return ""


@register.simple_tag()
def custom_js():
    theme_path = os.path.join(
        settings.MEDIA_ROOT,
        "overrides.js"
    )
    if os.path.exists(theme_path):
        return mark_safe(
            '<script src="{}"></script>'.format(
                os.path.join(settings.MEDIA_URL, "overrides.js")
            )
        )
    return ""
