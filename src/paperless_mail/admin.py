from django.contrib import admin
from django import forms

from paperless_mail.models import MailAccount, MailRule


class MailAccountForm(forms.ModelForm):

    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        fields = '__all__'
        model = MailAccount


class MailAccountAdmin(admin.ModelAdmin):

    list_display = ("name", "imap_server", "username")


class MailRuleAdmin(admin.ModelAdmin):

    list_display = ("name", "account", "folder", "action")


admin.site.register(MailAccount, MailAccountAdmin)
admin.site.register(MailRule, MailRuleAdmin)
