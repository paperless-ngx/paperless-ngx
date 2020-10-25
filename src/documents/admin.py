from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import Correspondent, Document, DocumentType, Log, Tag


class CorrespondentAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "automatic_classification"
    )
    list_editable = ("automatic_classification",)

    readonly_fields = ("slug",)


class TagAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "colour",
        "automatic_classification"
    )

    list_filter = ("colour",)
    list_editable = ("colour", "automatic_classification")

    readonly_fields = ("slug",)


class DocumentTypeAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "automatic_classification"
    )

    list_editable = ("automatic_classification",)

    readonly_fields = ("slug",)


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = ("added", "file_type", "storage_type",)
    list_display = ("title", "created", "added", "correspondent",
                    "tags_", "archive_serial_number", "document_type")
    list_filter = (
        "document_type",
        "tags",
        "correspondent"
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
    def tags_(self, obj):
        r = ""
        for tag in obj.tags.all():
            colour = tag.get_colour_display()
            r += self._html_tag(
                "span",
                tag.slug + ", "
            )
        return r

    @staticmethod
    def _html_tag(kind, inside=None, **kwargs):
        attributes = format_html_join(' ', '{}="{}"', kwargs.items())

        if inside is not None:
            return format_html("<{kind} {attributes}>{inside}</{kind}>",
                               kind=kind, attributes=attributes, inside=inside)

        return format_html("<{} {}/>", kind, attributes)


class LogAdmin(admin.ModelAdmin):

    list_display = ("created", "message", "level",)
    list_filter = ("level", "created",)


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Log, LogAdmin)


# Unless we implement multi-user, these default registrations don't make sense.
admin.site.unregister(Group)
admin.site.unregister(User)
