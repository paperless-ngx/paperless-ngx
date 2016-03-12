import django_filters

from rest_framework import filters

from .models import Document, Correspondent, Tag

#
# I hate how copy/pastey this file is.  Recommendations are welcome.
#


# Filters


class RelatedFilter(django_filters.MethodFilter):

    def __init__(self, *args, **kwargs):
        self.key = kwargs.pop("key")
        self.lookup_type = kwargs.get("lookup_type")
        django_filters.MethodFilter.__init__(self, *args, **kwargs)

    def filter(self, qs, value):
        if not value:
            return qs
        return qs.filter(**{"tags__{}".format(self.key): value})


# FilterSets


class SluggableFilterSet(filters.FilterSet):

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


class CorrespondentFilterSet(SluggableFilterSet):

    class Meta(object):
        model = Correspondent
        fields = ["name"]


class TagFilterSet(SluggableFilterSet):

    class Meta(object):
        model = Tag
        fields = ["name", "slug"]


class DocumentFilterSet(filters.FilterSet):

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

    tags__name = RelatedFilter(key="name")
    tags__name__startswith = RelatedFilter(key="name__startswith")
    tags__name__istartswith = RelatedFilter(key="name__istartswith")
    tags__name__endswith = RelatedFilter(key="name__endswith")
    tags__name__iendswith = RelatedFilter(key="name__iendswith")
    tags__name__contains = RelatedFilter(key="name__contains")
    tags__name__icontains = RelatedFilter(key="name__icontains")

    tags__slug = RelatedFilter(key="slug")
    tags__slug__startswith = RelatedFilter(key="slug__startswith")
    tags__slug__istartswith = RelatedFilter(key="slug__istartswith")
    tags__slug__endswith = RelatedFilter(key="slug__endswith")
    tags__slug__iendswith = RelatedFilter(key="slug__iendswith")
    tags__slug__contains = RelatedFilter(key="slug__contains")
    tags__slug__icontains = RelatedFilter(key="slug__icontains")

    correspondent__name = RelatedFilter(key="name")
    correspondent__name__startswith = RelatedFilter(key="name__startswith")
    correspondent__name__istartswith = RelatedFilter(key="name__istartswith")
    correspondent__name__endswith = RelatedFilter(key="name__endswith")
    correspondent__name__iendswith = RelatedFilter(key="name__iendswith")
    correspondent__name__contains = RelatedFilter(key="name__contains")
    correspondent__name__icontains = RelatedFilter(key="name__icontains")

    correspondent__slug = RelatedFilter(key="slug")
    correspondent__slug__startswith = RelatedFilter(key="slug__startswith")
    correspondent__slug__istartswith = RelatedFilter(key="slug__istartswith")
    correspondent__slug__endswith = RelatedFilter(key="slug__endswith")
    correspondent__slug__iendswith = RelatedFilter(key="slug__iendswith")
    correspondent__slug__contains = RelatedFilter(key="slug__contains")
    correspondent__slug__icontains = RelatedFilter(key="slug__icontains")

    class Meta(object):
        model = Document
        fields = ["title"]
