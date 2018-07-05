from datetime import datetime

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.templatetags.static import static

from .models import Correspondent, Tag, Document, Log


class MonthListFilter(admin.SimpleListFilter):

    title = "Month"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "month"

    def lookups(self, request, model_admin):
        r = []
        for document in Document.objects.all():
            r.append((
                document.created.strftime("%Y-%m"),
                document.created.strftime("%B %Y")
            ))
        return sorted(set(r), key=lambda x: x[0], reverse=True)

    def queryset(self, request, queryset):

        if not self.value():
            return None

        year, month = self.value().split("-")
        return queryset.filter(created__year=year, created__month=month)


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
            return (query, query)

        else:
            query = "{0}-{0}".format(date.year)
            display = "{}".format(date.year)
            return (query, display)

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

    list_display = ("name", "match", "matching_algorithm", "document_count")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")

    def document_count(self, obj):
        return obj.documents.count()


class TagAdmin(CommonAdmin):

    list_display = ("name", "colour", "match", "matching_algorithm", "document_count")
    list_filter = ("colour", "matching_algorithm")
    list_editable = ("colour", "match", "matching_algorithm")

    def document_count(self, obj):
        return obj.documents.count()


class DocumentAdmin(CommonAdmin):

    class Media:
        css = {
            "all": ("paperless.css",)
        }

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = ("added",)
    list_display = ("title", "created", "added", "thumbnail", "correspondent",
                    "tags_")
    list_filter = ("tags", "correspondent", FinancialYearFilter,
                   MonthListFilter)

    ordering = ["-created", "correspondent"]

    def has_add_permission(self, request):
        return False

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")
    created_.short_description = "Created"

    def thumbnail(self, obj):
        return self._html_tag(
            "a",
            self._html_tag(
                "img",
                src=reverse("fetch", kwargs={"kind": "thumb", "pk": obj.pk}),
                width=180,
                alt="Thumbnail of {}".format(obj.file_name),
                title=obj.file_name
            ),
            href=obj.download_url
        )
    thumbnail.allow_tags = True

    def tags_(self, obj):
        r = ""
        for tag in obj.tags.all():
            colour = tag.get_colour_display()
            r += self._html_tag(
                "a",
                tag.slug,
                **{
                    "class": "tag",
                    "style": "background-color: {};".format(colour),
                    "href": "{}?tags__id__exact={}".format(
                        reverse("admin:documents_document_changelist"),
                        tag.pk
                    )
                }
            )
        return r
    tags_.allow_tags = True

    def document(self, obj):
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
    document.allow_tags = True

    @staticmethod
    def _html_tag(kind, inside=None, **kwargs):

        attributes = []
        for lft, rgt in kwargs.items():
            attributes.append('{}="{}"'.format(lft, rgt))

        if inside is not None:
            return "<{kind} {attributes}>{inside}</{kind}>".format(
                kind=kind, attributes=" ".join(attributes), inside=inside)

        return "<{} {}/>".format(kind, " ".join(attributes))


class LogAdmin(CommonAdmin):

    list_display = ("created", "message", "level",)
    list_filter = ("level", "created",)


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Log, LogAdmin)


# Unless we implement multi-user, these default registrations don't make sense.
admin.site.unregister(Group)
admin.site.unregister(User)
