from django.conf import settings as django_settings


def settings(request):
    return {"settings": django_settings}
