from django.contrib import admin
from django.core.urlresolvers import reverse
from django.templatetags.static import static

from .models import Document


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("sender", "title", "content",)
    list_display = ("edit", "created", "sender", "title", "pdf")
    list_filter = ("created", "sender")
    save_on_top = True

    def edit(self, obj):
        return '<img src="{}" width="22" height="22" alt="Edit icon" />'.format(
            static("documents/img/edit.png"))
    edit.allow_tags = True

    def pdf(self, obj):
        return '<a href="{}">' \
                 '<img src="{}" width="22" height="22" alt="PDF icon">' \
               '</a>'.format(
                    reverse("fetch", kwargs={"pk": obj.pk}),
                    static("documents/img/application-pdf.png")
                )
    pdf.allow_tags = True

admin.site.register(Document, DocumentAdmin)
