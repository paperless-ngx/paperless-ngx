from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from edoc_mail.signals import mail_consumer_declaration


class EdocMailConfig(AppConfig):
    name = "edoc_mail"

    verbose_name = _("Edoc mail")

    def ready(self):
        from documents.signals import document_consumer_declaration

        if settings.TIKA_ENABLED:
            document_consumer_declaration.connect(mail_consumer_declaration)
        AppConfig.ready(self)
