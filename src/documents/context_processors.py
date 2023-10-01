from django.conf import settings as django_settings


def settings(request):
    return {
        "EMAIL_ENABLED": django_settings.EMAIL_HOST != "localhost"
        or django_settings.EMAIL_HOST_USER != "",
        "DISABLE_NORMAL_AUTH": django_settings.SOCIAL_AUTH_DISABLE_NORMAL_AUTH,
        "OIDC_ENABLE": django_settings.SOCIAL_AUTH_OIDC_ENABLE,
        "OIDC_NAME": django_settings.SOCIAL_AUTH_OIDC_NAME
        if django_settings.SOCIAL_AUTH_OIDC_ENABLE
        else None,
    }
