from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth import authenticate, login
import base64


class SessionOrBasicAuthMixin(AccessMixin):
    """
    Session or Basic Authentication mixin for Django.
    It determines if the requester is already logged in or if they have
    provided proper http-authorization and returning the view if all goes
    well, otherwise responding with a 401.

    Base for mixin found here: https://djangosnippets.org/snippets/3073/
    """

    def dispatch(self, request, *args, **kwargs):

        # check if user is authenticated via the session
        if request.user.is_authenticated:

            # Already logged in, just return the view.
            return super(SessionOrBasicAuthMixin, self).dispatch(
                request, *args, **kwargs
            )

        # apparently not authenticated via session, maybe via HTTP Basic?
        if 'HTTP_AUTHORIZATION' in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2:
                # NOTE: Support for only basic authentication
                if auth[0].lower() == "basic":
                    authString = base64.b64decode(auth[1]).decode('utf-8')
                    uname, passwd = authString.split(':')
                    user = authenticate(username=uname, password=passwd)
                    if user is not None:
                        if user.is_active:
                            login(request, user)
                            request.user = user
                            return super(
                                SessionOrBasicAuthMixin, self
                            ).dispatch(
                                request, *args, **kwargs
                            )

        # nope, really not authenticated
        return self.handle_no_permission()
