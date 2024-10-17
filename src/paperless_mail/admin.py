from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from guardian.admin import GuardedModelAdmin

from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail


class MailAccountAdminForm(forms.ModelForm):
    """Metadata classes used by Django admin to display the form."""

    class Meta:
        """Metadata class used by Django admin to display the form."""

        model = MailAccount
        widgets = {
            "password": forms.PasswordInput(),
        }
        fields = [
            "name",
            "imap_server",
            "username",
            "imap_security",
            "username",
            "password",
            "is_token",
            "character_set",
        ]


class MailAccountAdmin(GuardedModelAdmin):
    list_display = ("name", "imap_server", "username")

    fieldsets = [
        (None, {"fields": ["name", "imap_server", "imap_port"]}),
        (
            _("Authentication"),
            {"fields": ["imap_security", "username", "password", "is_token"]},
        ),
        (_("Advanced settings"), {"fields": ["character_set"]}),
    ]
    form = MailAccountAdminForm


class MailRuleAdmin(GuardedModelAdmin):
    radio_fields = {
        "attachment_type": admin.VERTICAL,
        "action": admin.VERTICAL,
        "assign_title_from": admin.VERTICAL,
        "assign_correspondent_from": admin.VERTICAL,
    }

    fieldsets = (
        (None, {"fields": ("name", "order", "account", "enabled", "folder")}),
        (
            _("Filter"),
            {
                "description": _(
                    "Paperless will only process mails that match ALL of the "
                    "filters given below.",
                ),
                "fields": (
                    "filter_from",
                    "filter_to",
                    "filter_subject",
                    "filter_body",
                    "filter_attachment_filename_include",
                    "filter_attachment_filename_exclude",
                    "maximum_age",
                    "consumption_scope",
                    "attachment_type",
                ),
            },
        ),
        (
            _("Actions"),
            {
                "description": _(
                    "The action applied to the mail. This action is only "
                    "performed when the mail body or attachments were "
                    "consumed from the mail.",
                ),
                "fields": ("action", "action_parameter"),
            },
        ),
        (
            _("Metadata"),
            {
                "description": _(
                    "Assign metadata to documents consumed from this rule "
                    "automatically. If you do not assign tags, types or "
                    "correspondents here, paperless will still process all "
                    "matching rules that you have defined.",
                ),
                "fields": (
                    "assign_title_from",
                    "assign_tags",
                    "assign_document_type",
                    "assign_correspondent_from",
                    "assign_correspondent",
                ),
            },
        ),
    )

    list_filter = ("account",)

    list_display = ("order", "name", "account", "folder", "action")

    list_editable = ("order",)

    list_display_links = ("name",)

    sortable_by = []

    ordering = ["order"]

    raw_id_fields = ("assign_correspondent", "assign_document_type")

    filter_horizontal = ("assign_tags",)


class ProcessedMailAdmin(admin.ModelAdmin):
    class Meta:
        model = ProcessedMail
        fields = "__all__"

    list_display = ("subject", "status", "processed", "received", "rule")

    ordering = ["-processed"]

    readonly_fields = [
        "owner",
        "rule",
        "folder",
        "uid",
        "subject",
        "received",
        "processed",
        "status",
        "error",
    ]

    list_display_links = ["subject"]

    list_filter = ("status", "rule")


admin.site.register(MailAccount, MailAccountAdmin)
admin.site.register(MailRule, MailRuleAdmin)
admin.site.register(ProcessedMail, ProcessedMailAdmin)
