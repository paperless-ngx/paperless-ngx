import re

from django.contrib.admin.templatetags.admin_list import (
    result_headers,
    result_hidden_fields,
    results
)
from django.template import Library


EXTRACT_URL = re.compile(r'href="(.*?)"')

register = Library()


@register.inclusion_tag("admin/documents/document/change_list_results.html")
def result_list(cl):
    """
    Copy/pasted from django.contrib.admin.templatetags.admin_list just so I can
    modify the value passed to `.inclusion_tag()` in the decorator here.  There
    must be a cleaner way... right?
    """
    headers = list(result_headers(cl))
    num_sorted_fields = 0
    for h in headers:
        if h['sortable'] and h['sorted']:
            num_sorted_fields += 1
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': headers,
            'num_sorted_fields': num_sorted_fields,
            'results': map(add_doc_edit_url, results(cl))}


def add_doc_edit_url(result):
    """
    Make the document edit URL accessible to the view as a separate item
    """
    title = result[1]
    match = re.search(EXTRACT_URL, title)
    edit_doc_url = match.group(1)
    result.append(edit_doc_url)
    return result
