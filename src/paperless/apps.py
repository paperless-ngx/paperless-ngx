from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from paperless.signals import handle_failed_login


class PaperlessConfig(AppConfig):
    name = "paperless"

    verbose_name = _("Paperless")

    def ready(self):
        from django.contrib.auth.signals import user_login_failed

        user_login_failed.connect(handle_failed_login)
        AppConfig.ready(self)
