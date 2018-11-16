from django_filters.rest_framework import BooleanFilter, FilterSet

from .models import Correspondent, Document, Tag


CHAR_KWARGS = (
    "startswith", "endswith", "contains",
    "istartswith", "iendswith", "icontains"
)


class CorrespondentFilterSet(FilterSet):

    class Meta:
        model = Correspondent
        fields = {
            "name": [
                "startswith", "endswith", "contains",
                "istartswith", "iendswith", "icontains"
            ],
            "slug": ["istartswith", "iendswith", "icontains"]
        }


class TagFilterSet(FilterSet):

    class Meta:
        model = Tag
        fields = {
            "name": [
                "startswith", "endswith", "contains",
                "istartswith", "iendswith", "icontains"
            ],
            "slug": ["istartswith", "iendswith", "icontains"]
        }


class DocumentFilterSet(FilterSet):

    tags_empty = BooleanFilter(
        label="Is tagged",
        field_name="tags",
        lookup_expr="isnull",
        exclude=True
    )

    class Meta:
        model = Document
        fields = {

            "title": CHAR_KWARGS,
            "content": ("contains", "icontains"),

            "correspondent__name": CHAR_KWARGS,
            "correspondent__slug": CHAR_KWARGS,

            "tags__name": CHAR_KWARGS,
            "tags__slug": CHAR_KWARGS,

        }
