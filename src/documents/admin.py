from django.contrib import admin
from django.core.urlresolvers import reverse
from django.templatetags.static import static

from .models import Sender, Tag, Document


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("sender__name", "title", "content",)
    list_display = ("edit", "created", "sender", "title", "tags_", "pdf")
    list_filter = ("created", "tags", "sender")
    list_per_page = 25

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

    def tags_(self, obj):
        r = ""
        for tag in obj.tags.all():
            r += '<span style="padding: 0 0.5em; background-color: {}; color: #ffffff; border-radius: 0.2em; margin: 1px; display: inline-block;">{}</span>'.format(
                tag.get_colour_display(),
                tag.slug
            )
        return r
    tags_.allow_tags = True

admin.site.register(Sender)
admin.site.register(Tag)
admin.site.register(Document, DocumentAdmin)
