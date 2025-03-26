from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

# from edoc import config
from edoc.signals import handle_failed_login


class Config(AppConfig):
    name = "edoc"

    verbose_name = _("Edoc")

    def ready(self):
        from django.contrib.auth.signals import user_login_failed

        user_login_failed.connect(handle_failed_login)
        AppConfig.ready(self)
