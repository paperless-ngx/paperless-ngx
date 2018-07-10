from datetime import datetime

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import reverse
from django.templatetags.static import static
from django.utils.safestring import mark_safe

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

    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        for document in Document.objects.filter(correspondent__isnull=True).exclude(tags__is_archived_tag=True):
            if obj.matches(document.content):
                document.correspondent = obj
                document.save(update_fields=("correspondent",))

class TagAdmin(CommonAdmin):

    list_display = ("name", "colour", "match", "matching_algorithm")
    list_filter = ("colour", "matching_algorithm")
    list_editable = ("colour", "match", "matching_algorithm")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        for document in Document.objects.all().exclude(tags__is_archived_tag=True):
            if obj.matches(document.content):
                document.tags.add(obj)


def add_tag_to_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        tag = Tag.objects.get(id=request.POST.get('tag_id'))
        if n:
            for obj in queryset:
                obj.tags.add(tag)
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            modeladmin.message_user(request, "Successfully added tag %(tag)s to %(count)d %(items)s." % {
                "tag": tag.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Add tag to multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        action="add_tag_to_selected",
        tags=Tag.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/mass_modify_tag.html" % (app_label, opts.model_name)
    , context)


add_tag_to_selected.short_description = "Add tag to selected documents"


def remove_tag_from_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        tag = Tag.objects.get(id=request.POST.get('tag_id'))
        if n:
            for obj in queryset:
                obj.tags.remove(tag)
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            modeladmin.message_user(request, "Successfully removed tag %(tag)s from %(count)d %(items)s." % {
                "tag": tag.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Remove tag from multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        action="remove_tag_from_selected",
        tags=Tag.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/mass_modify_tag.html" % (app_label, opts.model_name)
    , context)


remove_tag_from_selected.short_description = "Remove tag from selected documents"


def set_correspondent_on_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        correspondent = Correspondent.objects.get(id=request.POST.get('correspondent_id'))
        if n:
            for obj in queryset:
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            queryset.update(correspondent=correspondent)
            modeladmin.message_user(request, "Successfully set correspondent %(correspondent)s on %(count)d %(items)s." % {
                "correspondent": correspondent.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Set correspondent on multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        correspondents=Correspondent.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/set_correspondent.html" % (app_label, opts.model_name)
    , context)


set_correspondent_on_selected.short_description = "Set correspondent on selected documents"


def remove_correspondent_from_selected(modeladmin, request, queryset):
    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    n = queryset.count()
    if n:
        for obj in queryset:
            obj_display = str(obj)
            modeladmin.log_change(request, obj, obj_display)
        queryset.update(correspondent=None)
        modeladmin.message_user(request, "Successfully removed correspondent from %(count)d %(items)s." % {
            "count": n, "items": model_ngettext(modeladmin.opts, n)
        }, messages.SUCCESS)

    return None


remove_correspondent_from_selected.short_description = "Remove correspondent from selected documents"


class DocumentAdmin(CommonAdmin):

    class Media:
        css = {
            "all": ("paperless.css",)

        }

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = ("added",)
    list_display = ("title", "created", "added", "thumbnail", "correspondent",
                    "tags_", "archive_serial_number")
    list_filter = ("tags", "correspondent", FinancialYearFilter,
                   MonthListFilter)

    ordering = ["-created", "correspondent"]


    actions = [add_tag_to_selected, remove_tag_from_selected, set_correspondent_on_selected, remove_correspondent_from_selected]

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
