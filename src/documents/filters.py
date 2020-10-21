from django_filters.rest_framework import BooleanFilter, FilterSet

from .models import Correspondent, Document, Tag, DocumentType


CHAR_KWARGS = ["istartswith", "iendswith", "icontains", "iexact"]
ID_KWARGS = ["in", "exact"]


class CorrespondentFilterSet(FilterSet):

    class Meta:
        model = Correspondent
        fields = {
            "name": CHAR_KWARGS
        }


class TagFilterSet(FilterSet):

    class Meta:
        model = Tag
        fields = {
            "name": CHAR_KWARGS
        }


class DocumentTypeFilterSet(FilterSet):

    class Meta:
        model = DocumentType
        fields = {
            "name": CHAR_KWARGS
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
            "content": CHAR_KWARGS,

            "correspondent__id": ID_KWARGS,
            "correspondent__name": CHAR_KWARGS,

            "tags__id": ID_KWARGS,
            "tags__name": CHAR_KWARGS,

            "document_type__id": ID_KWARGS,
            "document_type__name": CHAR_KWARGS

        }
