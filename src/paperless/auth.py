from django.conf import settings
from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from rest_framework import authentication
from rest_framework import exceptions


class AutoLoginMiddleware(MiddlewareMixin):

    def process_request(self, request):
        try:
            request.user = User.objects.get(
                username=settings.AUTO_LOGIN_USERNAME)
        except User.DoesNotExist:
            pass


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


class HttpRemoteUserAuthentication(authentication.BaseAuthentication):
    """ This class allows authentication via HTTP_REMOTE_USER which is set for
        example by certain SSO applications.
    """

    def authenticate(self, request):
        username = request.META.get('HTTP_REMOTE_USER')
        if not username:
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')

        return (user, None)
