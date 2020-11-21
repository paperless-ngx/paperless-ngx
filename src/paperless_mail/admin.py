from django.contrib import admin
from paperless_mail.models import MailAccount, MailRule


class MailAccountAdmin(admin.ModelAdmin):

    list_display = ("name", "imap_server", "username")


class MailRuleAdmin(admin.ModelAdmin):

    list_filter = ("account",)

    list_display = ("order", "name", "account", "folder", "action")

    list_editable = ("order", )

    list_display_links = ("name", )

    sortable_by = []

    ordering = ["order"]


admin.site.register(MailAccount, MailAccountAdmin)
admin.site.register(MailRule, MailRuleAdmin)
