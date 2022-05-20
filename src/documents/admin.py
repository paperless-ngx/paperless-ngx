from django.contrib import admin

from .models import Correspondent
from .models import Document
from .models import DocumentType
from .models import SavedView
from .models import SavedViewFilterRule
from .models import StoragePath
from .models import Tag


class CorrespondentAdmin(admin.ModelAdmin):

    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")


class TagAdmin(admin.ModelAdmin):

    list_display = ("name", "color", "match", "matching_algorithm")
    list_filter = ("color", "matching_algorithm")
    list_editable = ("color", "match", "matching_algorithm")


class DocumentTypeAdmin(admin.ModelAdmin):

    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = (
        "added",
        "modified",
        "mime_type",
        "storage_type",
        "filename",
        "checksum",
        "archive_filename",
        "archive_checksum",
    )

    list_display_links = ("title",)

    list_display = ("id", "title", "mime_type", "filename", "archive_filename")

    list_filter = (
        ("mime_type"),
        ("archive_serial_number", admin.EmptyFieldListFilter),
        ("archive_filename", admin.EmptyFieldListFilter),
    )

    filter_horizontal = ("tags",)

    ordering = ["-id"]

    date_hierarchy = "created"

    def has_add_permission(self, request):
        return False

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")

    created_.short_description = "Created"

    def delete_queryset(self, request, queryset):
        from documents import index

        with index.open_index_writer() as writer:
            for o in queryset:
                index.remove_document(writer, o)

        super().delete_queryset(request, queryset)

    def delete_model(self, request, obj):
        from documents import index

        index.remove_document_from_index(obj)
        super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        from documents import index

        index.add_or_update_document(obj)
        super().save_model(request, obj, form, change)


class RuleInline(admin.TabularInline):
    model = SavedViewFilterRule


class SavedViewAdmin(admin.ModelAdmin):

    list_display = ("name", "user")

    inlines = [RuleInline]


class StoragePathInline(admin.TabularInline):
    model = StoragePath


class StoragePathAdmin(admin.ModelAdmin):
    list_display = ("name", "path", "match", "matching_algorithm")
    list_filter = ("path", "matching_algorithm")
    list_editable = ("path", "match", "matching_algorithm")


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(SavedView, SavedViewAdmin)
admin.site.register(StoragePath, StoragePathAdmin)
