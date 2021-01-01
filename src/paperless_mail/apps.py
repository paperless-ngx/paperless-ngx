from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _


class PaperlessMailConfig(AppConfig):
    name = 'paperless_mail'

    verbose_name = _('Paperless mail')
