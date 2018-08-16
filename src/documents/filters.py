from django_filters.rest_framework import CharFilter, FilterSet, BooleanFilter

from .models import Correspondent, Document, Tag


class CorrespondentFilterSet(FilterSet):

    class Meta(object):
        model = Correspondent
        fields = {
            "name": [
                "startswith", "endswith", "contains",
                "istartswith", "iendswith", "icontains"
            ],
            "slug": ["istartswith", "iendswith", "icontains"]
        }


class TagFilterSet(FilterSet):

    class Meta(object):
        model = Tag
        fields = {
            "name": [
                "startswith", "endswith", "contains",
                "istartswith", "iendswith", "icontains"
            ],
            "slug": ["istartswith", "iendswith", "icontains"]
        }


class DocumentFilterSet(FilterSet):

    CHAR_KWARGS = {
        "lookup_expr": (
            "startswith",
            "endswith",
            "contains",
            "istartswith",
            "iendswith",
            "icontains"
        )
    }

    correspondent__name = CharFilter(name="correspondent__name", **CHAR_KWARGS)
    correspondent__slug = CharFilter(name="correspondent__slug", **CHAR_KWARGS)
    tags__name = CharFilter(name="tags__name", **CHAR_KWARGS)
    tags__slug = CharFilter(name="tags__slug", **CHAR_KWARGS)
    tags__empty = BooleanFilter(name='tags', lookup_expr='isnull', distinct=True)

    class Meta(object):
        model = Document
        fields = {
            "title": [
                "startswith", "endswith", "contains",
                "istartswith", "iendswith", "icontains"
            ],
            "content": ["contains", "icontains"],
        }
