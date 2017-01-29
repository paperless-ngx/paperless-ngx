import os

from django.contrib import admin
from django.template import Library
from django.template.loader import get_template

from ..models import Document


register = Library()


@register.simple_tag(takes_context=True)
def change_list_results(context):
    """
    Django has a lot of places where you can override defaults, but
    unfortunately, `change_list_results.html` is not one of them.  In fact,
    it's a downright pain in the ass to override this file on a per-model basis
    and this is the cleanest way I could come up with.

    Basically all we've done here is defined `change_list_results.html` in an
    `admin` directory which globally overrides that file for *every* model.
    That template however simply loads this templatetag which determines
    whether we're currently looking at a `Document` listing or something else
    and loads the appropriate file in each case.

    Better work arounds for this are welcome as I hate this myself, but at the
    moment, it's all I could come up with.
    """

    path = os.path.join(
        os.path.dirname(admin.__file__),
        "templates",
        "admin",
        "change_list_results.html"
    )

    if context["cl"].model == Document:
        path = "admin/documents/document/change_list_results.html"

    return get_template(path).render(context)
