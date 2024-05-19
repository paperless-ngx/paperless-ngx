from django.conf import settings as django_settings

from paperless.config import GeneralConfig


def settings(request):
    general_config = GeneralConfig()
    app_logo = django_settings.APP_LOGO
    if general_config.app_logo is not None and len(general_config.app_logo) > 0:
        app_logo = general_config.app_logo

    return {
        "EMAIL_ENABLED": django_settings.EMAIL_HOST != "localhost"
        or django_settings.EMAIL_HOST_USER != "",
        "DISABLE_REGULAR_LOGIN": django_settings.DISABLE_REGULAR_LOGIN,
        "ACCOUNT_ALLOW_SIGNUPS": django_settings.ACCOUNT_ALLOW_SIGNUPS,
        "domain": getattr(django_settings, "PAPERLESS_URL", request.get_host()),
        "APP_LOGO": app_logo,
    }
