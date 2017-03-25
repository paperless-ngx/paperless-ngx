from django.conf import settings
from django.contrib import admin

from .models import Reminder


class ReminderAdmin(admin.ModelAdmin):

    class Media:
        css = {
            "all": ("paperless.css",)
        }

    list_per_page = settings.PAPERLESS_LIST_PER_PAGE
    list_display = ("date", "document", "note")
    list_filter = ("date",)
    list_editable = ("note",)


admin.site.register(Reminder, ReminderAdmin)
