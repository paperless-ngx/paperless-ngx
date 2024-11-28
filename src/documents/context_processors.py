from django.conf import settings as django_settings

from paperless.config import GeneralConfig


def settings(request):
    general_config = GeneralConfig()

    app_title = (
        django_settings.APP_TITLE
        if general_config.app_title is None or len(general_config.app_title) == 0
        else general_config.app_title
    )
    app_logo = (
        django_settings.APP_LOGO
        if general_config.app_logo is None or len(general_config.app_logo) == 0
        else django_settings.BASE_URL + general_config.app_logo.lstrip("/")
    )

    return {
        "EMAIL_ENABLED": django_settings.EMAIL_HOST != "localhost"
        or django_settings.EMAIL_HOST_USER != "",
        "DISABLE_REGULAR_LOGIN": django_settings.DISABLE_REGULAR_LOGIN,
        "REDIRECT_LOGIN_TO_SSO": django_settings.REDIRECT_LOGIN_TO_SSO,
        "ACCOUNT_ALLOW_SIGNUPS": django_settings.ACCOUNT_ALLOW_SIGNUPS,
        "domain": getattr(django_settings, "PAPERLESS_URL", request.get_host()),
        "APP_TITLE": app_title,
        "APP_LOGO": app_logo,
    }
