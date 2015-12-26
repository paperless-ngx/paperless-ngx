from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static

from .models import Document


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("sender", "title", "content",)
    list_display = ("edit", "created", "sender", "title", "thumbnail", "pdf")
    list_filter = ("created", "sender")
    save_on_top = True

    def edit(self, obj):
        return '<img src="{}" width="64" height="64" alt="Edit icon" />'.format(
            static("documents/img/edit.png"))
    edit.allow_tags = True

    def thumbnail(self, obj):
        return '<a href="{media}documents/img/{pk:07}.jpg" target="_blank">' \
                 '<img src="{media}documents/img/{pk:07}.jpg" width="100" />' \
               '</a>'.format(media=settings.MEDIA_URL, pk=obj.pk)
    thumbnail.allow_tags = True

    def pdf(self, obj):
        return '<a href="{}documents/pdf/{:07}.pdf">' \
                 '<img src="{}" width="64" height="64" alt="PDF icon">' \
               '</a>'.format(
                    settings.MEDIA_URL,
                    obj.pk,
                    static("documents/img/application-pdf.png")
                )
    pdf.allow_tags = True

admin.site.register(Document, DocumentAdmin)
