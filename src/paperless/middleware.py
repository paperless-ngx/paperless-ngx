from functools import wraps

from django.conf import settings

from paperless import version


def compress_exempt(view_func):
    """
    Exempt a view's response from compression.

    The compression middleware reads the flag off the Django request, so it
    has to be set there: DRF's request wrapper proxies reads but keeps writes
    to itself, and a flag set on it never arrives. Decorating dispatch runs
    before that wrapper exists.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        request.compress_exempt = True
        return view_func(request, *args, **kwargs)

    return wrapper


class ApiVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
            response["X-Api-Version"] = versions[len(versions) - 1]
            response["X-Version"] = version.__full_version_str__

        return response
