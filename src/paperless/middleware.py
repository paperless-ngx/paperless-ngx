from django.utils.deprecation import MiddlewareMixin
from .models import User


class Middleware(MiddlewareMixin):
    """
      This is a dummy authentication middleware class that creates what
      is roughly an Anonymous authenticated user so we can disable login
      and not interfere with existing user ID's. It's only used if
      login is disabled in paperless.conf (default is to require login)
    """

    def process_request(self, request):
        request.user = User()
