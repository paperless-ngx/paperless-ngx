from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.templatetags.static import static

from .models import Sender, Tag, Document


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


class DocumentAdmin(admin.ModelAdmin):

    search_fields = ("sender__name", "title", "content",)
    list_display = ("edit", "created", "sender", "title", "tags_", "pdf")
    list_filter = (MonthListFilter, "tags", "sender")
    list_editable = ("sender", "title",)
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

# Unless we implement multi-user, these default registrations don't make sense.
admin.site.unregister(Group)
admin.site.unregister(User)
