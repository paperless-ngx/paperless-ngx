from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.auth.models import Group, User
from django.db import models
from django.http import HttpResponseRedirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.http import urlquote
from django.utils.safestring import mark_safe
from djangoql.admin import DjangoQLSearchMixin

from .models import Correspondent, Document, DocumentType, Log, Tag


class FinancialYearFilter(admin.SimpleListFilter):

    title = "Financial Year"
    parameter_name = "fy"
    _fy_wraps = None

    def _fy_start(self, year):
        """Return date of the start of financial year for the given year."""
        fy_start = "{}-{}".format(str(year), settings.FY_START)
        return datetime.strptime(fy_start, "%Y-%m-%d").date()

    def _fy_end(self, year):
        """Return date of the end of financial year for the given year."""
        fy_end = "{}-{}".format(str(year), settings.FY_END)
        return datetime.strptime(fy_end, "%Y-%m-%d").date()

    def _fy_does_wrap(self):
        """Return whether the financial year spans across two years."""
        if self._fy_wraps is None:
            start = "{}".format(settings.FY_START)
            start = datetime.strptime(start, "%m-%d").date()
            end = "{}".format(settings.FY_END)
            end = datetime.strptime(end, "%m-%d").date()
            self._fy_wraps = end < start

        return self._fy_wraps

    def _determine_fy(self, date):
        """Return a (query, display) financial year tuple of the given date."""
        if self._fy_does_wrap():
            fy_start = self._fy_start(date.year)

            if date.date() >= fy_start:
                query = "{}-{}".format(date.year, date.year + 1)
            else:
                query = "{}-{}".format(date.year - 1, date.year)

            # To keep it simple we use the same string for both
            # query parameter and the display.
            return query, query

        else:
            query = "{0}-{0}".format(date.year)
            display = "{}".format(date.year)
            return query, display

    def lookups(self, request, model_admin):
        if not settings.FY_START or not settings.FY_END:
            return None

        r = []
        for document in Document.objects.all():
            r.append(self._determine_fy(document.created))

        return sorted(set(r), key=lambda x: x[0], reverse=True)

    def queryset(self, request, queryset):
        if not self.value() or not settings.FY_START or not settings.FY_END:
            return None

        start, end = self.value().split("-")
        return queryset.filter(created__gte=self._fy_start(start),
                               created__lte=self._fy_end(end))


class CommonAdmin(admin.ModelAdmin):
    list_per_page = settings.PAPERLESS_LIST_PER_PAGE


class CorrespondentAdmin(CommonAdmin):

    list_display = (
        "name",
        "automatic_classification",
        "document_count",
        "last_correspondence"
    )
    list_editable = ("automatic_classification",)

    readonly_fields = ("slug",)

    def get_queryset(self, request):
        qs = super(CorrespondentAdmin, self).get_queryset(request)
        qs = qs.annotate(
            document_count=models.Count("documents"),
            last_correspondence=models.Max("documents__created")
        )
        return qs

    def document_count(self, obj):
        return obj.document_count
    document_count.admin_order_field = "document_count"

    def last_correspondence(self, obj):
        return obj.last_correspondence
    last_correspondence.admin_order_field = "last_correspondence"


class TagAdmin(CommonAdmin):

    list_display = (
        "name",
        "colour",
        "automatic_classification",
        "document_count")
    list_filter = ("colour",)
    list_editable = ("colour", "automatic_classification")

    readonly_fields = ("slug",)

    class Media:
        js = ("js/colours.js",)

    def get_queryset(self, request):
        qs = super(TagAdmin, self).get_queryset(request)
        qs = qs.annotate(document_count=models.Count("documents"))
        return qs

    def document_count(self, obj):
        return obj.document_count
    document_count.admin_order_field = "document_count"


class DocumentTypeAdmin(CommonAdmin):

    list_display = ("name", "automatic_classification", "document_count")
    list_editable = ("automatic_classification",)

    readonly_fields = ("slug",)

    def get_queryset(self, request):
        qs = super(DocumentTypeAdmin, self).get_queryset(request)
        qs = qs.annotate(document_count=models.Count("documents"))
        return qs

    def document_count(self, obj):
        return obj.document_count
    document_count.admin_order_field = "document_count"


class DocumentAdmin(DjangoQLSearchMixin, CommonAdmin):

    class Media:
        css = {
            "all": ("paperless.css",)
        }

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = ("added", "file_type", "storage_type",)
    list_display = ("title", "created", "added", "correspondent",
                    "tags_", "archive_serial_number", "document_type")
    list_filter = (
        "document_type",
        "tags",
        "correspondent",
        FinancialYearFilter
    )

    filter_horizontal = ("tags",)

    ordering = ["-created", "correspondent"]

    date_hierarchy = "created"

    def has_add_permission(self, request):
        return False

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")
    created_.short_description = "Created"

    @mark_safe
    def thumbnail(self, obj):
        return self._html_tag(
            "a",
            self._html_tag(
                "img",
                src=reverse("fetch", kwargs={"kind": "thumb", "pk": obj.pk}),
                height=100,
                alt="Thumbnail of {}".format(obj.file_name),
                title=obj.file_name
            ),
            href=obj.download_url
        )

    @mark_safe
    def tags_(self, obj):
        r = ""
        for tag in obj.tags.all():
            colour = tag.get_colour_display()
            r += self._html_tag(
                "span",
                tag.slug + ", "
            )
        return r

    @mark_safe
    def document(self, obj):
        # TODO: is this method even used anymore?
        return self._html_tag(
            "a",
            self._html_tag(
                "img",
                src=static("documents/img/{}.png".format(obj.file_type)),
                width=22,
                height=22,
                alt=obj.file_type,
                title=obj.file_name
            ),
            href=obj.download_url
        )

    @staticmethod
    def _html_tag(kind, inside=None, **kwargs):
        attributes = format_html_join(' ', '{}="{}"', kwargs.items())

        if inside is not None:
            return format_html("<{kind} {attributes}>{inside}</{kind}>",
                               kind=kind, attributes=attributes, inside=inside)

        return format_html("<{} {}/>", kind, attributes)


class LogAdmin(CommonAdmin):

    list_display = ("created", "message", "level",)
    list_filter = ("level", "created",)


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Log, LogAdmin)


# Unless we implement multi-user, these default registrations don't make sense.
#admin.site.unregister(Group)
#admin.site.unregister(User)
