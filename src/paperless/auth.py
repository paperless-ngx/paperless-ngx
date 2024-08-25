import logging

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import PersistentRemoteUserMiddleware
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from rest_framework import authentication

logger = logging.getLogger("paperless.auth")


class AutoLoginMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        # Dont use auto-login with token request
        if request.path.startswith("/api/token/") and request.method == "POST":
            return None
        try:
            request.user = User.objects.get(username=settings.AUTO_LOGIN_USERNAME)
            auth.login(
                request=request,
                user=request.user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
        except User.DoesNotExist:
            pass


class AngularApiAuthenticationOverride(authentication.BaseAuthentication):
    """This class is here to provide authentication to the angular dev server
    during development. This is disabled in production.
    """

    def authenticate(self, request):
        if (
            settings.DEBUG
            and "Referer" in request.headers
            and request.headers["Referer"].startswith("http://localhost:4200/")
        ):
            user = User.objects.filter(is_staff=True).first()
            logger.debug(f"Auto-Login with user {user}")
            return (user, None)
        else:
            return None


class HttpRemoteUserMiddleware(PersistentRemoteUserMiddleware):
    """This class allows authentication via HTTP_REMOTE_USER which is set for
    example by certain SSO applications.
    """

    header = settings.HTTP_REMOTE_USER_HEADER_NAME

    def process_request(self, request: HttpRequest) -> None:
        # If remote user auth is enabled only for the frontend, not the API,
        # then we need dont want to authenticate the user for API requests.
        if (
            "/api/" in request.path
            and "paperless.auth.PaperlessRemoteUserAuthentication"
            not in settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        ):
            return
        return super().process_request(request)


class PaperlessRemoteUserAuthentication(authentication.RemoteUserAuthentication):
    """
    REMOTE_USER authentication for DRF which overrides the default header.
    """

    header = settings.HTTP_REMOTE_USER_HEADER_NAME
