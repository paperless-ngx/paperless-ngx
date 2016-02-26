from django.contrib import admin

from .models import Log


class LogAdmin(admin.ModelAdmin):

    list_display = ("message", "time", "level", "component")
    list_filter = ("level", "component",)


admin.site.register(Log, LogAdmin)
