import os

from django.http import HttpResponse
from django.views.generic import View
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100000


class FaviconView(View):

    def get(self, request, *args, **kwargs):
        favicon = os.path.join(
            os.path.dirname(__file__),
            "static",
            "paperless",
            "img",
            "favicon.ico"
        )
        with open(favicon, "rb") as f:
            return HttpResponse(f, content_type="image/x-icon")
