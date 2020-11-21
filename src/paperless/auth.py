from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication


class AngularApiAuthenticationOverride(authentication.BaseAuthentication):
    """ This class is here to provide authentication to the angular dev server
        during development. This is disabled in production.
    """

    def authenticate(self, request):
        if settings.DEBUG and 'Referer' in request.headers and request.headers['Referer'].startswith('http://localhost:4200/'):  # NOQA: E501
            user = User.objects.filter(is_staff=True).first()
            print("Auto-Login with user {}".format(user))
            return (user, None)
        else:
            return None
