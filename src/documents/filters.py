import django_filters

from rest_framework import filters

from .models import Document, Correspondent, Tag


class DocumentFilter(filters.FilterSet):

    title__startswith = django_filters.CharFilter(
        name="title", lookup_type="startswith",
        label="Title starts with (case sensitive)"
    )
    title__istartswith = django_filters.CharFilter(
        name="title", lookup_type="istartswith",
        label="Title starts with (case insensitive)"
    )
    title__endswith = django_filters.CharFilter(
        name="title", lookup_type="endswith",
        label="Title ends with (case sensitive)"
    )
    title__iendswith = django_filters.CharFilter(
        name="title", lookup_type="endswith",
        label="Title ends with (case insensitive)"
    )
    title__contains = django_filters.CharFilter(
        name="title", lookup_type="contains",
        label="Title contains (case sensitive)"
    )
    title__icontains = django_filters.CharFilter(
        name="title", lookup_type="icontains",
        label="Title contains (case insensitive)"
    )

    content__contains = django_filters.CharFilter(
        name="content", lookup_type="contains")
    content__icontains = django_filters.CharFilter(
        name="content", lookup_type="icontains")

    class Meta(object):
        model = Document
        fields = ["title"]


class SluggableFilter(filters.FilterSet):

    name__startswith = django_filters.CharFilter(
        name="name", lookup_type="startswith",
        label="Name starts with (case sensitive)"
    )
    name__istartswith = django_filters.CharFilter(
        name="name", lookup_type="istartswith",
        label="Name starts with (case insensitive)"
    )
    name__endswith = django_filters.CharFilter(
        name="name", lookup_type="endswith",
        label="Name ends with (case sensitive)"
    )
    name__iendswith = django_filters.CharFilter(
        name="name", lookup_type="endswith",
        label="Name ends with (case insensitive)"
    )
    name__contains = django_filters.CharFilter(
        name="name", lookup_type="contains",
        label="Name contains (case sensitive)"
    )
    name__icontains = django_filters.CharFilter(
        name="name", lookup_type="icontains",
        label="Name contains (case insensitive)"
    )

    slug__istartswith = django_filters.CharFilter(
        name="slug", lookup_type="istartswith",
        label="Slug starts with (case insensitive)"
    )
    slug__iendswith = django_filters.CharFilter(
        name="slug", lookup_type="endswith",
        label="Slug ends with (case insensitive)"
    )
    slug__icontains = django_filters.CharFilter(
        name="slug", lookup_type="icontains",
        label="Slug contains (case insensitive)"
    )


class CorrespondentFilter(SluggableFilter):

    class Meta(object):
        model = Correspondent
        fields = ["name"]


class TagFilter(SluggableFilter):

    class Meta(object):
        model = Tag
        fields = ["name"]
