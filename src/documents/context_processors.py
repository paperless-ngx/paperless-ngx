from django.conf import settings as django_settings


def settings(request):
    return {
        "EMAIL_ENABLED": django_settings.EMAIL_HOST != "localhost"
        or django_settings.EMAIL_HOST_USER != "",
        "DISABLE_REGULAR_LOGIN": django_settings.DISABLE_REGULAR_LOGIN,
        "ACCOUNT_ALLOW_SIGNUPS": django_settings.ACCOUNT_ALLOW_SIGNUPS,
        "domain": getattr(django_settings, "EDOC_URL", request.get_host()),
    }
