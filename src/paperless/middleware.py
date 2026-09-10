from compression_middleware.middleware import CompressionMiddleware
from django.conf import settings

from paperless import version


class StreamAwareCompressionMiddleware(CompressionMiddleware):
    """
    Bypasses compression for server-sent streams (text/event-stream).

    See https://github.com/friedelwolff/django-compression-middleware/pull/7
    """

    def process_response(self, request, response):
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("text/event-stream"):
            return response
        return super().process_response(request, response)


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
