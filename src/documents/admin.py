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

from documents.actions import (
    add_tag_to_selected,
    remove_correspondent_from_selected,
    remove_tag_from_selected,
    set_correspondent_on_selected
)

from .models import Correspondent, Document, Log, Tag


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


class RecentCorrespondentFilter(admin.RelatedFieldListFilter):
    """
    If PAPERLESS_RECENT_CORRESPONDENT_YEARS is set, we limit the available
    correspondents to documents sent our way over the past ``n`` years.
    """

    def field_choices(self, field, request, model_admin):

        years = settings.PAPERLESS_RECENT_CORRESPONDENT_YEARS
        correspondents = Correspondent.objects.all()

        if years and years > 0:
            self.title = "Correspondent (Recent)"
            days = 365 * years
            correspondents = correspondents.filter(
                documents__created__gte=datetime.now() - timedelta(days=days)
            ).distinct()

        return [(c.id, c.name) for c in correspondents]


class CommonAdmin(admin.ModelAdmin):
    list_per_page = settings.PAPERLESS_LIST_PER_PAGE


class CorrespondentAdmin(CommonAdmin):

    list_display = (
        "name",
        "match",
        "matching_algorithm",
        "document_count",
        "last_correspondence"
    )
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")

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
        "name", "colour", "match", "matching_algorithm", "document_count")
    list_filter = ("colour", "matching_algorithm")
    list_editable = ("colour", "match", "matching_algorithm")

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


class DocumentAdmin(CommonAdmin):

    class Media:
        css = {
            "all": ("paperless.css",)
        }

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = ("added", "file_type", "storage_type",)
    list_display = ("title", "created", "added", "thumbnail", "correspondent",
                    "tags_")
    list_filter = (
        "tags",
        ("correspondent", RecentCorrespondentFilter),
        FinancialYearFilter
    )

    filter_horizontal = ("tags",)

    ordering = ["-created", "correspondent"]

    actions = [
        add_tag_to_selected,
        remove_tag_from_selected,
        set_correspondent_on_selected,
        remove_correspondent_from_selected
    ]

    date_hierarchy = "created"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document_queue = []

    def has_add_permission(self, request):
        return False

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")
    created_.short_description = "Created"

    def changelist_view(self, request, extra_context=None):

        response = super().changelist_view(
            request,
            extra_context=extra_context
        )

        if request.method == "GET":
            cl = self.get_changelist_instance(request)
            self.document_queue = [doc.id for doc in cl.queryset]

        return response

    def change_view(self, request, object_id=None, form_url='',
                    extra_context=None):

        extra_context = extra_context or {}

        if self.document_queue and object_id:
            if int(object_id) in self.document_queue:
                # There is a queue of documents
                current_index = self.document_queue.index(int(object_id))
                if current_index < len(self.document_queue) - 1:
                    # ... and there are still documents in the queue
                    extra_context["next_object"] = self.document_queue[
                        current_index + 1
                    ]

        return super(DocumentAdmin, self).change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    def response_change(self, request, obj):

        # This is mostly copied from ModelAdmin.response_change()
        opts = self.model._meta
        preserved_filters = self.get_preserved_filters(request)

        msg_dict = {
            "name": opts.verbose_name,
            "obj": format_html(
                '<a href="{}">{}</a>',
                urlquote(request.path),
                obj
            ),
        }
        if "_saveandeditnext" in request.POST:
            msg = format_html(
                'The {name} "{obj}" was changed successfully. '
                'Editing next object.',
                **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = reverse(
                "admin:{}_{}_change".format(opts.app_label, opts.model_name),
                args=(request.POST["_next_object"],),
                current_app=self.admin_site.name
            )
            redirect_url = add_preserved_filters(
                {
                    "preserved_filters": preserved_filters,
                    "opts": opts
                },
                redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        return super().response_change(request, obj)

    @mark_safe
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

    @mark_safe
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
admin.site.register(Document, DocumentAdmin)
admin.site.register(Log, LogAdmin)


# Unless we implement multi-user, these default registrations don't make sense.
admin.site.unregister(Group)
admin.site.unregister(User)
