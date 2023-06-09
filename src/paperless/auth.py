from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import PersistentRemoteUserMiddleware
from django.contrib.auth.models import User, Group
from django.utils.deprecation import MiddlewareMixin
from rest_framework import authentication

def add_user_to_default_groups(user):
    if settings.DEFAULT_GROUP is None or len(settings.DEFAULT_GROUP) == 0:
        return
    if user.is_authenticated:
        default_group_names = settings.DEFAULT_GROUP
        for group_name in default_group_names:
            group_name = group_name.strip()
            group = Group.objects.filter(name=group_name)

            if group.exists() and not user.groups.filter(name=group_name).exists():
                user.groups.add(group.first())

class AutoLoginMiddleware(MiddlewareMixin):
    def process_request(self, request):
        try:
            request.user = User.objects.get(username=settings.AUTO_LOGIN_USERNAME)
            auth.login(
                request=request,
                user=request.user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            add_user_to_default_groups(request.user)      
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
            print(f"Auto-Login with user {user}")
            return (user, None)
        else:
            return None


class HttpRemoteUserMiddleware(PersistentRemoteUserMiddleware):
    """This class allows authentication via HTTP_REMOTE_USER which is set for
    example by certain SSO applications.
    """

    header = settings.HTTP_REMOTE_USER_HEADER_NAME
    
    def process_request(self, request):
            super().process_request(request)
            add_user_to_default_groups(request.user)